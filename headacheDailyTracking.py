import asyncio
import os
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from fpdf import FPDF
from dotenv import load_dotenv

# Load bot token
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Initialize bot and router
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Database setup
conn = sqlite3.connect("headache_logs.db")
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS headaches (
                    id INTEGER PRIMARY KEY, 
                    date TEXT, 
                    start_time TEXT, 
                    stop_time TEXT, 
                    medications TEXT, 
                    rating INTEGER, 
                    comments TEXT)''')
conn.commit()

# Store user input before saving to database
user_data = {}

# Main Menu
async def main_menu(chat_id: int):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Record Headache", callback_data="record")],
        [InlineKeyboardButton(text="Export Report in PDF", callback_data="export")]
    ])
    await bot.send_message(chat_id, "Choose an option:", reply_markup=keyboard)

# Start command
@router.message(Command("start"))
async def start_handler(message: Message):
    await message.answer("Hello! I'm your headache tracking bot.")
    await main_menu(message.chat.id)

# Recording Headache parameters
@router.callback_query(F.data == "record")
async def start_recording(callback: CallbackQuery):
    user_data[callback.from_user.id] = {}
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Today", callback_data="day_today")],
        [InlineKeyboardButton(text="Yesterday", callback_data="day_yesterday")]
    ])
    await callback.message.answer("Which day?", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "day_today")
async def set_day_today(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data[user_id]['date'] = datetime.now().strftime("%Y-%m-%d")
    await ask_start_time(callback.message)

@router.callback_query(F.data == "day_yesterday")
async def set_day_yesterday(callback: CallbackQuery):
    user_id = callback.from_user.id
    yesterday = datetime.now() - timedelta(days=1)
    user_data[user_id]['date'] = yesterday.strftime("%Y-%m-%d")
    await ask_start_time(callback.message)

async def ask_start_time(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Now", callback_data="start_time_now")],
        [InlineKeyboardButton(text="Enter Time", callback_data="start_time_specify")]
    ])
    await message.answer("When did it start?", reply_markup=keyboard)

@router.callback_query(F.data == "start_time_now")
async def save_start_time_now(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data[user_id]['start_time'] = datetime.now().strftime("%H:%M")
    await ask_medication(callback.message)

@router.callback_query(F.data == "start_time_specify")
async def ask_start_time_specify(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data[user_id]['waiting_for_specific_start_time'] = True
    await callback.message.answer("Please enter the start time in HH:MM format.")
    await callback.answer()

# Ask for medication
async def ask_medication(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Yes", callback_data="medication_yes")],
        [InlineKeyboardButton(text="No", callback_data="medication_no")]
    ])
    await message.answer("Did you take medication?", reply_markup=keyboard)

@router.callback_query(F.data.startswith("medication_"))
async def handle_medication(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data[user_id]['medications'] = []
    if callback.data == "medication_yes":
        user_data[user_id]['waiting_for_medication_name'] = True
        await ask_medication_name(callback.message)
    else:
        await ask_rating(callback.message)

# Ask for name of medication
async def ask_medication_name(message: Message):
    await message.answer("Please enter the name of the medication you took:")

# Ask for time of medication
async def ask_medication_time(message: Message):
    await message.answer("Please enter the time you took this medication (e.g., 14:30):")

# Add another medication
@router.callback_query(F.data == "add_another")
async def add_another(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data[user_id]['waiting_for_medication_name'] = True
    await ask_medication_name(callback.message)

# Finish adding medications
@router.callback_query(F.data == "done_adding")
async def done_adding(callback: CallbackQuery):
    await ask_rating(callback.message)

# Ask for pain rating
async def ask_rating(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=str(i), callback_data=f"rating_{i}")] for i in range(1, 11)
    ])
    await message.answer("Rate your pain from 1 (low) to 10 (high)", reply_markup=keyboard)

@router.callback_query(F.data.startswith("rating_"))
async def save_rating(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data[user_id]['rating'] = int(callback.data.split("_")[1])
    await ask_stop_time(callback.message)

# Ask for stop time
async def ask_stop_time(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Now", callback_data="stop_time_now")],
        [InlineKeyboardButton(text="Enter Time", callback_data="stop_time_specify")]
    ])
    await message.answer("When did the headache stop?", reply_markup=keyboard)

@router.callback_query(F.data == "stop_time_now")
async def save_stop_time_now(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data[user_id]['stop_time'] = datetime.now().strftime("%H:%M")
    user_data[user_id]['waiting_for_comments'] = True
    await ask_comments(callback.message)

@router.callback_query(F.data == "stop_time_specify")
async def ask_stop_time_specify(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_data[user_id]['waiting_for_specific_stop_time'] = True
    await callback.message.answer("Please enter the stop time in HH:MM format.")
    await callback.answer()

# Ask for additional comments
async def ask_comments(message: Message):
    await message.answer("Any additional comments?")

@router.message(Command("reset"))
async def reset_progress(message: Message):
    user_id = message.from_user.id
    if user_id in user_data:
        del user_data[user_id]
        await message.answer("Your progress has been reset.")
    else:
        await message.answer("No active headache tracking session to reset.")
    await main_menu(message.chat.id)

async def delete_user_data(user_id: int):
    if user_id in user_data:
        del user_data[user_id]
    await main_menu(user_id)

@router.message()
async def handle_text_input(message: Message):
    user_id = message.from_user.id

    if user_id in user_data:
        # if 'start_time' not in user_data[user_id]:
        if user_data[user_id].get('waiting_for_specific_start_time', False):
            try:
                # Validate start time format
                datetime.strptime(message.text, "%H:%M")
                user_data[user_id]['start_time'] = message.text
                user_data[user_id]['waiting_for_specific_start_time'] = False
                await ask_medication(message)
            except ValueError:
                await message.answer("Invalid format. Please enter time as HH:MM (e.g., 14:30).")

        elif user_data[user_id].get('waiting_for_specific_stop_time', False):
            try:
                # Validate stop time format
                datetime.strptime(message.text, "%H:%M")
                user_data[user_id]['stop_time'] = message.text
                user_data[user_id]['waiting_for_specific_stop_time'] = False
                user_data[user_id]['waiting_for_comments'] = True
                await ask_comments(message)
            except ValueError:
                await message.answer("Invalid format. Please enter time as HH:MM (e.g., 14:30).")

        elif user_data[user_id].get('waiting_for_comments', False):
            user_data[user_id]['comments'] = message.text
            user_data[user_id]['waiting_for_comments'] = False
            await save_to_db(message)

        # If the medication name was being input
        elif user_data[user_id].get('waiting_for_medication_name', False):
            medication_name = message.text
            user_data[user_id]['medications'].append({'name': medication_name})
            user_data[user_id]['waiting_for_medication_name'] = False
            user_data[user_id]['waiting_for_medication_time'] = True
            await ask_medication_time(message)

        elif user_data[user_id].get('waiting_for_medication_time', False):
            # Validate and save the medication time
            try:
                medication_time = datetime.strptime(message.text, "%H:%M").strftime("%H:%M")
                last_medication = user_data[user_id]['medications'][-1]
                last_medication['time'] = medication_time
                user_data[user_id]['waiting_for_medication_time'] = False
                await message.answer(f"Added {last_medication['name']} at {medication_time}.")

                # Ask if user wants to add another medication
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Yes, add another", callback_data="add_another")],
                    [InlineKeyboardButton(text="No, I'm done", callback_data="done_adding")]
                ])
                await message.answer(f"Would you like to add another medication?", reply_markup=keyboard)
            except ValueError:
                await message.answer("Invalid format. Please enter time as HH:MM (e.g., 14:30).")

# Save to database
async def save_to_db(message: Message):
    user_id = message.from_user.id
    data = user_data.pop(user_id, None)

    if data and "stop_time" in data:  # Only save if stop time is provided
        # medications = "; ".join([f"{med['name']} at {med['time']}" for med in data['medications']])
        medications = "; ".join([
            f"{med['name']} at {med['time']}" for med in data['medications']
        ])
        if not medications:
            medications = "No medications taken"

        cursor.execute(
            "INSERT INTO headaches (date, start_time, stop_time, medications, rating, comments) VALUES (?, ?, ?, ?, ?, ?)",
            (
            data['date'], data['start_time'], data['stop_time'], medications, data['rating'], data.get('comments', '')))
        conn.commit()
        await message.answer("Your headache record has been saved.")
    else:
        await message.answer("Error saving data. Please make sure you entered all required details.")
    await main_menu(message.chat.id)

# Exporting to PDF
@router.callback_query(F.data == "export")
async def handle_export(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Last Week", callback_data="export_week")],
        [InlineKeyboardButton(text="Last Month", callback_data="export_month")]
    ])
    await callback.message.answer("Choose report period:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "export_week")
async def export_week(callback: CallbackQuery):
    await export_pdf(callback, period="week")
    await callback.answer()

@router.callback_query(F.data == "export_month")
async def export_month(callback: CallbackQuery):
    await export_pdf(callback, period="month")
    await callback.answer()

async def generate_headache_report(records, period):
    """Generates a PDF headache report with dynamic column widths and row heights."""

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Title
    title = f"Headache Report (Last {period.capitalize()})"
    pdf.cell(200, 10, title, ln=True, align='C')
    pdf.ln(10)

    # Headers
    headers = ["#", "Date", "Start Time", "Stop Time", "Medications", "Rating", "Comments"]

    # Calculate max column widths
    max_widths = calculate_column_widths(records, headers, pdf)

    # Draw table headers
    for header in headers:
        pdf.cell(max_widths[header], 10, header, border=1, align='C')
    pdf.ln()

    # Draw table rows
    for idx, record in enumerate(records, start=1):
        draw_table_row(pdf, idx, record, headers, max_widths)

    filename = "headache_report.pdf"
    pdf.output(filename)
    return filename


def calculate_column_widths(records, headers, pdf):
    """Calculate the maximum column widths based on headers and data."""
    temp_pdf = FPDF()
    temp_pdf.set_font("Arial", size=12)

    max_widths = {header: temp_pdf.get_string_width(header) + 6 for header in headers}

    for record in records:
        for header, value in zip(headers[1:], record):  # Excluding the index column
            if value is not None:
                text = str(value)
                if header in ["Medications", "Comments"]:
                    # Simulate multi_cell line wrapping
                    lines = split_text_into_lines(text, max_widths[header] - 4, temp_pdf)
                    width = max(temp_pdf.get_string_width(line) + 4 for line in lines)
                else:
                    width = temp_pdf.get_string_width(text) + 4

                max_widths[header] = max(max_widths[header], width)

    return max_widths

def draw_table_row(pdf, idx, record, headers, max_widths):
    """Draws a single row in the table, adjusting for multiline text fields."""
    y_start = pdf.get_y()

    # Determine row height dynamically
    row_height = max(10, calculate_row_height(pdf, record, headers, max_widths))

    # Index column
    pdf.cell(max_widths["#"], row_height, str(idx), border=1, align='C')

    # Other columns
    for header, value in zip(headers[1:], record):  # Skip index column
        x_position = pdf.get_x()
        text = str(value) if value is not None else ""

        if header in ["Medications", "Comments"]:
            # For Medications and Comments, use multi_cell for dynamic text wrapping
            pdf.multi_cell(max_widths[header], 5, text, border=1, align='L')
            pdf.set_xy(x_position + max_widths[header], y_start)  # Reset position
        else:
            pdf.cell(max_widths[header], row_height, text, border=1, align='C')

    pdf.ln(row_height)


def calculate_row_height(pdf, record, headers, max_widths):
    """Determines the required row height based on multiline text fields."""
    line_counts = [
        len(split_text_into_lines(str(value), max_widths[header] - 4, pdf))
        if header in ["Medications", "Comments"] and isinstance(value, str) else 1
        for header, value in zip(headers[1:], record)
    ]
    return max(line_counts) * 5  # 5 is the line height

def split_text_into_lines(text, max_width, pdf):
    """Splits text into lines based on the max width for a column."""
    words = text.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip()
        if pdf.get_string_width(test_line) > max_width:
            lines.append(current_line)
            current_line = word
        else:
            current_line = test_line

    if current_line:
        lines.append(current_line)

    return lines

async def export_pdf(callback: CallbackQuery, period: str):
    today = datetime.now()
    if period == "week":
        start_date = today - timedelta(weeks=1)
    elif period == "month":
        start_date = today - timedelta(days=30)

    start_date_str = start_date.strftime("%Y-%m-%d")

    cursor.execute(
        "SELECT date, start_time, stop_time, medications, rating, comments FROM headaches WHERE date >= ?",
        (start_date_str,)
    )
    records = cursor.fetchall()
    if not records:
        await bot.send_message(callback.from_user.id, f"No records for the last {period}.")
        return

    filename = await generate_headache_report(records, period)

    input_file = FSInputFile(filename, filename=filename)
    await bot.send_document(callback.from_user.id, input_file)
    os.remove(filename)
    await callback.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
