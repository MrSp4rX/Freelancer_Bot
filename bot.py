# Regular Imports
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# Self Imports
from config import TELEGRAM_TOKEN, ADMIN_ID
from database import init_db, SessionLocal, User
from modules import (
    client_flow,
    freelancer_flow,
    common,
    payments,
    chat_flow,
    admin_flow,
    report_flow,
    wallet_flow
)

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry point for the admin panel. Restricted to ADMIN_ID."""
    if str(update.effective_user.id) != ADMIN_ID:
        await update.message.reply_text("You are not authorized to use this command.")
        return
    await admin_flow.show_admin_dashboard(update, context)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command for new and returning users."""
    user_info = update.effective_user
    db_session = SessionLocal()
    try:
        user = db_session.query(User).filter(User.telegram_id == user_info.id).first()
        if not user:
            new_user = User(
                telegram_id=user_info.id,
                first_name=user_info.first_name,
                username=user_info.username
            )
            db_session.add(new_user)
            db_session.commit()
            logger.info(f"New user created: {user_info.username} ({user_info.id})")
            await common.show_main_menu(update, context)
            return
        if user.status == 'banned':
            await update.message.reply_text("Your account has been suspended. Please contact support.")
            return
        if user.role == 'client':
            await client_flow.show_client_dashboard(update, context)
        elif user.role == 'freelancer':
            await freelancer_flow.show_freelancer_dashboard(update, context)
        else:
            await common.show_main_menu(update, context)
    finally:
        db_session.close()

