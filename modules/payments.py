import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import SessionLocal, Job
from . import matching
from config import ADMIN_ID

logger = logging.getLogger(__name__)

async def handle_deposit_sent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Notifies the admin that a user has marked a deposit as sent."""
    query = update.callback_query
    await query.answer()
    tx_id = int(query.data.split('_')[-1])
    await query.edit_message_text("Thank you. Your deposit is pending confirmation from an administrator. You will be notified once it is approved.")
    keyboard = [[InlineKeyboardButton("Confirm Deposit", callback_data=f"admin_confirm_deposit_{tx_id}")]]
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"User {query.from_user.first_name} (`{query.from_user.id}`) has marked deposit transaction `{tx_id}` as sent. Please verify and confirm.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_deposit_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the user a placeholder message with a payment button."""
    query = update.callback_query
    await query.answer()
    job_id = int(query.data.split('_')[-1])
    payment_address = "YOUR_TEST_CRYPTO_ADDRESS"
    network = "TRC20"

    text = (
        f"To post your job, please send the required deposit to the following address:\n\n"
        f"**Address:** `{payment_address}`\n"
        f"**Network:** `{network}`\n\n"
        f"⚠️ This is for testing only. Once you click the button below, the payment will be automatically confirmed."
    )
    
    keyboard = [[InlineKeyboardButton("✅ I Have Sent The Payment", callback_data=f"payment_sent_{job_id}")]]
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


# This is the new function for auto-confirming the payment
async def auto_confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Automatically confirms payment for testing, changes job status to 'open',
    and notifies matching freelancers.
    """
    query = update.callback_query
    await query.answer()
    job_id = int(query.data.split('_')[-1])

    db_session = SessionLocal()
    try:
        job = db_session.query(Job).filter(Job.id == job_id).first()
        if job and job.status == 'pending_deposit':
            job.status = 'open'
            db_session.commit()
            
            await query.edit_message_text("✅ Payment confirmed! Your job is now live and freelancers are being notified.")
            logger.info(f"Auto-confirmed payment for Job ID {job.id}. Job is now open.")
            
            # Notify matching freelancers that the job is now available
            await matching.notify_matching_freelancers(context, job)
            
        else:
            await query.edit_message_text("This job is not awaiting payment or could not be found.")
            logger.warning(f"Attempted to auto-confirm payment for non-pending job ID {job_id}.")

    except Exception as e:
        logger.error(f"An error occurred during auto-confirmation for job {job_id}: {e}")
        await query.edit_message_text("An error occurred. Please contact support.")
    finally:
        db_session.close()

# These functions would be used in a production environment with manual admin checks.
# They are not needed for the current testing setup but are included for completeness.

async def payment_sent_placeholder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Notifies admin that a payment has been marked as sent by a user."""
    # This function is no longer used in the main testing flow.
    pass

async def admin_confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allows an admin to manually confirm a payment and post a job."""
    # This function is no longer used in the main testing flow.
    pass
