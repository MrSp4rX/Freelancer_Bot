# To be placed in: freelancer_bot/modules/client_flow.py

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler
from sqlalchemy import func

from database import SessionLocal, Job, User, Application, Review, Skill
from . import matching

TITLE, DESCRIPTION, BUDGET, CURRENCY, CATEGORY, SKILLS = range(6)
RATING, COMMENT = range(6,8)

logger = logging.getLogger(__name__)

def get_client_dashboard_markup() -> InlineKeyboardMarkup:
    """Creates the main client dashboard keyboard."""
    keyboard = [
        [InlineKeyboardButton("?? Post a New Job", callback_data='client_post_job')],
        [InlineKeyboardButton("⏳ Active Projects", callback_data='client_active_projects')],
        [InlineKeyboardButton("?? View Proposals", callback_data='client_view_proposals')],
        [InlineKeyboardButton("✅ Completed Jobs", callback_data='client_completed_jobs')],
        [InlineKeyboardButton("?? Billing & Payments", callback_data='client_billing')],
    ]
    return InlineKeyboardMarkup(keyboard)

async def show_client_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the main client dashboard."""
    user_name = update.effective_user.first_name
    text = f" CLIENT CONTROL CENTER\nWelcome, {user_name}!"
    markup = get_client_dashboard_markup()
    if update.callback_query:
        await update.callback_query.edit_message_text(text=text, reply_markup=markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode='Markdown')

async def client_button_placeholder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """A placeholder for features that are not yet implemented."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text=f"This feature (`{query.data}`) is under construction.\n\n"
             "Press the button below to return to your dashboard.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="back_to_client_dashboard")]])
    )

# --- PROPOSAL & HIRING FLOW ---

