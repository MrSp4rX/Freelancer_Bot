import math
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from database import SessionLocal, User, Transaction
from config import ADMIN_ID

AWAIT_DEPOSIT_AMOUNT = range(1)
AWAIT_WITHDRAWAL_AMOUNT, AWAIT_WITHDRAWAL_ADDRESS = range(1, 3)

async def prompt_for_withdrawal_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the user how much they want to withdraw."""
    query = update.callback_query
    await query.answer()
    db_session = SessionLocal()
    try:
        user = db_session.query(User).filter(User.telegram_id == query.from_user.id).first()
        await query.edit_message_text(
            f"Your current balance is **${user.balance:,.2f}**.\n\n"
            "Please enter the amount in USD you would like to withdraw.\n\n"
            "Type /cancel to return to your wallet.",
            parse_mode='Markdown'
        )
    finally:
        db_session.close()
    return AWAIT_WITHDRAWAL_AMOUNT

async def receive_withdrawal_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the amount and asks for the wallet address."""
    try:
        amount = float(update.message.text)
        if amount <= 0:
            await update.message.reply_text("Please enter a positive amount.")
            return AWAIT_WITHDRAWAL_AMOUNT
    except ValueError:
        await update.message.reply_text("That's not a valid number. Please try again.")
        return AWAIT_WITHDRAWAL_AMOUNT

    db_session = SessionLocal()
    try:
        user = db_session.query(User).filter(User.telegram_id == update.effective_user.id).first()
        if user.balance < amount:
            await update.message.reply_text(
                f"Insufficient funds. Your balance is ${user.balance:,.2f}, but you requested ${amount:,.2f}.\n\n"
                "Please enter a valid amount or type /cancel."
            )
            return AWAIT_WITHDRAWAL_AMOUNT
        context.user_data['withdrawal_amount'] = amount
        await update.message.reply_text(
            "Amount confirmed. Now, please reply with your USDT (TRC20) wallet address."
        )
        return AWAIT_WITHDRAWAL_ADDRESS
    finally:
        db_session.close()

async def process_withdrawal_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives wallet address, creates the transaction, and notifies the admin."""
    wallet_address = update.message.text
    amount = context.user_data.get('withdrawal_amount')
    user_id = update.effective_user.id

    db_session = SessionLocal()
    try:
        user = db_session.query(User).filter(User.telegram_id == user_id).first()
        user.balance -= amount
        new_tx = Transaction(
            user_id=user.id,
            type='withdrawal',
            amount=amount,
            status='pending',
            transaction_hash=wallet_address
        )
        db_session.add(new_tx)
        db_session.commit()
        admin_text = (
            f"**New Withdrawal Request**\n\n"
            f"**User:** {user.first_name} (`{user.telegram_id}`)\n"
            f"**Transaction ID:** `{new_tx.id}`\n"
            f"**Amount:** `${amount:,.2f}`\n"
            f"**To Address:** `{wallet_address}`"
        )
        keyboard = [[InlineKeyboardButton("Mark as Paid", callback_data=f"admin_confirm_withdrawal_{new_tx.id}")]]
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        await update.message.reply_text(
            "Your withdrawal request has been submitted. It will be processed by an administrator shortly."
        )
    finally:
        db_session.close()
        context.user_data.pop('withdrawal_amount', None)

    return ConversationHandler.END

async def show_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the user's wallet balance and options."""
    query = update.callback_query
    await query.answer()
    db_session = SessionLocal()
    try:
        user = db_session.query(User).filter(User.telegram_id == query.from_user.id).first()
        text = (
            f"**Your Wallet**\n\n"
            f"**Current Balance:** ${user.balance:,.2f} USD\n\n"
            "You can deposit funds to post jobs or withdraw your earnings."
        )
        if user.role == 'client':
            back_callback = "back_to_client_dashboard"
        else:
            back_callback = "back_to_freelancer_dashboard"

        keyboard = [
            [
                InlineKeyboardButton("Deposit Funds", callback_data="wallet_deposit_start"),
                InlineKeyboardButton("Withdraw Funds", callback_data="wallet_withdraw_start")
            ],
            [InlineKeyboardButton("View Transaction History", callback_data="wallet_history_0")],
            [InlineKeyboardButton("Back to Dashboard", callback_data=back_callback)]
        ]

        await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    finally:
        db_session.close()

