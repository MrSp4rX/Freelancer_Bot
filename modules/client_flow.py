import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler
from sqlalchemy import func, or_

from database import SessionLocal, Job, User, Application, Review, Skill, Transaction
from . import matching

logger = logging.getLogger(__name__)

# --- STATE DEFINITIONS ---
GET_SKILLS, TITLE, DESCRIPTION, BUDGET, CURRENCY = range(5)
RATING, COMMENT = range(5, 7)


# --- DASHBOARD & GENERAL FUNCTIONS ---

def get_client_dashboard_markup() -> InlineKeyboardMarkup:
    """Creates the main client dashboard keyboard."""
    keyboard = [
        [InlineKeyboardButton("Post a New Job", callback_data='client_post_job')],
        [InlineKeyboardButton("Active Projects", callback_data='client_active_projects')],
        [InlineKeyboardButton("View Proposals", callback_data='client_view_proposals')],
        [InlineKeyboardButton("Completed Jobs", callback_data='client_completed_jobs')],
        [InlineKeyboardButton("Chat with Freelancer", callback_data='chat_from_dashboard_client')],
        [InlineKeyboardButton("Billing & Payments", callback_data='client_wallet')],
    ]
    return InlineKeyboardMarkup(keyboard)

async def show_client_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the main client dashboard."""
    user_name = update.effective_user.first_name
    text = f"Client Control Center\nWelcome, {user_name}!"
    markup = get_client_dashboard_markup()
    if update.callback_query:
        await update.callback_query.edit_message_text(text=text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)

async def client_button_placeholder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """A placeholder for features that are not yet implemented."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text=f"This feature (`{query.data}`) is under construction.\n\n"
             "Press the button below to return to your dashboard.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="back_to_client_dashboard")]])
    )

# --- JOB POSTING CONVERSATION ---

async def post_job_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the job posting conversation by asking for skills as text."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "Let's post a new job.\n\n"
        "Please list the skills required for this job, separated by commas.\n\n"
        "Example: `Python, Graphic Design, Social Media Marketing`\n\n"
        "Type /cancel to stop.",
        parse_mode='Markdown'
    )
    return GET_SKILLS

async def received_skills_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes the text input of skills, finds them in the DB, and proceeds."""
    skill_names = [skill.strip() for skill in update.message.text.split(',')]
    
    db_session = SessionLocal()
    try:
        # Find all skills in the database that match the provided names (case-insensitive)
        found_skills = db_session.query(Skill).filter(
            or_(*[func.lower(Skill.name) == func.lower(name) for name in skill_names])
        ).all()
        
        if not found_skills:
            await update.message.reply_text("I couldn't find any of the skills you listed. Please check the spelling and try again.\n\nExample: `Python, Web Development`")
            return GET_SKILLS

        # Store the IDs of the skills that were found
        context.user_data['job_skill_ids'] = {skill.id for skill in found_skills}
        found_names = [skill.name for skill in found_skills]
        
        await update.message.reply_text(
            f"✅ Skills recognized: {', '.join(found_names)}\n\n"
            "Great. Now, what is the job title?"
        )
        return TITLE
    finally:
        db_session.close()

async def received_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the job title and asks for the description."""
    context.user_data['title'] = update.message.text
    await update.message.reply_text("Got it. Now, please provide a detailed description.")
    return DESCRIPTION