async def select_job_to_view_proposals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows a client their open jobs so they can select one to view proposals for."""
    query = update.callback_query
    await query.answer()
    db_session = SessionLocal()
    try:
        user = db_session.query(User).filter(User.telegram_id == query.from_user.id).first()
        client_jobs = db_session.query(Job).filter(Job.client_id == user.id, Job.status == 'open').all()
        if not client_jobs:
            await query.edit_message_text("You have no open jobs with active proposals right now.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_client_dashboard")]]))
            return
        keyboard = [[InlineKeyboardButton(f"{job.title} ({len(job.applications)} proposals)", callback_data=f"view_proposals_{job.id}_0")] for job in client_jobs]
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_client_dashboard")])
        await query.edit_message_text("Please select a job to view its proposals:", reply_markup=InlineKeyboardMarkup(keyboard))
    finally:
        db_session.close()

async def view_proposals_for_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays proposals for a specific job, with pagination."""
    query = update.callback_query
    await query.answer()
    _, _, job_id_str, index_str = query.data.split('_')
    job_id = int(job_id_str)
    current_index = int(index_str)

    db_session = SessionLocal()
    try:
        applications = db_session.query(Application).filter(Application.job_id == job_id).all()
        if not applications:
            await query.edit_message_text(
                "There are no proposals for this job yet.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Job List", callback_data="client_view_proposals")]])
            )
            return
        
        app = applications[current_index]
        proposal_text = (
            f"**Proposal for: {app.job.title}**\n\n"
            f"**From Freelancer:** {app.freelancer.first_name} (@{app.freelancer.username})\n"
            f"**Bid Amount:** ${app.bid_amount:,.2f} USD\n\n"
            f"**Message:**\n{app.proposal_text}"
        )

        keyboard = []
        nav_row = []
        if current_index > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"view_proposals_{job_id}_{current_index - 1}"))
        if current_index < len(applications) - 1:
            nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"view_proposals_{job_id}_{current_index + 1}"))
        keyboard.append(nav_row)
        
        keyboard.append([InlineKeyboardButton("?? View Freelancer's Profile", callback_data=f"view_profile_{app.freelancer.id}_{job_id}_{current_index}")])
        keyboard.append([
            InlineKeyboardButton("✅ Accept", callback_data=f"accept_app_{app.id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_app_{app.id}")
        ])
        keyboard.append([InlineKeyboardButton("⬅️ Back to Job List", callback_data="client_view_proposals")])
        
        await query.edit_message_text(text=proposal_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    finally:
        db_session.close()

async def show_public_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays a freelancer's public profile to a client."""
    query = update.callback_query
    await query.answer()
    _, _, freelancer_id_str, job_id_str, index_str = query.data.split('_')
    freelancer_id = int(freelancer_id_str)

    db_session = SessionLocal()
    try:
        freelancer = db_session.query(User).filter(User.id == freelancer_id).first()
        if not freelancer:
            await query.edit_message_text("Error: Freelancer profile not found.")
            return

        avg_rating, num_reviews = db_session.query(func.avg(Review.rating), func.count(Review.id)).filter(Review.reviewee_id == freelancer.id).first()
        completed_jobs = db_session.query(Job).filter(Job.hired_freelancer_id == freelancer.id, Job.status == 'completed').count()
        rating_str = f"{avg_rating:.2f} ⭐ out of {num_reviews} reviews" if num_reviews > 0 else "No reviews yet"

        profile_text = (
            f"**Freelancer Profile**\n\n"
            f"**Name:** {freelancer.first_name}\n"
            f"**Bio:** {freelancer.bio or 'No bio set.'}\n\n"
            f"**Reputation:**\n"
            f"- **Average Rating:** {rating_str}\n"
            f"- **Jobs Completed:** {completed_jobs}"
        )
        
        keyboard = [[InlineKeyboardButton("⬅️ Back to Proposal", callback_data=f"view_proposals_{job_id_str}_{index_str}")]]
        await query.edit_message_text(text=profile_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    finally:
        db_session.close()

async def accept_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Accepts a freelancer's application, hires them, and rejects other applicants."""
    query = update.callback_query
    await query.answer()
    application_id = int(query.data.split('_')[-1])
    db_session = SessionLocal()
    try:
        accepted_app = db_session.query(Application).filter(Application.id == application_id).first()
        if not accepted_app or accepted_app.job.status != 'open':
            await query.edit_message_text("This job is no longer available.")
            return

        job = accepted_app.job
        job.status = 'in_progress'
        job.hired_freelancer_id = accepted_app.freelancer_id
        accepted_app.status = 'accepted'
        
        # Notify other applicants
        other_apps = db_session.query(Application).filter(Application.job_id == job.id, Application.id != accepted_app.id).all()
        for app in other_apps:
            app.status = 'rejected'
            try:
                await context.bot.send_message(chat_id=app.freelancer.telegram_id, text=f"Unfortunately, your application for '{job.title}' was not selected.")
            except Exception as e:
                logger.error(f"Failed to send rejection to {app.freelancer.telegram_id}: {e}")
        
        db_session.commit()
        
        # Notify the hired freelancer
        try:
            await context.bot.send_message(chat_id=accepted_app.freelancer.telegram_id, text=f"?? Congratulations! Your application for '{job.title}' has been accepted!")
        except Exception as e:
            logger.error(f"Failed to send acceptance to {accepted_app.freelancer.telegram_id}: {e}")
        
        await query.edit_message_text(f"✅ You have hired {accepted_app.freelancer.first_name} for **{job.title}**.")
    finally:
        db_session.close()

async def reject_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Rejects a single freelancer's application."""
    query = update.callback_query
    await query.answer()
    application_id = int(query.data.split('_')[-1])
    db_session = SessionLocal()
    try:
        app_to_reject = db_session.query(Application).filter(Application.id == application_id).first()
        if not app_to_reject:
            await query.edit_message_text("Application not found.")
            return

        app_to_reject.status = 'rejected'
        db_session.commit()

        try:
            await context.bot.send_message(chat_id=app_to_reject.freelancer.telegram_id, text=f"Your application for '{app_to_reject.job.title}' was not selected at this time.")
        except Exception as e:
            logger.error(f"Failed to send rejection to {app_to_reject.freelancer.telegram_id}: {e}")
        
        await query.edit_message_text(f"You have rejected the application from {app_to_reject.freelancer.first_name}.")
    finally:
        db_session.close()


# --- JOB POSTING CONVERSATION ---

async def ask_for_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gets all skill categories from DB and asks the user to choose one."""
    query = update.callback_query
    await query.answer()
    db_session = SessionLocal()
    try:
        # Get distinct, non-null categories
        categories = db_session.query(Skill.category).filter(Skill.category.isnot(None)).distinct().all()
        if not categories:
            await query.edit_message_text("No skill categories found. Please contact an admin.")
            return ConversationHandler.END

        keyboard = [[InlineKeyboardButton(cat[0], callback_data=f"job_cat_{cat[0]}")] for cat in categories]
        await query.edit_message_text(
            "Great. Now, please select a category for this job:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CATEGORY
    finally:
        db_session.close()

async def received_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the chosen category and moves to skill selection."""
    query = update.callback_query
    await query.answer()

    chosen_category = query.data.split('job_cat_')[-1]
    context.user_data['job_category'] = chosen_category

    # Now show the skills menu, filtered by the chosen category
    await edit_job_skills(update, context)
    return SKILLS


async def post_job_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the job posting conversation."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Let's post a job. First, what is the **job title**?\n\nType /cancel to stop.", parse_mode='Markdown')
    return TITLE

async def received_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the job title and asks for the description."""
    context.user_data['title'] = update.message.text
    await update.message.reply_text("Got it. Now, please provide a detailed **description**.", parse_mode='Markdown')
    return DESCRIPTION

async def received_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the description and asks for the budget."""
    context.user_data['description'] = update.message.text
    await update.message.reply_text("Excellent. What is the **total budget** in USD? (e.g., 500)", parse_mode='Markdown')
    return BUDGET

async def received_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the budget and asks for the deposit currency."""
    try:
        context.user_data['budget'] = float(update.message.text)
    except ValueError:
        await update.message.reply_text("Invalid number. Please enter the budget again.")
        return BUDGET
    
    keyboard = [
        [InlineKeyboardButton("USDT (TRC20)", callback_data='currency_USDT.TRC20')],
        [InlineKeyboardButton("Bitcoin (BTC)", callback_data='currency_BTC')]
    ]
    await update.message.reply_text("Which cryptocurrency for the deposit?", reply_markup=InlineKeyboardMarkup(keyboard))
    return CURRENCY

async def received_currency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves currency selection and transitions to category selection."""
    query = update.callback_query
    await query.answer()
    context.user_data['currency'] = query.data.split('_')[1]

    # Initialize an empty set for skills in context
    context.user_data['job_skills'] = set()

    await ask_for_category(update, context)
    return CATEGORY


async def edit_job_skills(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows a paginated menu of skills filtered by category."""
    query = update.callback_query

    page = 0
    if query:
        await query.answer()
        try:
            page = int(query.data.split('_')[-1])
        except (ValueError, IndexError):
            page = 0

    skills_per_page = 7
    offset = page * skills_per_page
    db_session = SessionLocal()
    try:
        chosen_category = context.user_data.get('job_category')
        skill_query = db_session.query(Skill).filter(Skill.category == chosen_category)

        total_skills = skill_query.count()
        all_skills = skill_query.limit(skills_per_page).offset(offset).all()

        selected_skill_ids = context.user_data.get('job_skills', set())

        keyboard = []
        for skill in all_skills:
            text = f"✅ {skill.name}" if skill.id in selected_skill_ids else skill.name
            keyboard.append([InlineKeyboardButton(text, callback_data=f"job_toggle_skill_{skill.id}_{page}")])

        nav_row = []
        if page > 0: nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"job_edit_skills_{page - 1}"))
        if (page + 1) * skills_per_page < total_skills: nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"job_edit_skills_{page + 1}"))
        if nav_row: keyboard.append(nav_row)

        keyboard.append([InlineKeyboardButton("✅ Done Adding Skills", callback_data="job_skills_done")])

        text = f"Please select the skills required for this job (Category: {chosen_category}):"
        if query: await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else: await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    finally:
        db_session.close()



async def toggle_job_skill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Adds or removes a skill from the job being created."""
    query = update.callback_query
    _, _, skill_id_str, page_str = query.data.split('_')
    skill_id = int(skill_id_str)
    
    selected_skills = context.user_data.get('job_skills', set())
    if skill_id in selected_skills:
        selected_skills.remove(skill_id)
    else:
        selected_skills.add(skill_id)
    context.user_data['job_skills'] = selected_skills
    
    await edit_job_skills(update, context)

async def received_skills(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Final step: Saves the job with skills and ends the conversation."""
    query = update.callback_query
    await query.answer()
    
    title = context.user_data['title']
    description = context.user_data['description']
    budget = context.user_data['budget']
    chosen_currency = context.user_data['currency']
    skill_ids = context.user_data['job_skills']

    db_session = SessionLocal()
    try:
        user = db_session.query(User).filter(User.telegram_id==update.effective_user.id).first()
        new_job = Job(title=title, description=description, budget=budget, currency=chosen_currency, client_id=user.id)
        
        if skill_ids:
            skills_to_add = db_session.query(Skill).filter(Skill.id.in_(skill_ids)).all()
            new_job.skills_required.extend(skills_to_add)

        db_session.add(new_job)
        db_session.commit()
        
        escrow_amount = budget * 0.75
        confirmation_text = (
             f"✅ **Job Draft Created!**\n\n"
             f"**Title:** {title}\n"
             f"**Skills:** {', '.join([s.name for s in new_job.skills_required]) or 'None specified'}\n"
             f"**Budget:** ${budget:,.2f} USD\n\n"
             f"**Amount to Deposit:** ${escrow_amount:,.2f} USD"
        )
        keyboard = [[InlineKeyboardButton("Proceed to Deposit", callback_data=f'deposit_{new_job.id}')]]
        await query.edit_message_text(text=confirmation_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    finally:
        db_session.close()

    context.user_data.clear()
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the current conversation (job posting or review)."""
    await update.message.reply_text("Action cancelled.")
    context.user_data.clear()
    await show_client_dashboard(update, context) # Return to dashboard
    return ConversationHandler.END


# --- JOB COMPLETION & REVIEW FLOW ---

async def view_active_projects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the client their projects that are in progress or awaiting completion confirmation."""
    query = update.callback_query
    await query.answer()
    db_session = SessionLocal()
    try:
        client = db_session.query(User).filter(User.telegram_id == query.from_user.id).first()
        active_jobs = db_session.query(Job).filter(Job.client_id == client.id, Job.status.in_(['in_progress', 'pending_completion'])).all()
        
        if not active_jobs:
            await query.edit_message_text("You have no active projects.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_client_dashboard")]]))
            return

        keyboard = []
        for job in active_jobs:
            button_text = f"{job.title} ({job.status})"
            if job.status == 'pending_completion':
                keyboard.append([InlineKeyboardButton(f"➡️ {button_text}", callback_data=f"confirm_complete_{job.id}")])
            else:
                keyboard.append([InlineKeyboardButton(button_text, callback_data="none")])
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_client_dashboard")])
        
        await query.edit_message_text("Your active projects. Select a job awaiting your confirmation:", reply_markup=InlineKeyboardMarkup(keyboard))
    finally:
        db_session.close()

async def show_completed_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the client a list of their completed jobs."""
    query = update.callback_query
    await query.answer()
    db_session = SessionLocal()
    try:
        client = db_session.query(User).filter(User.telegram_id == query.from_user.id).first()
        completed_jobs = db_session.query(Job).filter(Job.client_id == client.id, Job.status == 'completed').order_by(Job.created_at.desc()).all()

        if not completed_jobs:
            await query.edit_message_text("You have no completed jobs.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_client_dashboard")]]))
            return

        response_text = "**Your Completed Jobs**\n\n"
        for job in completed_jobs:
            response_text += f"✅ **{job.title}**\n"
            if job.hired_freelancer:
                response_text += f"   - Freelancer: {job.hired_freelancer.first_name}\n"
            response_text += f"   - Budget: ${job.budget:,.2f}\n\n"
            
        keyboard = [[InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="back_to_client_dashboard")]]
        await query.edit_message_text(text=response_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    finally:
        db_session.close()

async def confirm_completion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Marks a job as complete, simulates payment, and initiates the review process."""
    query = update.callback_query
    await query.answer()
    job_id = int(query.data.split('_')[-1])
    db_session = SessionLocal()
    try:
        job = db_session.query(Job).filter(Job.id == job_id).first()
        if job and job.status == 'pending_completion':
            job.status = 'completed'
            db_session.commit()
            
            logger.info(f"SIMULATING PAYMENT for Job ID: {job.id} to Freelancer ID: {job.hired_freelancer_id}")
            await context.bot.send_message(chat_id=job.hired_freelancer.telegram_id, text=f"✅ Payment Released! Client confirmed completion for '{job.title}'.")
            await query.edit_message_text(f"Project '{job.title}' is now complete. Payment released.")
            
            # Prompt both parties to review each other
            await prompt_for_review(context, job, reviewer=job.client, reviewee=job.hired_freelancer)
            await prompt_for_review(context, job, reviewer=job.hired_freelancer, reviewee=job.client)
        else:
            await query.edit_message_text("This action cannot be performed now.")
    finally:
        db_session.close()

async def prompt_for_review(context: ContextTypes.DEFAULT_TYPE, job: Job, reviewer: User, reviewee: User):
    """Sends a message to a user asking them to review the other party."""
    keyboard = [[InlineKeyboardButton("⭐" * i, callback_data=f"review_{job.id}_{reviewee.id}_{i}") for i in range(1, 6)]]
    await context.bot.send_message(
        chat_id=reviewer.telegram_id,
        text=f"Job '{job.title}' is complete! Please rate your experience with {reviewee.first_name}.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_rating_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles when a user clicks a star rating button."""
    query = update.callback_query
    await query.answer()
    _, job_id, reviewee_id, rating = query.data.split('_')
    context.user_data['review_data'] = {'job_id': int(job_id), 'reviewee_id': int(reviewee_id), 'rating': int(rating)}
    await query.edit_message_text("Thank you for the rating! Add an optional comment, or /skip.")
    return COMMENT

async def received_review_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves a review comment and ends the review conversation."""
    comment = update.message.text
    review_data = context.user_data.get('review_data')
    db_session = SessionLocal()
    try:
        reviewer = db_session.query(User).filter(User.telegram_id == update.effective_user.id).first()
        new_review = Review(
            job_id=review_data['job_id'],
            reviewer_id=reviewer.id,
            reviewee_id=review_data['reviewee_id'],
            rating=review_data['rating'],
            comment=comment
        )
        db_session.add(new_review)
        db_session.commit()
        await update.message.reply_text("✅ Review submitted. Thank you!")
    finally:
        db_session.close()
    
    context.user_data.clear()
    return ConversationHandler.END

async def skip_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves a review with only a rating (no comment) and ends the conversation."""
    review_data = context.user_data.get('review_data')
    db_session = SessionLocal()
    try:
        reviewer = db_session.query(User).filter(User.telegram_id == update.effective_user.id).first()
        new_review = Review(
            job_id=review_data['job_id'],
            reviewer_id=reviewer.id,
            reviewee_id=review_data['reviewee_id'],
            rating=review_data['rating'],
            comment=None
        )
        db_session.add(new_review)
        db_session.commit()
        await update.message.reply_text("✅ Review (rating only) submitted. Thank you!")
    finally:
        db_session.close()

    context.user_data.clear()
    return ConversationHandler.END

