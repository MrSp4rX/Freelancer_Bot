# To be placed in: freelancer_bot/modules/freelancer_flow.py

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler
from sqlalchemy import func

# Import all necessary models from the database
from database import SessionLocal, Job, User, Application, Review, Skill

# --- STATE DEFINITIONS ---
PROPOSAL, BID_AMOUNT = range(2)
EDIT_BIO = range(2, 3)

# --- DASHBOARD & GENERAL FUNCTIONS ---
def get_freelancer_dashboard_markup() -> InlineKeyboardMarkup:
    """Creates the freelancer dashboard keyboard."""
    keyboard = [
        [InlineKeyboardButton("Browse New Jobs", callback_data='freelancer_browse_jobs')],
        [InlineKeyboardButton("My Bids & Proposals", callback_data='freelancer_my_bids')],
        [InlineKeyboardButton("Chat with Client", callback_data='chat_from_dashboard_freelancer')],
        [InlineKeyboardButton("Ongoing Projects", callback_data='freelancer_ongoing_projects')],
        [InlineKeyboardButton("My Profile & Skills", callback_data='freelancer_profile')],
        [InlineKeyboardButton("Earnings & Payouts", callback_data='freelancer_earnings')],
    ]
    return InlineKeyboardMarkup(keyboard)

async def show_freelancer_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    text = f"Freelancer Career *\nWelcome, {user_name}!"
    markup = get_freelancer_dashboard_markup()
    if update.callback_query:
        await update.callback_query.edit_message_text(text=text, reply_markup=markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode='Markdown')


async def freelancer_button_placeholder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text=f"This feature (`{query.data}`) is under construction.\n\n"
             "Press the button below to return to your dashboard.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("?? Back to Dashboard", callback_data="back_to_freelancer_dashboard")]])
    )

