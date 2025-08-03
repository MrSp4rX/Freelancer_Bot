from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# --- Main Menu ---
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends the main menu with role selection buttons."""
    keyboard = [
        [InlineKeyboardButton("?? I'm a Client", callback_data='role_select_client')],
        [InlineKeyboardButton("??‍?? I'm a Freelancer", callback_data='role_select_freelancer')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Welcome to the Freelancer Hub! ??\n\n"
        "Are you here to hire talent or to find work?",
        reply_markup=reply_markup
    )

