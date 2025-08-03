import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from database import SessionLocal, User
from config import ADMIN_ID

logger = logging.getLogger(__name__)

# State definition for the conversation
AWAIT_REPORT_REASON = range(1)

async def start_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the report conversation by asking for a reason."""
    query = update.callback_query
    await query.answer()

    # The user ID to be reported is stored in the callback_data
    reported_user_id = int(query.data.split('_')[-1])
    context.user_data['reported_user_id'] = reported_user_id
    
    await query.edit_message_text(
        text="You are about to report this user. Please provide a clear and detailed reason for your report.\n\nType /cancel to abort."
    )
    return AWAIT_REPORT_REASON

async def submit_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Submits the report to the admin and confirms with the user."""
    report_reason = update.message.text
    reporter_user = update.effective_user
    reported_user_id = context.user_data.get('reported_user_id')

    db_session = SessionLocal()
    try:
        reported_user = db_session.query(User).filter(User.id == reported_user_id).first()
        if not reported_user:
            await update.message.reply_text("Could not find the user you are trying to report.")
            return ConversationHandler.END

        # Format the report message for the admin
        admin_notification = (
            f"**New User Report**\n\n"
            f"**Reporter:** {reporter_user.first_name} (@{reporter_user.username})\n"
            f"**Reporter TG ID:** `{reporter_user.id}`\n\n"
            f"**Reported User:** {reported_user.first_name} (@{reported_user.username})\n"
            f"**Reported User TG ID:** `{reported_user.telegram_id}`\n\n"
            f"**Reason:**\n{report_reason}"
        )
        
        # Send the report to the admin
        await context.bot.send_message(
            chat_id=ADMIN_ID, 
            text=admin_notification, 
            parse_mode='Markdown'
        )

        await update.message.reply_text("Thank you. Your report has been submitted and will be reviewed by an administrator.")

    finally:
        db_session.close()
        context.user_data.pop('reported_user_id', None)

    return ConversationHandler.END

async def cancel_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the report process."""
    context.user_data.pop('reported_user_id', None)
    await update.message.reply_text("Report cancelled.")
    return ConversationHandler.END