async def show_transaction_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays a paginated list of the user's transactions."""
    query = update.callback_query
    await query.answer()
    page = int(query.data.split('_')[-1])
    db_session = SessionLocal()
    try:
        user = db_session.query(User).filter(User.telegram_id == query.from_user.id).first()
        tx_per_page = 5
        offset = page * tx_per_page
        user_transactions = db_session.query(Transaction).filter(Transaction.user_id == user.id).order_by(Transaction.created_at.desc()).limit(tx_per_page).offset(offset).all()
        total_tx = db_session.query(Transaction).filter(Transaction.user_id == user.id).count()

        if not user_transactions:
            text = "You have no transactions yet."
        else:
            total_pages = math.ceil(total_tx / tx_per_page)
            text = f"**Your Transaction History (Page {page + 1} of {total_pages})**\n\n"
            for tx in user_transactions:
                status_icon = {"pending": "⏳", "completed": "✅", "failed": "❌"}.get(tx.status, "")
                amount_sign = "-" if tx.type in ['withdrawal', 'payment'] else "+"
                text += f"{status_icon} `{tx.created_at.strftime('%Y-%m-%d')}`: {tx.type.capitalize()} of **{amount_sign}${tx.amount:,.2f}**\n"

        keyboard = []
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"wallet_history_{page - 1}"))
        if (page + 1) * tx_per_page < total_tx:
            nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"wallet_history_{page + 1}"))
        if nav_row:
            keyboard.append(nav_row)
        keyboard.append([InlineKeyboardButton("Back to Wallet", callback_data="back_to_wallet")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    finally:
        db_session.close()

async def prompt_for_deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the user how much they want to deposit, handling pre-filled amounts."""
    query = update.callback_query
    await query.answer()
    parts = query.data.split('_')
    if len(parts) > 3:
        try:
            prefilled_amount = float(parts[-1])
            text = (
                f"To continue, you need to deposit at least **${prefilled_amount:,.2f}**.\n\n"
                "Please confirm by sending this amount, or enter a different (higher) amount.\n\n"
                "Type /cancel to return to your wallet."
            )
        except ValueError:
            text = "An error occurred. Please enter the amount you wish to deposit."
    else:
        text = "Please enter the amount in USD you would like to deposit.\n\nType /cancel to return to your wallet."
    await query.edit_message_text(text, parse_mode='Markdown')
    return AWAIT_DEPOSIT_AMOUNT

async def generate_deposit_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Creates a pending transaction and shows payment details with a confirmation button."""
    try:
        amount = float(update.message.text)
        if amount <= 0:
            await update.message.reply_text("Please enter a positive amount.")
            return AWAIT_DEPOSIT_AMOUNT
    except ValueError:
        await update.message.reply_text("That's not a valid number. Please try again.")
        return AWAIT_DEPOSIT_AMOUNT

    db_session = SessionLocal()
    try:
        user = db_session.query(User).filter(User.telegram_id == update.effective_user.id).first()
        new_tx = Transaction(user_id=user.id, type='deposit', amount=amount, status='pending')
        db_session.add(new_tx)
        db_session.commit()
        wallet_address = "YOUR_USDT_TRC20_WALLET_ADDRESS"
        text = (
            f"To complete your deposit of **${amount:,.2f}**, please send the equivalent amount of USDT to the following TRC20 address:\n\n"
            f"`{wallet_address}`\n\n"
            f"Your unique Transaction ID is `{new_tx.id}`. After sending, please click the button below."
        )
        keyboard = [[InlineKeyboardButton("I Have Sent The Payment", callback_data=f"deposit_sent_{new_tx.id}")]]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    finally:
        db_session.close()
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Generic cancel handler for wallet conversations."""
    await update.message.reply_text("Action cancelled. Returning to your wallet.")
    return ConversationHandler.END