async def role_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the client/freelancer role selection and shows the correct dashboard."""
    query = update.callback_query
    await query.answer()

    role = 'client' if query.data == 'role_select_client' else 'freelancer'
    
    db_session = SessionLocal()
    try:
        user = db_session.query(User).filter(User.telegram_id == query.from_user.id).first()
        if user:
            user.role = role
            db_session.commit()
            logger.info(f"User {user.telegram_id} selected role: {role}")

            if role == 'client':
                await client_flow.show_client_dashboard(update, context)
            else:
                await freelancer_flow.show_freelancer_dashboard(update, context)
    finally:
        db_session.close()

async def test(update, context):
    await update.message.reply_text("Entered Test")
    return ConversationHandler.END

def main() -> None:
    init_db()
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    report_conv_handler = ConversationHandler(
		    entry_points=[CallbackQueryHandler(report_flow.start_report, pattern='^report_user_')],
		    states={
		        report_flow.AWAIT_REPORT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, report_flow.submit_report)]
		    },
		    fallbacks=[CommandHandler('cancel', report_flow.cancel_report)],
		    per_message=False
		)

    job_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(client_flow.post_job_start, pattern='^client_post_job$')],
        states={
            client_flow.GET_SKILLS: [MessageHandler(filters.TEXT & ~filters.COMMAND, client_flow.received_skills_text)],
            client_flow.TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, client_flow.received_title)],
            client_flow.DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, client_flow.received_description)],
            client_flow.BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, client_flow.received_budget)],
        },
        fallbacks=[CommandHandler('cancel', client_flow.cancel_conversation)],
        per_message=False
    )


    chat_conv_handler = ConversationHandler(
	    entry_points=[
	        CallbackQueryHandler(chat_flow.prompt_for_job_id, pattern='^chat_from_dashboard_'),
	        CallbackQueryHandler(chat_flow.start_chat, pattern='^chat_'),
	    ],
	    states={
	        chat_flow.AWAIT_JOB_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, chat_flow.receive_job_id_and_start_chat)],
	        chat_flow.CHATTING: [MessageHandler(filters.ALL & ~filters.COMMAND, chat_flow.relay_message)]
	},
	    fallbacks=[
	        CommandHandler('endchat', chat_flow.end_chat),
	        CommandHandler('cancel', chat_flow.cancel_chat_setup)
	    ],
	    per_message=False,
	    conversation_timeout=210
	)

    application_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(freelancer_flow.start_application, pattern='^apply_job_')],
        states={
            freelancer_flow.PROPOSAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, freelancer_flow.received_proposal)],
            freelancer_flow.BID_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, freelancer_flow.received_bid_amount)],
        },
        fallbacks=[CommandHandler('cancel', freelancer_flow.cancel_application)],
        per_message=False
    )

    review_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(client_flow.handle_rating_selection, pattern='^review_')],
        states={client_flow.COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, client_flow.received_review_comment)]},
        fallbacks=[CommandHandler('skip', client_flow.skip_comment), CommandHandler('cancel', client_flow.cancel_conversation)],
        per_message=False
    )

    profile_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(freelancer_flow.start_bio_edit, pattern='^edit_profile_bio$')],
        states={freelancer_flow.EDIT_BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, freelancer_flow.received_bio)]},
        fallbacks=[CommandHandler('cancel', freelancer_flow.cancel_application)],
        per_message=False
    )

    ban_conv_handler = ConversationHandler(
	    entry_points=[CallbackQueryHandler(admin_flow.prompt_for_ban_reason, pattern='^admin_ban_user_')],
	    states={
	        admin_flow.AWAIT_BAN_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_flow.ban_user_with_reason)]
	    },
	    fallbacks=[CommandHandler('cancel', admin_flow.cancel_ban)],
	    per_message=False
	)

    deposit_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(wallet_flow.prompt_for_deposit_amount, pattern='^wallet_deposit_start')],
        states={
            wallet_flow.AWAIT_DEPOSIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, wallet_flow.generate_deposit_details)]
        },
        fallbacks=[CommandHandler('cancel', wallet_flow.cancel_conversation)],
        per_message=False
    )

    withdrawal_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(wallet_flow.prompt_for_withdrawal_amount, pattern='^wallet_withdraw_start$')],
        states={
            wallet_flow.AWAIT_WITHDRAWAL_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, wallet_flow.receive_withdrawal_amount)],
            wallet_flow.AWAIT_WITHDRAWAL_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, wallet_flow.process_withdrawal_request)]
        },
        fallbacks=[CommandHandler('cancel', wallet_flow.cancel_conversation)],
        per_message=False
    )

    application.add_handler(withdrawal_conv_handler)
    application.add_handler(deposit_conv_handler)
    application.add_handler(CallbackQueryHandler(admin_flow.admin_confirm_deposit, pattern='^admin_confirm_deposit_'))
    application.add_handler(CallbackQueryHandler(admin_flow.admin_confirm_withdrawal, pattern='^admin_confirm_withdrawal_'))

    # 1. Conversation Handlers
    application.add_handler(job_conv_handler)
    application.add_handler(application_conv_handler)
    application.add_handler(review_conv_handler)
    application.add_handler(profile_conv_handler)
    application.add_handler(chat_conv_handler)
    application.add_handler(ban_conv_handler)
    application.add_handler(report_conv_handler)

    # 2. Command Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_command))

    # 3. Specific CallbackQuery Handlers
    # -- General, Payment, & Wallet --
    application.add_handler(CallbackQueryHandler(payments.handle_deposit_sent, pattern='^deposit_sent_'))
    application.add_handler(CallbackQueryHandler(role_selection_handler, pattern='^role_select_'))
    application.add_handler(CallbackQueryHandler(payments.handle_deposit_request, pattern='^deposit_'))
    application.add_handler(CallbackQueryHandler(payments.auto_confirm_payment, pattern='^payment_sent_'))
    application.add_handler(CallbackQueryHandler(wallet_flow.show_wallet, pattern='^client_wallet$'))
    application.add_handler(CallbackQueryHandler(wallet_flow.show_wallet, pattern='^freelancer_wallet$'))
    application.add_handler(CallbackQueryHandler(wallet_flow.show_wallet, pattern='^back_to_wallet$'))
    application.add_handler(CallbackQueryHandler(wallet_flow.show_transaction_history, pattern='^wallet_history_'))

    # -- Client Flow --
    application.add_handler(CallbackQueryHandler(client_flow.show_client_dashboard, pattern='^back_to_client_dashboard$'))
    application.add_handler(CallbackQueryHandler(client_flow.select_job_to_view_proposals, pattern='^client_view_proposals$'))
    application.add_handler(CallbackQueryHandler(client_flow.view_proposals_for_job, pattern='^view_proposals_'))
    application.add_handler(CallbackQueryHandler(client_flow.show_public_profile, pattern='^view_profile_'))
    application.add_handler(CallbackQueryHandler(client_flow.accept_application, pattern='^accept_app_'))
    application.add_handler(CallbackQueryHandler(client_flow.reject_application, pattern='^reject_app_'))
    application.add_handler(CallbackQueryHandler(client_flow.view_active_projects, pattern='^client_active_projects$'))
    application.add_handler(CallbackQueryHandler(client_flow.confirm_completion, pattern='^confirm_complete_'))
    application.add_handler(CallbackQueryHandler(client_flow.show_completed_jobs, pattern='^client_completed_jobs$'))
    application.add_handler(CallbackQueryHandler(client_flow.show_billing_info, pattern='^client_billing$'))

    # -- Freelancer Flow --
    application.add_handler(CallbackQueryHandler(freelancer_flow.show_freelancer_dashboard, pattern='^back_to_freelancer_dashboard$'))
    application.add_handler(CallbackQueryHandler(freelancer_flow.browse_jobs, pattern='^freelancer_browse_jobs$'))
    application.add_handler(CallbackQueryHandler(freelancer_flow.browse_jobs, pattern='^browse_job_'))
    application.add_handler(CallbackQueryHandler(freelancer_flow.browse_jobs, pattern='^view_specific_job_'))
    application.add_handler(CallbackQueryHandler(freelancer_flow.show_my_applications, pattern='^freelancer_my_bids$'))
    application.add_handler(CallbackQueryHandler(freelancer_flow.show_my_applications, pattern='^view_app_'))
    application.add_handler(CallbackQueryHandler(freelancer_flow.show_my_profile, pattern='^freelancer_profile$'))
    application.add_handler(CallbackQueryHandler(freelancer_flow.edit_skills_menu, pattern='^edit_skills_menu'))
    application.add_handler(CallbackQueryHandler(freelancer_flow.toggle_skill, pattern='^toggle_skill_'))
    application.add_handler(CallbackQueryHandler(freelancer_flow.view_ongoing_projects, pattern='^freelancer_ongoing_projects$'))
    application.add_handler(CallbackQueryHandler(freelancer_flow.mark_job_complete, pattern='^mark_complete_'))
    application.add_handler(CallbackQueryHandler(freelancer_flow.show_earnings, pattern='^freelancer_earnings$'))
    application.add_handler(CallbackQueryHandler(freelancer_flow.show_client_profile, pattern='^view_client_'))

    # -- Admin Flow --
    application.add_handler(CallbackQueryHandler(admin_flow.show_admin_dashboard, pattern='^admin_back_to_menu$'))
    application.add_handler(CallbackQueryHandler(admin_flow.list_all_users, pattern='^admin_list_users_'))
    application.add_handler(CallbackQueryHandler(admin_flow.show_user_details, pattern='^admin_view_user_'))
    application.add_handler(CallbackQueryHandler(admin_flow.unban_user, pattern='^admin_unban_user_'))
    application.add_handler(CallbackQueryHandler(payments.admin_confirm_payment, pattern='^admin_confirm_'))

    # 4. General "Catch-all" Placeholder Handlers (Must be last)
    application.add_handler(CallbackQueryHandler(client_flow.client_button_placeholder, pattern='^client_'))
    application.add_handler(CallbackQueryHandler(freelancer_flow.freelancer_button_placeholder, pattern='^freelancer_'))

    print("Bot is running...")
    application.run_polling()




if __name__ == '__main__':
    main()

