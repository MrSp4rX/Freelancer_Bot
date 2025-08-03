import logging
from telegram import *
from telegram.ext import *

from database import *
from config import *

logger = logging.getLogger(__name__)

# State definition
CHATTING = range(1)

async def start_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts a chat session. Can be job-specific or general."""
    query = update.callback_query
    await query.answer()
    parts = query.data.split('_')
    try:
        recipient_id = int(parts[1])
        job_id = int(parts[2]) if len(parts) > 2 else None
    except (ValueError, IndexError):
        await query.edit_message_text("Could not start chat due to an error.")
        return ConversationHandler.END

    context.user_data['chat_recipient_id'] = recipient_id
    context.user_data['chat_job_id'] = job_id
    chat_topic = "the relevant job"
    if job_id:
        db_session = SessionLocal()
        try:
            job = db_session.query(Job).filter(Job.id == job_id).first()
            if job:
                chat_topic = f"job '{job.title}'"
        finally:
            db_session.close()
    else:
        chat_topic = "an admin matter"

    await query.edit_message_text(
        f"You are now in a private chat regarding {chat_topic}.\n\n"
        "Your identity is hidden. All messages you send will be forwarded.\n"
        "Type /endchat to leave the conversation."
    )
    return CHATTING

async def relay_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Copies message content and relays it anonymously.
    If the recipient is the admin, it adds a 'Reply' button.
    """
    recipient_id = context.user_data.get('chat_recipient_id')
    sender_id = update.effective_user.id
    if not recipient_id:
        await update.message.reply_text("Your chat session has expired. Please start a new one.")
        return ConversationHandler.END

    message = update.effective_message
    reply_markup = None
    if recipient_id == int(ADMIN_ID):
        reply_button = InlineKeyboardButton("Reply to User", callback_data=f"chat_{sender_id}")
        reply_markup = InlineKeyboardMarkup([[reply_button]])
    try:
        if message.text:
            await context.bot.send_message(chat_id=recipient_id, text=message.text, reply_markup=reply_markup)
        elif message.photo:
            await context.bot.send_photo(chat_id=recipient_id, photo=message.photo[-1].file_id, caption=message.caption, reply_markup=reply_markup)
        elif message.document:
            await context.bot.send_document(chat_id=recipient_id, document=message.document.file_id, caption=message.caption, reply_markup=reply_markup)
        else:
            await message.forward(chat_id=recipient_id)
            if reply_markup:
                 await context.bot.send_message(chat_id=recipient_id, text="Click below to reply.", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Failed to relay message content to {recipient_id}: {e}")
        await update.message.reply_text("Your message could not be sent.")
    return CHATTING

async def end_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ends the chat session."""
    context.user_data.pop('chat_recipient_id', None)
    context.user_data.pop('chat_job_id', None)
    
    await update.message.reply_text(
        "You have left the chat. Your messages will no longer be forwarded."
    )
    return ConversationHandler.END

AWAIT_JOB_ID, CHATTING = range(2)

async def prompt_for_job_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the user for a Job ID to start a chat."""
    query = update.callback_query
    await query.answer()

    # Store who is initiating the chat (client or freelancer)
    role = query.data.split('_')[-1]
    context.user_data['chat_initiator_role'] = role

    await query.edit_message_text("Please enter the Job ID you would like to discuss.")
    return AWAIT_JOB_ID


async def receive_job_id_and_start_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives a Job ID and initiates a chat if validation passes."""
    try:
        job_id = int(update.message.text)
    except ValueError:
        await update.message.reply_text("That is not a valid ID. Please enter a numeric Job ID.")
        return AWAIT_JOB_ID

    user_id = update.effective_user.id
    initiator_role = context.user_data.get('chat_initiator_role')
    db_session = SessionLocal()
    try:
        job = db_session.query(Job).filter(Job.id == job_id).first()
        if not job:
            await update.message.reply_text("No job found with that ID. Please check the ID and try again.")
            return AWAIT_JOB_ID

        recipient_user = None
        # If the client is starting the chat
        if initiator_role == 'client' and job.client.telegram_id == user_id:
            if job.hired_freelancer:
                recipient_user = job.hired_freelancer
            else:
                await update.message.reply_text("This job does not have a freelancer assigned to it yet.")
                return ConversationHandler.END
        
        # If the freelancer is starting the chat
        elif initiator_role == 'freelancer' and job.hired_freelancer and job.hired_freelancer.telegram_id == user_id:
            recipient_user = job.client
        
        else:
            await update.message.reply_text("You do not have permission to access the chat for this job.")
            return ConversationHandler.END

        # If we found a valid recipient, start the chat
        context.user_data['chat_recipient_id'] = recipient_user.telegram_id
        context.user_data['chat_job_id'] = job.id

        # Notify the recipient that someone wants to chat
        await context.bot.send_message(
            chat_id=recipient_user.telegram_id,
            text=f"A user is online to chat about the job: '{job.title}'."
        )

        # Confirm chat start for the initiator
        await update.message.reply_text(
            f"You are now in a private chat regarding '{job.title}'.\n\n"
            "Type /endchat to leave the conversation."
        )
        return CHATTING

    finally:
        db_session.close()

async def cancel_chat_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the process of setting up a chat."""
    context.user_data.pop('chat_initiator_role', None)
    await update.message.reply_text("Chat setup cancelled.")
    return ConversationHandler.END

