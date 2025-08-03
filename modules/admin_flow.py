from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import SessionLocal, User, Transaction
from config import ADMIN_ID

AWAIT_BAN_REASON = range(1)


async def admin_confirm_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tx_id = int(query.data.split('_')[-1])

    db_session = SessionLocal()
    try:
        tx = db_session.query(Transaction).filter(Transaction.id == tx_id).first()
        if not tx or tx.status != 'pending' or tx.type != 'withdrawal':
            await query.edit_message_text("This transaction is not a pending withdrawal or was not found.")
            return
        tx.status = 'completed'
        db_session.commit()
        await query.edit_message_text(f"✅ Marked withdrawal of ${tx.amount} for user {tx.user.first_name} as complete.")
        await context.bot.send_message(
            chat_id=tx.user.telegram_id,
            text=f"Your withdrawal request for ${tx.amount} has been processed and the funds have been sent."
        )
    finally:
        db_session.close()


async def admin_confirm_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for admin to confirm a user's deposit."""
    query = update.callback_query
    await query.answer()
    tx_id = int(query.data.split('_')[-1])

    db_session = SessionLocal()
    try:
        tx = db_session.query(Transaction).filter(Transaction.id == tx_id).first()
        if not tx or tx.status != 'pending' or tx.type != 'deposit':
            await query.edit_message_text("This transaction is not a pending deposit or was not found.")
            return
        tx.status = 'completed'
        user = tx.user
        user.balance += tx.amount
        db_session.commit()
        await query.edit_message_text(f"✅ Confirmed deposit of ${tx.amount} for user {user.first_name}.")
        await context.bot.send_message(
            chat_id=user.telegram_id,
            text=f"Your deposit of ${tx.amount} has been successfully credited to your wallet."
        )
    finally:
        db_session.close()

def get_admin_dashboard_markup():
    keyboard = [
        [InlineKeyboardButton("View All Users", callback_data='admin_list_users_0')],
        [InlineKeyboardButton("Platform Statistics (Placeholder)", callback_data='admin_stats')],
    ]
    return InlineKeyboardMarkup(keyboard)

async def show_admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the main admin dashboard."""
    text = "**Admin Control Panel**\n\nWelcome, Admin. Please choose an option."
    markup = get_admin_dashboard_markup()
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text=text, reply_markup=markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=markup, parse_mode='Markdown')


async def list_all_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays a paginated list of all users."""
    query = update.callback_query
    await query.answer()

    page = int(query.data.split('_')[-1])
    users_per_page = 10
    offset = page * users_per_page
    
    db_session = SessionLocal()
    try:
        all_users = db_session.query(User).order_by(User.id).limit(users_per_page).offset(offset).all()
        total_users = db_session.query(User).count()
        
        if not all_users:
            await query.edit_message_text("No users found.", reply_markup=get_admin_dashboard_markup())
            return
            
        keyboard = []
        for user in all_users:
            status_icon = "" if user.status == 'active' else ""
            button_text = f"{user.first_name} (@{user.username or 'N/A'}) - {user.role or 'N/A'}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"admin_view_user_{user.id}")])

        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_list_users_{page - 1}"))
        if (page + 1) * users_per_page < total_users:
            nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"admin_list_users_{page + 1}"))
        if nav_row:
            keyboard.append(nav_row)
        print("\n\n\n", page, "\n\n\n")
        keyboard.append([InlineKeyboardButton("Back to Admin Menu", callback_data="admin_back_to_menu")])
        await query.edit_message_text(f"All Users - {str(len(all_users))}", reply_markup=InlineKeyboardMarkup(keyboard))
    finally:
        db_session.close()


async def show_user_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows detailed information for a specific user."""
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split('_')[-1])

    db_session = SessionLocal()
    try:
        user = db_session.query(User).filter(User.id == user_id).first()
        if not user:
            await query.edit_message_text("User not found.")
            return

        text = (
            f"**User Details**\n\n"
            f"**Name:** {user.first_name}\n"
            f"**Username:** @{user.username or 'N/A'}\n"
            f"**Telegram ID:** `{user.telegram_id}`\n"
            f"**Role:** {user.role or 'Not Set'}\n"
            f"**Status:** `{user.status.upper()}`\n"
            f"**Joined:** {user.created_at.strftime('%Y-%m-%d')}"
        )

        keyboard = []
        if user.status == 'active':
            keyboard.append([InlineKeyboardButton("Ban User ??", callback_data=f"admin_ban_user_{user.id}")])
        else:
            keyboard.append([InlineKeyboardButton("Unban User ??", callback_data=f"admin_unban_user_{user.id}")])
        
        keyboard.append([InlineKeyboardButton("Back to User List", callback_data="admin_list_users_0")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    finally:
        db_session.close()

async def prompt_for_ban_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the admin for a reason before banning a user."""
    query = update.callback_query
    await query.answer()
    
    user_id_to_ban = int(query.data.split('_')[-1])
    context.user_data['user_id_to_ban'] = user_id_to_ban
    
    await query.edit_message_text(
        text="Please enter the reason for banning this user.\n\nType /cancel to abort."
    )
    return AWAIT_BAN_REASON

async def ban_user_with_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Bans the user, stores the reason, and notifies them."""
    ban_reason = update.message.text
    user_id_to_ban = context.user_data.get('user_id_to_ban')

    db_session = SessionLocal()
    try:
        user_to_ban = db_session.query(User).filter(User.id == user_id_to_ban).first()
        if not user_to_ban:
            await update.message.reply_text("User not found.")
            return ConversationHandler.END
        user_to_ban.status = 'banned'
        user_to_ban.admin_notes = f"Ban Reason: {ban_reason}"
        db_session.commit()
        notification_text = (
            "Your account has been suspended.\n\n"
            f"**Reason:** {ban_reason}\n\n"
            "If you believe this is a mistake, you can discuss this with an administrator."
        )
        contact_button = InlineKeyboardButton("Contact Admin", callback_data=f"chat_{ADMIN_ID}")
        try:
            await context.bot.send_message(
                chat_id=user_to_ban.telegram_id,
                text=notification_text,
                reply_markup=InlineKeyboardMarkup([[contact_button]]),
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to send ban notification to user {user_to_ban.id}: {e}")

        await update.message.reply_text(f"User {user_to_ban.first_name} has been banned.")
        
    finally:
        db_session.close()
        context.user_data.pop('user_id_to_ban', None)

    return ConversationHandler.END

async def cancel_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop('user_id_to_ban', None)
    await update.message.reply_text("Ban process cancelled.")
    return ConversationHandler.END

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unbans a user and notifies them."""
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split('_')[-1])
    db_session = SessionLocal()
    try:
        user = db_session.query(User).filter(User.id == user_id).first()
        if user:
            user.status = 'active'
            db_session.commit()
            try:
                await context.bot.send_message(
                    chat_id=user.telegram_id,
                    text="Your account has been reactivated. You can now use the bot again."
                )
            except Exception as e:
                logger.error(f"Failed to send unban notification to user {user.id}: {e}")

            await query.answer("User has been unbanned.", show_alert=True)
            await show_user_details(update, context)
    finally:
        db_session.close()

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bans a user."""
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split('_')[-1])

    db_session = SessionLocal()
    try:
        user = db_session.query(User).filter(User.id == user_id).first()
        if user:
            user.status = 'banned'
            db_session.commit()
            await query.answer("User has been banned.", show_alert=True)
            await show_user_details(update, context)
    finally:
        db_session.close()