async def received_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the description and asks for the budget."""
    context.user_data['description'] = update.message.text
    await update.message.reply_text("Excellent. What is the total budget in USD? (e.g., 500)")
    return BUDGET

async def received_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives budget, checks balance, and posts the job or prompts for deposit."""
    try:
        budget = float(update.message.text)
        if budget <= 0:
            await update.message.reply_text("Please enter a positive amount for the budget.")
            return BUDGET
    except ValueError:
        await update.message.reply_text("That's not a valid number. Please try again.")
        return BUDGET

    context.user_data['budget'] = budget
    title = context.user_data['title']
    description = context.user_data['description']
    skill_ids = context.user_data['job_skill_ids']

    db_session = SessionLocal()
    try:
        client = db_session.query(User).filter(User.telegram_id == update.effective_user.id).first()
        if client.balance >= budget:
            client.balance -= budget

            new_job = Job(
                title=title,
                description=description,
                budget=budget,
                client_id=client.id,
                status='open'
            )
            skills_to_add = db_session.query(Skill).filter(Skill.id.in_(skill_ids)).all()
            new_job.skills_required.extend(skills_to_add)
            db_session.add(new_job)
            db_session.commit()
            payment_tx = Transaction(
                user_id=client.id,
                type='payment',
                amount=budget,
                status='completed',
                related_job_id=new_job.id
            )
            db_session.add(payment_tx)
            db_session.commit()

            await update.message.reply_text(
                f"Success! ${budget:,.2f} has been deducted from your wallet.\n\n"
                f"Your job '{title}' is now live and freelancers are being notified."
            )
            await matching.notify_matching_freelancers(context, new_job)
        else:
            shortfall = budget - client.balance
            text = (
                f"**Insufficient Funds**\n\n"
                f"Your current balance is: `${client.balance:,.2f}`\n"
                f"The job requires: `${budget:,.2f}`\n\n"
                f"You need to deposit at least **${shortfall:,.2f}** to post this job."
            )
            keyboard = [[InlineKeyboardButton(f"Deposit ${shortfall:,.2f} Now", callback_data=f"wallet_deposit_start_{shortfall}")]]
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    finally:
        db_session.close()

    context.user_data.clear()
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the current conversation."""
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("Action cancelled.")
    else:
        await update.message.reply_text("Action cancelled.")
    
    context.user_data.clear()
    await show_client_dashboard(update, context)
    return ConversationHandler.END

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
            f"Proposal for: {app.job.title}\n\n"
            f"From Freelancer: {app.freelancer.first_name} (@{app.freelancer.username})\n"
            f"Bid Amount: ${app.bid_amount:,.2f} USD\n\n"
            f"Message:\n{app.proposal_text}"
        )

        keyboard = []
        nav_row = []
        if current_index > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"view_proposals_{job_id}_{current_index - 1}"))
        if current_index < len(applications) - 1:
            nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"view_proposals_{job_id}_{current_index + 1}"))
        keyboard.append(nav_row)
        keyboard.append([InlineKeyboardButton(" Contact Freelancer", callback_data=f"chat_{app.freelancer.id}_{job_id}")])
        keyboard.append([InlineKeyboardButton("View Freelancer's Profile", callback_data=f"view_profile_{app.freelancer.id}_{job_id}_{current_index}")])
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
            f"Freelancer Profile\n\n"
            f"Name: {freelancer.first_name}\n"
            f"Bio: {freelancer.bio or 'No bio set.'}\n\n"
            f"Reputation:\n"
            f"- Average Rating: {rating_str}\n"
            f"- Jobs Completed: {completed_jobs}"
        )
        keyboard = [    [InlineKeyboardButton("Report Freelancer", callback_data=f"report_user_{freelancer.id}")],
			[InlineKeyboardButton("⬅️ Back to Proposal", callback_data=f"view_proposals_{job_id_str}_{index_str}")]
		]
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
        
        other_apps = db_session.query(Application).filter(Application.job_id == job.id, Application.id != accepted_app.id).all()
        for app in other_apps:
            app.status = 'rejected'
            try:
                await context.bot.send_message(chat_id=app.freelancer.telegram_id, text=f"Unfortunately, your application for '{job.title}' was not selected.")
            except Exception as e:
                logger.error(f"Failed to send rejection to {app.freelancer.telegram_id}: {e}")
        
        db_session.commit()
        
        try:
            await context.bot.send_message(chat_id=accepted_app.freelancer.telegram_id, text=f"Congratulations! Your application for '{job.title}' has been accepted!")
        except Exception as e:
            logger.error(f"Failed to send acceptance to {accepted_app.freelancer.telegram_id}: {e}")
        
        await query.edit_message_text(f"✅ You have hired {accepted_app.freelancer.first_name} for {job.title}.")
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
            # Add the Job ID to the button text
            button_text = f"{job.title} (ID: {job.id}) - {job.status}"
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

        response_text = "Your Completed Jobs\n\n"
        for job in completed_jobs:
            response_text += f"✅ {job.title}\n"
            if job.hired_freelancer:
                response_text += f"   - Freelancer: {job.hired_freelancer.first_name}\n"
            response_text += f"   - Budget: ${job.budget:,.2f}\n\n"
            
        keyboard = [[InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="back_to_client_dashboard")]]
        await query.edit_message_text(text=response_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    finally:
        db_session.close()

async def confirm_completion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Marks a job as complete, deducts a 10% fee, pays the freelancer 90%,
    and initiates the review process.
    """
    query = update.callback_query
    await query.answer()
    job_id = int(query.data.split('_')[-1])
    db_session = SessionLocal()
    try:
        job = db_session.query(Job).filter(Job.id == job_id).first()
        if job and job.status == 'pending_completion':
            commission = job.budget * 0.10
            freelancer_payout = job.budget - commission
            freelancer = job.hired_freelancer
            if freelancer:
                freelancer.balance += freelancer_payout
                earning_tx = Transaction(
                    user_id=freelancer.id,
                    type='earning',
                    amount=freelancer_payout,
                    status='completed',
                    related_job_id=job.id
                )
                db_session.add(earning_tx)
            job.status = 'completed'
            db_session.commit()
            logger.info(f"Payment processed for Job ID: {job.id}. Freelancer Payout: ${freelancer_payout}, Commission: ${commission}")
            if freelancer:
                notification_text = (
                    f"Payment Received!\n\n"
                    f"The client has confirmed completion for the job: '{job.title}'.\n\n"
                    f"An amount of **${freelancer_payout:,.2f}** (90% of the ${job.budget:,.2f} budget) has been credited to your wallet."
                )
                await context.bot.send_message(chat_id=freelancer.telegram_id, text=notification_text, parse_mode='Markdown')

            await query.edit_message_text(f"Project '{job.title}' is now complete. Payment has been released to the freelancer.")
            if freelancer:
                await prompt_for_review(context, job, reviewer=job.client, reviewee=freelancer)
                await prompt_for_review(context, job, reviewer=freelancer, reviewee=job.client)

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

# Add to freelancer_bot/modules/client_flow.py

async def show_billing_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays billing and payment information to the client."""
    query = update.callback_query
    await query.answer()
    
    text = (
        " **Billing & Payments**\n\n"
        "All transactions on this platform are managed through an escrow system using cryptocurrency.\n\n"
        "- **Deposits**: When you post a job, you deposit 75% of the budget into escrow.\n"
        "- **Payments**: Funds are automatically released to the freelancer from escrow only after you confirm the job is completed to your satisfaction.\n\n"
        "For your transaction history, please contact an administrator."
    )
    
    keyboard = [[InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="back_to_client_dashboard")]]
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


