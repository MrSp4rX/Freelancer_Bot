import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import SessionLocal, Job, User, Skill

logger = logging.getLogger(__name__)

async def notify_matching_freelancers(context: ContextTypes.DEFAULT_TYPE, job: Job):
    """Finds and notifies freelancers whose skills match a new job posting."""
    
    db_session = SessionLocal()
    try:
        required_skill_ids = {skill.id for skill in job.skills_required}
        if not required_skill_ids:
            logger.info(f"Job {job.id} has no required skills. No notifications sent.")
            return

        # Find all users who are freelancers and have at least one of the required skills
        matching_freelancers = db_session.query(User).filter(
            User.role == 'freelancer',
            User.skills.any(Skill.id.in_(required_skill_ids))
        ).all()
        
        if not matching_freelancers:
            logger.info(f"No freelancers found with matching skills for job {job.id}.")
            return

        notification_text = (
            f"?? **New Job Alert!**\n\n"
            f"A new job matching your skills has been posted:\n\n"
            f"?? **{job.title}**\n"
            f"?? Budget: ${job.budget:,.2f}"
        )
        # In matching.py
        keyboard = [[InlineKeyboardButton("?? View Job & Apply", callback_data=f"view_specific_job_{job.id}")]]


        sent_count = 0
        for freelancer in matching_freelancers:
            try:
                await context.bot.send_message(
                    chat_id=freelancer.telegram_id,
                    text=notification_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send notification to {freelancer.telegram_id} for job {job.id}: {e}")
        
        logger.info(f"Sent {sent_count} notifications for job {job.id}.")

    finally:
        db_session.close()