# --- PROFILE VIEW & EDIT FLOW ---
async def show_my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db_session = SessionLocal()
    try:
        freelancer = db_session.query(User).filter(User.telegram_id == query.from_user.id).first()
        avg_rating, num_reviews = db_session.query(func.avg(Review.rating), func.count(Review.id)).filter(Review.reviewee_id == freelancer.id).first()
        completed_jobs = db_session.query(Job).filter(Job.hired_freelancer_id == freelancer.id, Job.status == 'completed').count()
        
        rating_str = f"{avg_rating:.2f} ⭐ out of {num_reviews} reviews" if num_reviews > 0 else "No reviews yet"
        skills_str = ", ".join([skill.name for skill in freelancer.skills]) or "No skills set."

        profile_text = (
            f"**Your Freelancer Profile**\n\n"
            f"**Name:** {freelancer.first_name}\n"
            f"**Bio:** {freelancer.bio or 'Not set.'}\n"
            f"**Skills:** {skills_str}\n\n"
            f"**Statistics:**\n"
            f"- **Average Rating:** {rating_str}\n"
            f"- **Jobs Completed:** {completed_jobs}"
        )
        keyboard = [
            [InlineKeyboardButton("✏️ Edit Bio", callback_data="edit_profile_bio")],
            [InlineKeyboardButton("??️ Edit Skills", callback_data="edit_skills_menu")],
            [InlineKeyboardButton("?? Back to Dashboard", callback_data="back_to_freelancer_dashboard")]
        ]
        await query.edit_message_text(text=profile_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    finally:
        db_session.close()

async def start_bio_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Please send your new bio (max 200 characters).\n\nType /cancel to stop.")
    return EDIT_BIO

async def received_bio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    new_bio = update.message.text[:200]
    db_session = SessionLocal()
    try:
        user = db_session.query(User).filter(User.telegram_id == update.effective_user.id).first()
        user.bio = new_bio
        db_session.commit()
        await update.message.reply_text("✅ Your bio has been updated successfully!")
    finally:
        db_session.close()
    await show_freelancer_dashboard(update, context)
    return ConversationHandler.END

async def edit_skills_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db_session = SessionLocal()
    try:
        freelancer = db_session.query(User).filter(User.telegram_id == query.from_user.id).first()
        all_skills = db_session.query(Skill).all()
        freelancer_skill_ids = {skill.id for skill in freelancer.skills}
        keyboard = []
        for skill in all_skills:
            text = f"✅ {skill.name}" if skill.id in freelancer_skill_ids else skill.name
            keyboard.append([InlineKeyboardButton(text, callback_data=f"toggle_skill_{skill.id}")])
        keyboard.append([InlineKeyboardButton("?? Back to Profile", callback_data="freelancer_profile")])
        await query.edit_message_text("Select skills to add or remove:", reply_markup=InlineKeyboardMarkup(keyboard))
    finally:
        db_session.close()

async def toggle_skill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    skill_id = int(query.data.split('_')[-1])
    db_session = SessionLocal()
    try:
        freelancer = db_session.query(User).filter(User.telegram_id == query.from_user.id).first()
        skill_to_toggle = db_session.query(Skill).filter(Skill.id == skill_id).first()
        if skill_to_toggle in freelancer.skills:
            freelancer.skills.remove(skill_to_toggle)
            await query.answer(f"Removed '{skill_to_toggle.name}'")
        else:
            freelancer.skills.append(skill_to_toggle)
            await query.answer(f"Added '{skill_to_toggle.name}'")
        db_session.commit()
    finally:
        db_session.close()
    await edit_skills_menu(update, context)

# --- OTHER FREELANCER FUNCTIONS (Unchanged but included for completeness) ---

# In freelancer_flow.py

async def browse_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    db_session = SessionLocal()
    try:
        all_jobs = db_session.query(Job).filter(Job.status == 'open').order_by(Job.created_at.desc()).all()
        if not all_jobs:
            await query.edit_message_text("No open jobs at the moment.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_freelancer_dashboard")]]))
            return

        current_index = 0
        
        # NEW: Logic to handle viewing a specific job by its ID
        if query.data.startswith('view_specific_job_'):
            target_id = int(query.data.split('_')[-1])
            # Find the index of the job with the matching ID
            try:
                current_index = next(i for i, job in enumerate(all_jobs) if job.id == target_id)
            except StopIteration:
                await query.edit_message_text("This job is no longer available or could not be found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_freelancer_dashboard")]]))
                return
        
        # Existing logic for handling pagination (Next/Prev)
        elif query.data.startswith('browse_job_'):
            try:
                current_index = int(query.data.split('_')[-1])
            except (ValueError, IndexError):
                current_index = 0

        # Ensure index is valid
        if not (0 <= current_index < len(all_jobs)):
            await query.edit_message_text("An error occurred while trying to display this job.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_freelancer_dashboard")]]))
            return
            
        job = all_jobs[current_index]
        job_text = (f"**{job.title}**\n\n"
                    f"**Description:** {job.description}\n\n"
                    f"**Budget:** ${job.budget:,.2f} USD ({job.currency})")
        
        keyboard = []
        nav_row = []
        if current_index > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"browse_job_{current_index - 1}"))
        if current_index < len(all_jobs) - 1:
            nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"browse_job_{current_index + 1}"))
        
        if nav_row:
            keyboard.append(nav_row)
            
        keyboard.append([InlineKeyboardButton("✍️ Apply for this Job", callback_data=f"apply_job_{job.id}")])
        keyboard.append([InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="back_to_freelancer_dashboard")])
        
        await query.edit_message_text(text=job_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    finally:
        db_session.close()

async def start_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['applying_for_job_id'] = int(query.data.split('_')[-1])
    await query.edit_message_text("Please write your **proposal**.\n\nType /cancel to stop.", parse_mode='Markdown')
    return PROPOSAL

async def received_proposal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['proposal_text'] = update.message.text
    await update.message.reply_text("What is your **bid amount** in USD?", parse_mode='Markdown')
    return BID_AMOUNT

async def received_bid_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try: bid = float(update.message.text)
    except ValueError:
        await update.message.reply_text("Invalid number. Please enter your bid again.")
        return BID_AMOUNT
    db_session = SessionLocal()
    try:
        freelancer = db_session.query(User).filter(User.telegram_id == update.effective_user.id).first()
        job_id = context.user_data['applying_for_job_id']
        proposal = context.user_data['proposal_text']
        existing_application = db_session.query(Application).filter(Application.job_id == job_id, Application.freelancer_id == freelancer.id).first()
        if existing_application:
            await update.message.reply_text("You have already applied for this job.")
            context.user_data.clear()
            return ConversationHandler.END
        new_application = Application(proposal_text=proposal, bid_amount=bid, job_id=job_id, freelancer_id=freelancer.id)
        db_session.add(new_application)
        db_session.commit()
        await update.message.reply_text("✅ Your application has been submitted!")
    finally:
        db_session.close()
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Action cancelled.")
    context.user_data.clear()
    return ConversationHandler.END

async def show_my_applications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows a freelancer their applications one by one with pagination."""
    query = update.callback_query
    await query.answer()

    db_session = SessionLocal()
    try:
        freelancer = db_session.query(User).filter(User.telegram_id == query.from_user.id).first()
        my_apps = db_session.query(Application).filter(Application.freelancer_id == freelancer.id).order_by(Application.created_at.desc()).all()

        if not my_apps:
            await query.edit_message_text("You have not applied for any jobs yet.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_freelancer_dashboard")]]))
            return

        current_index = 0
        if query.data.startswith('view_app_'):
            try:
                current_index = int(query.data.split('_')[-1])
            except (ValueError, IndexError):
                current_index = 0

        app = my_apps[current_index]

        status_emoji = {"submitted": "➡️", "accepted": "✅", "rejected": "❌", "viewed": "??"}.get(app.status, "➡️")

        response_text = (
            f"**Your Application ({current_index + 1}/{len(my_apps)})**\n\n"
            f"{status_emoji} **Job:** {app.job.title} (ID: `{app.job.id}`)\n" # Job ID is now visible here
            f"   - **Status:** `{app.status}`\n"
            f"   - **Your Bid:** `${app.bid_amount:,.2f}`"
        )

        keyboard = []
        nav_row = []
        if current_index > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"view_app_{current_index - 1}"))
        if current_index < len(my_apps) - 1:
            nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"view_app_{current_index + 1}"))

        if nav_row:
            keyboard.append(nav_row)

        keyboard.append([InlineKeyboardButton("?? Contact Client", callback_data=f"chat_{app.job.client.id}_{app.job.id}")])
        keyboard.append([InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="back_to_freelancer_dashboard")])

        await query.edit_message_text(text=response_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    finally:
        db_session.close()

async def view_ongoing_projects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db_session = SessionLocal()
    try:
        freelancer = db_session.query(User).filter(User.telegram_id == query.from_user.id).first()
        ongoing_jobs = db_session.query(Job).filter(Job.hired_freelancer_id == freelancer.id, Job.status.in_(['in_progress', 'pending_completion'])).all()
        if not ongoing_jobs:
            await query.edit_message_text("You have no ongoing projects.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_freelancer_dashboard")]]))
            return

        keyboard = []
        for job in ongoing_jobs:
            # Add the Job ID to the button text
            button_text = f"{job.title} (ID: {job.id}) - {job.status}"
            if job.status == 'in_progress':
                keyboard.append([InlineKeyboardButton(button_text, callback_data=f"mark_complete_{job.id}")])
            else:
                keyboard.append([InlineKeyboardButton(button_text, callback_data="none")])

        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_freelancer_dashboard")])
        await query.edit_message_text("Select a job to mark it as complete:", reply_markup=InlineKeyboardMarkup(keyboard))
    finally:
        db_session.close()


async def mark_job_complete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    job_id = int(query.data.split('_')[-1])
    db_session = SessionLocal()
    try:
        job = db_session.query(Job).filter(Job.id == job_id).first()
        if job and job.status == 'in_progress':
            job.status = 'pending_completion'
            db_session.commit()
            await query.edit_message_text(f"You marked '{job.title}' as complete. The client has been notified.")
            await context.bot.send_message(chat_id=job.client.telegram_id, text=f"?? Freelancer marked '{job.title}' as complete. Please review and confirm.")
        else:
            await query.edit_message_text("This action cannot be performed now.")
    finally:
        db_session.close()


# To be placed in: freelancer_bot/modules/freelancer_flow.py

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler
from sqlalchemy import func

from database import SessionLocal, Job, User, Application, Review, Skill

# --- STATE DEFINITIONS ---
PROPOSAL, BID_AMOUNT = range(2)
EDIT_BIO = range(2, 3)

# --- PROFILE VIEW & EDIT FLOW ---
async def show_my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db_session = SessionLocal()
    try:
        freelancer = db_session.query(User).filter(User.telegram_id == query.from_user.id).first()
        avg_rating, num_reviews = db_session.query(func.avg(Review.rating), func.count(Review.id)).filter(Review.reviewee_id == freelancer.id).first()
        completed_jobs = db_session.query(Job).filter(Job.hired_freelancer_id == freelancer.id, Job.status == 'completed').count()
        rating_str = f"{avg_rating:.2f} ⭐ out of {num_reviews} reviews" if num_reviews > 0 else "No reviews yet"
        skills_str = ", ".join([skill.name for skill in freelancer.skills]) or "No skills set."

        profile_text = (
            f"**Your Freelancer Profile**\n\n"
            f"**Name:** {freelancer.first_name}\n"
            f"**Bio:** {freelancer.bio or 'Not set.'}\n"
            f"**Skills:** {skills_str}\n\n"
            f"**Statistics:**\n"
            f"- **Average Rating:** {rating_str}\n"
            f"- **Jobs Completed:** {completed_jobs}"
        )
        keyboard = [
            [InlineKeyboardButton("✏️ Edit Bio", callback_data="edit_profile_bio")],
            [InlineKeyboardButton("??️ Edit Skills", callback_data="edit_skills_menu_0")],
            [InlineKeyboardButton("?? Back to Dashboard", callback_data="back_to_freelancer_dashboard")]
        ]
        await query.edit_message_text(text=profile_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    finally:
        db_session.close()

async def start_bio_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Please send your new bio (max 200 characters).\n\nType /cancel to stop.")
    return EDIT_BIO

async def received_bio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    new_bio = update.message.text[:200]
    db_session = SessionLocal()
    try:
        user = db_session.query(User).filter(User.telegram_id == update.effective_user.id).first()
        user.bio = new_bio
        db_session.commit()
        await update.message.reply_text("✅ Your bio has been updated successfully!")
    finally:
        db_session.close()
    await show_freelancer_dashboard(update, context)
    return ConversationHandler.END

async def edit_skills_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = 0
    if query.data != 'edit_skills_menu':
        try: page = int(query.data.split('_')[-1])
        except (ValueError, IndexError): page = 0
    skills_per_page = 7
    offset = page * skills_per_page
    db_session = SessionLocal()
    try:
        freelancer = db_session.query(User).filter(User.telegram_id == query.from_user.id).first()
        all_skills = db_session.query(Skill).limit(skills_per_page).offset(offset).all()
        total_skills = db_session.query(Skill).count()
        freelancer_skill_ids = {skill.id for skill in freelancer.skills}
        keyboard = []
        for skill in all_skills:
            text = f"✅ {skill.name}" if skill.id in freelancer_skill_ids else skill.name
            keyboard.append([InlineKeyboardButton(text, callback_data=f"toggle_skill_{skill.id}_{page}")])
        nav_row = []
        if page > 0: nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"edit_skills_menu_{page - 1}"))
        if (page + 1) * skills_per_page < total_skills: nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"edit_skills_menu_{page + 1}"))
        if nav_row: keyboard.append(nav_row)
        keyboard.append([InlineKeyboardButton("?? Back to Profile", callback_data="freelancer_profile")])
        await query.edit_message_text("Select skills to add or remove:", reply_markup=InlineKeyboardMarkup(keyboard))
    finally:
        db_session.close()

async def toggle_skill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, _, skill_id_str, page_str = query.data.split('_')
    skill_id, page = int(skill_id_str), int(page_str)
    db_session = SessionLocal()
    try:
        freelancer = db_session.query(User).filter(User.telegram_id == query.from_user.id).first()
        skill_to_toggle = db_session.query(Skill).filter(Skill.id == skill_id).first()
        if skill_to_toggle in freelancer.skills:
            freelancer.skills.remove(skill_to_toggle)
            await query.answer(f"Removed '{skill_to_toggle.name}'")
        else:
            freelancer.skills.append(skill_to_toggle)
            await query.answer(f"Added '{skill_to_toggle.name}'")
        db_session.commit()
    finally:
        db_session.close()
    query.data = f"edit_skills_menu_{page}"
    await edit_skills_menu(update, context)

# Add to freelancer_bot/modules/freelancer_flow.py

async def show_earnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Calculates and displays the freelancer's total earnings."""
    query = update.callback_query
    await query.answer()
    db_session = SessionLocal()
    try:
        freelancer = db_session.query(User).filter(User.telegram_id == query.from_user.id).first()
        
        # Calculate total earnings from completed jobs
        total_earned = db_session.query(func.sum(Job.budget)).filter(
            Job.hired_freelancer_id == freelancer.id,
            Job.status == 'completed'
        ).scalar() or 0.0

        earnings_text = f"?? **Your Earnings & Payouts**\n\n"
        earnings_text += f"**Total Lifetime Earnings:** ${total_earned:,.2f} USD\n\n"
        earnings_text += "Payouts are processed manually at this time. Please contact an admin to request a withdrawal."

        keyboard = [[InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="back_to_freelancer_dashboard")]]
        await query.edit_message_text(text=earnings_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    finally:
        db_session.close()

