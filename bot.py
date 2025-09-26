import os
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, PreCheckoutQueryHandler, ExtBot
from telegram.error import TelegramError
from telegram import Update
from database import Database
import asyncio
from datetime import datetime
import re

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Suppress httpx request logging to prevent token exposure
logging.getLogger("httpx").setLevel(logging.WARNING)

# Bot configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
LOG_GROUP_ID = -1002911871934
INITIAL_ADMIN_ID = 8147394357

# Initialize database
db = Database()

class TelegramBot:
    def __init__(self):
        self.application = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build()
        self.setup_handlers()
        # Add error handler
        self.application.add_error_handler(self.error_handler)

    async def error_handler(self, update, context):
        logger.error(f"Exception while handling an update: {context.error}")
        # Try to notify user of error
        try:
            if update and update.effective_chat:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ An error occurred. Please try again later."
                )
        except:
            pass

    def setup_handlers(self):
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("chat", self.chat))
        self.application.add_handler(CommandHandler("end", self.end_chat))
        self.application.add_handler(CommandHandler("vip", self.vip))
        self.application.add_handler(CommandHandler("refer", self.refer))
        self.application.add_handler(CommandHandler("profile", self.profile))
        
        # Admin commands
        self.application.add_handler(CommandHandler("stats", self.admin_stats))
        self.application.add_handler(CommandHandler("broadcast", self.admin_broadcast))
        self.application.add_handler(CommandHandler("block", self.admin_block))
        self.application.add_handler(CommandHandler("unblock", self.admin_unblock))
        self.application.add_handler(CommandHandler("adminlist", self.admin_list))
        self.application.add_handler(CommandHandler("promote", self.admin_promote))
        self.application.add_handler(CommandHandler("remove", self.admin_remove))
        self.application.add_handler(CommandHandler("promotevip", self.admin_promote_vip))
        self.application.add_handler(CommandHandler("fjoin", self.admin_fjoin))
        self.application.add_handler(CommandHandler("removefjoin", self.admin_remove_fjoin))
        
        # Callback query handler
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Pre-checkout handler for payments
        self.application.add_handler(PreCheckoutQueryHandler(self.precheckout_callback))
        
        # Message handler for chat forwarding
        self.application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, self.handle_message))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        # Check if user already exists (to determine if they're new)
        existing_user = db.get_user(user.id)
        is_new_user = existing_user is None
        
        # Check for referral - only process for new users
        referred_by = None
        if is_new_user and context.args and len(context.args) > 0:
            try:
                referred_by = int(context.args[0])
                if referred_by != user.id:
                    # Give VIP to referrer for 24 hours
                    db.set_vip_status(referred_by, 1)
                    db.update_referral_count(referred_by)
                    
                    # Notify referrer
                    try:
                        await context.bot.send_message(
                            chat_id=referred_by,
                            text="🎉 Someone started the bot through your referral link! You've been granted VIP status for 24 hours."
                        )
                    except:
                        pass
            except ValueError:
                referred_by = None
        
        # Add user to database (or update if exists)
        db.add_user(user.id, user.username, user.first_name, user.last_name, referred_by)
        
        # Check if user already agreed to terms
        user_data = db.get_user(user.id)
        if user_data and bool(user_data['agreed_terms']):
            if bool(user_data['profile_completed']):
                await self.check_force_join_compliance(update, context)
            else:
                await self.setup_profile(update, context)
            return
        
        # Show Terms and Conditions
        keyboard = [
            [InlineKeyboardButton("✅ Agree", callback_data="terms_agree")],
            [InlineKeyboardButton("❌ Not Agree", callback_data="terms_disagree")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        terms_text = """
🤖 **Welcome to BoyGirlChatBot!**

**Terms and Conditions:**

1. This bot is for anonymous chatting between users
2. No inappropriate content or harassment allowed
3. Respect other users and maintain decency
4. Links are not allowed in chats
5. Users must join required groups to use the bot
6. Admin decisions are final
7. Bot logs messages for moderation purposes

By clicking "Agree", you accept these terms and conditions.
        """
        
        await update.message.reply_text(terms_text, reply_markup=reply_markup, parse_mode='Markdown')

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        
        if data == "terms_agree":
            db.update_user_terms(user_id, True)
            await query.edit_message_text("✅ Terms accepted! Now let's set up your profile.")
            await self.setup_profile(update, context)
            
        elif data == "terms_disagree":
            await query.edit_message_text("❌ You must agree to the terms to use this bot. Goodbye!")
            return
            
        elif data.startswith("gender_"):
            gender = data.split("_")[1]
            db.update_user_profile(user_id, gender=gender)
            await query.edit_message_text(f"✅ Gender set to: {gender}")
            await self.setup_country(update, context)
            
        elif data.startswith("country_"):
            country = data.split("_")[1]
            db.update_user_profile(user_id, country=country)
            await query.edit_message_text(f"✅ Country set to: {country}")
            await self.setup_age(update, context)
            
        elif data.startswith("age_"):
            age = int(data.split("_")[1])
            # Save age and mark profile as completed
            db.update_user_profile(user_id, age=age, profile_completed=True)
            await query.edit_message_text(f"✅ Age set to: {age}")
            await self.check_force_join_compliance(update, context)

            
        elif data == "vip_refer":
            await self.show_referral_info(update, context)
            
        elif data == "vip_purchase":
            await self.show_vip_purchase_options(update, context)
            
        elif data.startswith("buy_vip_"):
            days, stars = data.split("_")[2], int(data.split("_")[3])
            await self.process_vip_purchase(update, context, int(days), stars)
            
        elif data == "update_profile":
            await self.update_profile_menu(update, context)
            
        elif data == "partner_filter":
            user_data = db.get_user(user_id)
            if user_data and user_data['is_vip'] and user_data['vip_until'] and datetime.fromisoformat(str(user_data['vip_until'])) > datetime.now():
                await self.partner_filter_menu(update, context)
            else:
                await query.edit_message_text("🔒 This feature is only available for VIP users. Use /vip to get VIP status.")
                
        elif data.startswith("filter_"):
            gender_filter = data.split("_")[1] if data.split("_")[1] != "any" else None
            db.update_partner_filter(user_id, gender_filter)
            filter_text = gender_filter if gender_filter else "Any"
            await query.edit_message_text(f"✅ Partner filter set to: {filter_text}")
            
        elif data == "edit_gender":
            keyboard = [
                [InlineKeyboardButton("👨 Male", callback_data="update_gender_Male")],
                [InlineKeyboardButton("👩 Female", callback_data="update_gender_Female")],
                [InlineKeyboardButton("🔙 Back", callback_data="update_profile")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("🚹 **Select your gender:**", reply_markup=reply_markup, parse_mode='Markdown')
            
        elif data == "edit_country":
            keyboard = [
                [InlineKeyboardButton("🇵🇰 Pakistan", callback_data="update_country_Pakistan")],
                [InlineKeyboardButton("🇮🇳 India", callback_data="update_country_India")],
                [InlineKeyboardButton("🇺🇸 USA", callback_data="update_country_USA")],
                [InlineKeyboardButton("🇬🇧 UK", callback_data="update_country_UK")],
                [InlineKeyboardButton("🇨🇦 Canada", callback_data="update_country_Canada")],
                [InlineKeyboardButton("🌍 Other", callback_data="update_country_Other")],
                [InlineKeyboardButton("🔙 Back", callback_data="update_profile")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("🌍 **Select your country:**", reply_markup=reply_markup, parse_mode='Markdown')
            
        elif data == "edit_age":
            keyboard = []
            for age in range(18, 36, 2):
                keyboard.append([InlineKeyboardButton(f"{age}-{age+1}", callback_data=f"update_age_{age}")])
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="update_profile")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("🎂 **Select your age group:**", reply_markup=reply_markup, parse_mode='Markdown')
            
        elif data.startswith("update_gender_"):
            new_gender = data.split("_")[2]
            db.update_user_profile(user_id, gender=new_gender)
            await query.edit_message_text(f"✅ Gender updated to: {new_gender}")
            
        elif data.startswith("update_country_"):
            new_country = data.split("_")[2]
            db.update_user_profile(user_id, country=new_country)
            await query.edit_message_text(f"✅ Country updated to: {new_country}")
            
        elif data.startswith("update_age_"):
            new_age = int(data.split("_")[2])
            db.update_user_profile(user_id, age=new_age)
            await query.edit_message_text(f"✅ Age updated to: {new_age}")
            
        elif data == "back_to_profile":
            keyboard = [
                [InlineKeyboardButton("✏️ Update Profile", callback_data="update_profile")],
                [InlineKeyboardButton("🔍 Partner Filter (VIP)", callback_data="partner_filter")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("👤 **Profile Options:**", reply_markup=reply_markup, parse_mode='Markdown')
            
        # New gender-based matching callbacks
        elif data == "match_girls":
            user_data = db.get_user(user_id)
            if user_data and user_data['is_vip'] and user_data['vip_until'] and datetime.fromisoformat(str(user_data['vip_until'])) > datetime.now():
                await self.find_chat_partner_by_gender(update, context, "Female")
            else:
                await query.edit_message_text("🔒 This feature is only available for VIP users. Use /vip to get VIP status.")
                
        elif data == "match_boys":
            user_data = db.get_user(user_id)
            if user_data and user_data['is_vip'] and user_data['vip_until'] and datetime.fromisoformat(str(user_data['vip_until'])) > datetime.now():
                await self.find_chat_partner_by_gender(update, context, "Male")
            else:
                await query.edit_message_text("🔒 This feature is only available for VIP users. Use /vip to get VIP status.")
                
        elif data == "match_random":
            await self.find_chat_partner_by_gender(update, context, None)

    async def setup_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("👨 Male", callback_data="gender_Male")],
            [InlineKeyboardButton("👩 Female", callback_data="gender_Female")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query and update.callback_query.message:
            await update.callback_query.message.reply_text("👤 Please select your gender:", reply_markup=reply_markup)
        elif update.message:
            await update.message.reply_text("👤 Please select your gender:", reply_markup=reply_markup)

    async def setup_country(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("🇺🇸 USA", callback_data="country_USA"), InlineKeyboardButton("🇬🇧 UK", callback_data="country_UK")],
            [InlineKeyboardButton("🇮🇳 India", callback_data="country_India"), InlineKeyboardButton("🇨🇦 Canada", callback_data="country_Canada")],
            [InlineKeyboardButton("🇦🇺 Australia", callback_data="country_Australia"), InlineKeyboardButton("🇩🇪 Germany", callback_data="country_Germany")],
            [InlineKeyboardButton("🇫🇷 France", callback_data="country_France"), InlineKeyboardButton("🇯🇵 Japan", callback_data="country_Japan")],
            [InlineKeyboardButton("🌍 Other", callback_data="country_Other")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query and update.callback_query.message:
            await update.callback_query.message.reply_text("🌍 Please select your country:", reply_markup=reply_markup)
        elif update.message:
            await update.message.reply_text("🌍 Please select your country:", reply_markup=reply_markup)

    async def setup_age(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("18-25", callback_data="age_22"), InlineKeyboardButton("26-35", callback_data="age_30")],
            [InlineKeyboardButton("36-45", callback_data="age_40"), InlineKeyboardButton("46+", callback_data="age_50")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query and update.callback_query.message:
            await update.callback_query.message.reply_text("📅 Please select your age group:", reply_markup=reply_markup)
        elif update.message:
            await update.message.reply_text("📅 Please select your age group:", reply_markup=reply_markup)

    async def check_force_join_compliance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        force_join_groups = db.get_force_join_groups()
        user_id = update.effective_user.id
        
        if not force_join_groups:
            await self.show_main_menu(update, context)
            return
        
        non_member_groups = []
        for group in force_join_groups:
            try:
                member = await context.bot.get_chat_member(group['group_id'], user_id)
                if member.status in ['left', 'kicked']:
                    non_member_groups.append(group)
            except:
                non_member_groups.append(group)
        
        if non_member_groups:
            keyboard = []
            for group in non_member_groups:
                try:
                    # Validate URL format
                    group_link = group['group_link']
                    if group_link.startswith('@'):
                        group_link = f"https://t.me/{group_link[1:]}"
                    elif not group_link.startswith('http'):
                        group_link = f"https://t.me/{group_link}"
                    
                    keyboard.append([InlineKeyboardButton(f"Join Group {len(keyboard)+1}", url=group_link)])
                except:
                    # Skip invalid groups
                    continue
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            message_text = "🔒 You must join all required groups to use this bot:"
            
            if update.callback_query and update.callback_query.message:
                await update.callback_query.message.reply_text(message_text, reply_markup=reply_markup)
            elif update.message:
                await update.message.reply_text(message_text, reply_markup=reply_markup)
        else:
            await self.show_main_menu(update, context)

    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message_text = """
🤖 **Welcome to BoysGirlsChatBot!**

Available commands:
🗨️ /chat - Find a random chat partner
🛑 /end - End current chat session
👑 /vip - Get VIP status
🔗 /refer - View your referral link
👤 /profile - Update profile or set partner filter

Enjoy chatting anonymously!
        """
        
        if update.callback_query and update.callback_query.message:
            await update.callback_query.message.reply_text(message_text, parse_mode='Markdown')
        elif update.message:
            await update.message.reply_text(message_text, parse_mode='Markdown')

    async def chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        # Check user eligibility
        if not await self.check_user_eligibility(update, context):
            return
        
        user_data = db.get_user(user_id)
        
        # Check if already in chat
        if user_data['chat_partner']:
            await update.message.reply_text("❌ You are already in a chat session. Use /end to end current session.")
            return
        
        # Show gender-based matching options
        keyboard = [
            [InlineKeyboardButton("👩 Match with Girls (VIP)", callback_data="match_girls")],
            [InlineKeyboardButton("👨 Match with Boys (VIP)", callback_data="match_boys")],
            [InlineKeyboardButton("🎲 Match Randomly (Free)", callback_data="match_random")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text("🔍 **Choose your matching preference:**", reply_markup=reply_markup, parse_mode='Markdown')

    async def find_chat_partner_by_gender(self, update: Update, context: ContextTypes.DEFAULT_TYPE, gender_filter):
        user_id = update.effective_user.id if update.effective_user else update.callback_query.from_user.id
        
        user_data = db.get_user(user_id)
        
        # Check if already in chat
        if user_data['chat_partner']:
            message = "❌ You are already in a chat session. Use /end to end current session."
            if update.callback_query:
                await update.callback_query.edit_message_text(message)
            else:
                await update.message.reply_text(message)
            return
        
        # Mark user as looking for chat
        db.set_user_looking_for_chat(user_id, True)
        
        # Find partner
        partner_id = db.find_chat_partner_by_gender(user_id, gender_filter)
        
        if not partner_id:
            message = "⏳ Looking for a chat partner... Please try again in a moment."
            if update.callback_query:
                await update.callback_query.edit_message_text(message)
            else:
                await update.message.reply_text(message)
            return
        
        # Start chat session
        db.start_chat_session(user_id, partner_id)
        
        # Get partner info
        partner_data = db.get_user(partner_id)
        
        # Notify both users
        user_message = f"🎉 Chat partner found!\n👤 Gender: {partner_data['gender']}\n📅 Age: {partner_data['age']}\n\nYou can now start chatting!"
        partner_message = f"🎉 Chat partner found!\n👤 Gender: {user_data['gender']}\n📅 Age: {user_data['age']}\n\nYou can now start chatting!"
        
        if update.callback_query:
            await update.callback_query.edit_message_text(user_message)
        else:
            await update.message.reply_text(user_message)
        await context.bot.send_message(chat_id=partner_id, text=partner_message)

    async def end_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if not await self.check_user_eligibility(update, context):
            return
        
        partner_id = db.end_chat_session(user_id)
        
        if partner_id:
            await update.message.reply_text("✅ Chat session ended. Use /chat to find a new partner.")
            await context.bot.send_message(chat_id=partner_id, text="❌ Your chat partner has ended the session. Use /chat to find a new partner.")
        else:
            await update.message.reply_text("❌ You are not currently in a chat session.")

    async def vip(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_user_eligibility(update, context):
            return
        
        keyboard = [
            [InlineKeyboardButton("🔗 Refer friends and earn VIP", callback_data="vip_refer")],
            [InlineKeyboardButton("💎 Purchase VIP", callback_data="vip_purchase")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text("👑 **VIP Membership Options:**", reply_markup=reply_markup, parse_mode='Markdown')

    async def show_referral_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id if update.effective_user else update.callback_query.from_user.id
        user_data = db.get_user(user_id)
        
        referral_link = f"https://t.me/BoysGirlsChatBot?start={user_id}"
        message_text = f"""
🔗 **Your Referral Link:**
{referral_link}

📊 **Referral Stats:**
👥 People referred: {user_data['referral_count']}

💡 **How it works:**
• Share your referral link with friends
• When someone starts the bot through your link, you get VIP for 24 hours
• No limit on referrals!
        """
        
        if update.callback_query:
            await update.callback_query.edit_message_text(message_text, parse_mode='Markdown')
        elif update.message:
            await update.message.reply_text(message_text, parse_mode='Markdown')

    async def show_vip_purchase_options(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("1 Day - 10 ⭐", callback_data="buy_vip_1_10")],
            [InlineKeyboardButton("5 Days - 25 ⭐", callback_data="buy_vip_5_25")],
            [InlineKeyboardButton("12 Days - 50 ⭐", callback_data="buy_vip_12_50")],
            [InlineKeyboardButton("1 Months - 100 ⭐", callback_data="buy_vip_30_100")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = "💎 **VIP Purchase Options:**\n\nSelect your preferred VIP duration:"
        
        if update.callback_query:
            await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')
        elif update.message:
            await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')

    async def process_vip_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE, days: int, stars: int):
        user_id = update.effective_user.id if update.effective_user else update.callback_query.from_user.id
        
        # Create invoice
        title = f"VIP Membership - {days} Days"
        description = f"Get VIP access for {days} days with exclusive features"
        payload = f"vip_{days}_{user_id}"
        currency = "XTR"  # Telegram Stars
        prices = [LabeledPrice("VIP Membership", stars)]
        
        await context.bot.send_invoice(
            chat_id=user_id,
            title=title,
            description=description,
            payload=payload,
            provider_token="",
            currency=currency,
            prices=prices
        )

    async def precheckout_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.pre_checkout_query
        
        # Check if payload is valid
        if query.invoice_payload.startswith("vip_"):
            await query.answer(ok=True)
            
            # Process payment
            payload_parts = query.invoice_payload.split("_")
            days = int(payload_parts[1])
            user_id = int(payload_parts[2])
            
            # Grant VIP status
            db.set_vip_status(user_id, days)
            
            # Send confirmation
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🎉 Payment successful! You now have VIP access for {days} days."
            )
        else:
            await query.answer(ok=False, error_message="Invalid payment")

    async def refer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.show_referral_info(update, context)

    async def profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.check_user_eligibility(update, context):
            return
        
        keyboard = [
            [InlineKeyboardButton("✏️ Update Profile", callback_data="update_profile")],
            [InlineKeyboardButton("🔍 Partner Filter (VIP)", callback_data="partner_filter")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text("👤 **Profile Options:**", reply_markup=reply_markup, parse_mode='Markdown')

    async def update_profile_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("🚹 Change Gender", callback_data="edit_gender")],
            [InlineKeyboardButton("🌍 Change Country", callback_data="edit_country")],
            [InlineKeyboardButton("🎂 Change Age", callback_data="edit_age")],
            [InlineKeyboardButton("🔙 Back to Profile", callback_data="back_to_profile")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text("✏️ **Choose what to update:**", reply_markup=reply_markup, parse_mode='Markdown')
        elif update.message:
            await update.message.reply_text("✏️ **Choose what to update:**", reply_markup=reply_markup, parse_mode='Markdown')

    async def partner_filter_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("🧑🏻‍🦰 Male Only", callback_data="filter_Male")],
            [InlineKeyboardButton("👱🏻‍♀ Female Only", callback_data="filter_Female")],
            [InlineKeyboardButton("🔄 Any Gender", callback_data="filter_any")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text("🔍 **Select Partner Filter:**", reply_markup=reply_markup, parse_mode='Markdown')
        elif update.message:
            await update.message.reply_text("🔍 **Select Partner Filter:**", reply_markup=reply_markup, parse_mode='Markdown')

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if not await self.check_user_eligibility(update, context):
            return
        
        user_data = db.get_user(user_id)
        
        if not user_data['chat_partner']:
            await update.message.reply_text("❌ You are not in a chat session. Use /chat to find a partner.")
            return
        
        partner_id = user_data['chat_partner']
        
        # Check for links
        if update.message.text and any(url in update.message.text.lower() for url in ['http', 'www.', '.com', '.org', '.net']):
            await update.message.reply_text("❌ Links are not allowed in chats.")
            return
        
        # Forward message to partner
        try:
            if update.message.text:
                await context.bot.send_message(chat_id=partner_id, text=update.message.text)
                db.log_message(user_id, partner_id, "text", update.message.text)
                await self.log_to_group(context, user_id, partner_id, "text", update.message.text)
                
            elif update.message.photo:
                photo_file_id = update.message.photo[-1].file_id
                await context.bot.send_photo(chat_id=partner_id, photo=photo_file_id, caption=update.message.caption)
                db.log_message(user_id, partner_id, "photo", update.message.caption or "Photo")
                await self.log_to_group(context, user_id, partner_id, "photo", "Photo", file_id=photo_file_id, caption=update.message.caption)
                
            elif update.message.video:
                video_file_id = update.message.video.file_id
                await context.bot.send_video(chat_id=partner_id, video=video_file_id, caption=update.message.caption)
                db.log_message(user_id, partner_id, "video", update.message.caption or "Video")
                await self.log_to_group(context, user_id, partner_id, "video", "Video", file_id=video_file_id, caption=update.message.caption)
                
            elif update.message.sticker:
                sticker_file_id = update.message.sticker.file_id
                await context.bot.send_sticker(chat_id=partner_id, sticker=sticker_file_id)
                db.log_message(user_id, partner_id, "sticker", "Sticker")
                await self.log_to_group(context, user_id, partner_id, "sticker", "Sticker", file_id=sticker_file_id)
                
            elif update.message.voice:
                voice_file_id = update.message.voice.file_id
                await context.bot.send_voice(chat_id=partner_id, voice=voice_file_id)
                db.log_message(user_id, partner_id, "voice", "Voice message")
                await self.log_to_group(context, user_id, partner_id, "voice", "Voice message", file_id=voice_file_id)
                
        except Exception as e:
            logger.error(f"Error forwarding message: {e}")
            await update.message.reply_text("❌ Failed to send message. Your partner may have left the chat.")

    async def log_to_group(self, context: ContextTypes.DEFAULT_TYPE, sender_id: int, receiver_id: int, message_type: str, content: str, file_id=None, caption=None):
        try:
            sender_data = db.get_user(sender_id)
            receiver_data = db.get_user(receiver_id)
            
            log_header = f"""📝 Message Log
👤 Sender: {sender_id} (@{sender_data['username'] or 'N/A'}) - {sender_data['gender']}
👤 Receiver: {receiver_id} (@{receiver_data['username'] or 'N/A'}) - {receiver_data['gender']}
⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
            
            # Send actual content based on message type
            if message_type == "text":
                full_message = f"""{log_header}
📱 Type: Text Message
💬 Content: {content}"""
                await context.bot.send_message(chat_id=LOG_GROUP_ID, text=full_message)
                
            elif message_type == "photo" and file_id:
                await context.bot.send_photo(
                    chat_id=LOG_GROUP_ID, 
                    photo=file_id, 
                    caption=f"""{log_header}
📱 Type: Photo
💬 Caption: {caption or 'No caption'}"""
                )
                
            elif message_type == "video" and file_id:
                await context.bot.send_video(
                    chat_id=LOG_GROUP_ID, 
                    video=file_id, 
                    caption=f"""{log_header}
📱 Type: Video
💬 Caption: {caption or 'No caption'}"""
                )
                
            elif message_type == "sticker" and file_id:
                await context.bot.send_sticker(chat_id=LOG_GROUP_ID, sticker=file_id)
                await context.bot.send_message(
                    chat_id=LOG_GROUP_ID, 
                    text=f"""{log_header}
📱 Type: Sticker"""
                )
                
            elif message_type == "voice" and file_id:
                await context.bot.send_voice(chat_id=LOG_GROUP_ID, voice=file_id)
                await context.bot.send_message(
                    chat_id=LOG_GROUP_ID, 
                    text=f"""{log_header}
📱 Type: Voice Message"""
                )
                
            else:
                # Fallback for other types
                full_message = f"""{log_header}
📱 Type: {message_type}
💬 Content: {content}"""
                await context.bot.send_message(chat_id=LOG_GROUP_ID, text=full_message)
                
        except Exception as e:
            logger.error(f"Error logging to group: {e}")

    async def check_user_eligibility(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        user_data = db.get_user(user_id)
        
        if not user_data:
            await update.message.reply_text("❌ Please start the bot first with /start")
            return False
        
        # Normalize boolean values to handle SQLite (0/1) vs PostgreSQL (bool) differences
        is_blocked = bool(user_data['is_blocked'])
        agreed_terms = bool(user_data['agreed_terms'])
        profile_completed = bool(user_data['profile_completed'])
        
        if is_blocked:
            await update.message.reply_text("❌ You are blocked from using this bot.")
            return False
        
        if not agreed_terms:
            await update.message.reply_text("❌ Please agree to terms first with /start")
            return False
        
        if not profile_completed:
            await update.message.reply_text("❌ Please complete your profile first.")
            return False
        
        # Check VIP expiry
        db.check_vip_expired(user_id)
        
        # Check force join compliance
        force_join_groups = db.get_force_join_groups()
        for group in force_join_groups:
            try:
                member = await context.bot.get_chat_member(group['group_id'], user_id)
                if member.status in ['left', 'kicked']:
                    await self.check_force_join_compliance(update, context)
                    return False
            except:
                await self.check_force_join_compliance(update, context)
                return False
        
        return True

    # Admin commands
    async def admin_promote_vip(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if not db.is_admin(user_id):
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        if len(context.args) != 2:
            await update.message.reply_text("❌ Usage: /promotevip <user_id> <duration_in_days>")
            return
        
        try:
            target_user_id = int(context.args[0])
            duration = int(context.args[1])
            
            if duration <= 0:
                await update.message.reply_text("❌ Duration must be greater than 0.")
                return
            
            # Check if target user exists
            target_user = db.get_user(target_user_id)
            if not target_user:
                await update.message.reply_text("❌ User not found in database.")
                return
            
            # Grant VIP status
            db.set_vip_status(target_user_id, duration)
            
            # Notify admin
            await update.message.reply_text(f"✅ User {target_user_id} has been granted VIP status for {duration} days.")
            
            # Notify user
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"🎉 You have been granted VIP status for {duration} days by an admin!"
                )
            except:
                pass
                
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID or duration. Both must be numbers.")

    async def admin_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not db.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        stats = db.get_detailed_stats()
        force_join_groups = db.get_force_join_groups()
        
        stats_message = f"""
📊 **Detailed Bot Statistics**

👥 **User Statistics:**
• Total Users: {stats['total_users']}
• 👨 Male Users: {stats['male_users']}
• 👩 Female Users: {stats['female_users']}
• ✅ Completed Profiles: {stats['completed_profiles']}
• ❌ Blocked Users: {stats['blocked_users']}

🟢 **Live Users (Currently Active):**
• 👨 Live Male Users: {stats['live_male_users']}
• 👩 Live Female Users: {stats['live_female_users']}
• 📱 Total Live Users: {stats['live_male_users'] + stats['live_female_users']}

💬 **Chat Statistics:**
• Active Chat Sessions: {stats['active_chats']}
• Total Messages Sent: {stats['total_messages']}

👑 **Premium Statistics:**
• VIP Users: {stats['vip_users']}
• Total Referrals Made: {stats['total_referrals']}

🔒 **System Settings:**
• Force Join Groups: {len(force_join_groups)}

⏰ **Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        await update.message.reply_text(stats_message, parse_mode='Markdown')

    async def admin_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not db.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        if not update.message.reply_to_message:
            await update.message.reply_text("❌ Please reply to a message to broadcast it.")
            return
        
        users = db.get_all_users()
        sent_count = 0
        
        await update.message.reply_text(f"📢 Starting broadcast to {len(users)} users...")
        
        for user in users:
            try:
                await context.bot.copy_message(
                    chat_id=user['user_id'],
                    from_chat_id=update.message.chat_id,
                    message_id=update.message.reply_to_message.message_id
                )
                sent_count += 1
            except:
                continue
        
        await update.message.reply_text(f"✅ Broadcast completed! Sent to {sent_count}/{len(users)} users.")

    async def admin_block(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not db.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        if not context.args:
            await update.message.reply_text("❌ Please provide user ID. Usage: /block <user_id>")
            return
        
        try:
            user_id = int(context.args[0])
            db.block_user(user_id)
            await update.message.reply_text(f"✅ User {user_id} has been blocked.")
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.")

    async def admin_unblock(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not db.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        if not context.args:
            await update.message.reply_text("❌ Please provide user ID. Usage: /unblock <user_id>")
            return
        
        try:
            user_id = int(context.args[0])
            db.unblock_user(user_id)
            await update.message.reply_text(f"✅ User {user_id} has been unblocked.")
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.")

    async def admin_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not db.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        admins = db.get_admins()
        
        if not admins:
            await update.message.reply_text("❌ No admins found.")
            return
        
        admin_list = "👑 **Admin List:**\n\n"
        for admin in admins:
            admin_list += f"• {admin['user_id']}\n"
        
        await update.message.reply_text(admin_list, parse_mode='Markdown')

    async def admin_promote(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not db.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        if not context.args:
            await update.message.reply_text("❌ Please provide user ID. Usage: /promote <user_id>")
            return
        
        try:
            user_id = int(context.args[0])
            db.add_admin(user_id, update.effective_user.id)
            await update.message.reply_text(f"✅ User {user_id} has been promoted to admin.")
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.")

    async def admin_remove(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not db.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        if not context.args:
            await update.message.reply_text("❌ Please provide user ID. Usage: /remove <user_id>")
            return
        
        try:
            user_id = int(context.args[0])
            if user_id == INITIAL_ADMIN_ID:
                await update.message.reply_text("❌ Cannot remove the initial admin.")
                return
            
            db.remove_admin(user_id)
            await update.message.reply_text(f"✅ User {user_id} has been removed from admin.")
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID.")

    async def admin_fjoin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not db.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        if not context.args:
            await update.message.reply_text("❌ Please provide group link. Usage: /fjoin <group_link>")
            return
        
        group_link = context.args[0]
        
        # Extract group ID from link
        try:
            if "joinchat" in group_link:
                await update.message.reply_text("❌ Please provide a public group link (not invite link).")
                return
            
            if "@" in group_link:
                group_username = group_link.split("@")[-1]
                chat = await context.bot.get_chat(f"@{group_username}")
                group_id = chat.id
            else:
                await update.message.reply_text("❌ Invalid group link format.")
                return
            
            db.add_force_join_group(group_id, group_link, update.effective_user.id)
            await update.message.reply_text(f"✅ Group added to force join list: {group_link}")
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error adding group: {str(e)}")

    async def admin_remove_fjoin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not db.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        if not context.args:
            await update.message.reply_text("❌ Please provide group ID or link. Usage: /removefjoin <group_id_or_link>")
            return
        
        try:
            # Try as group ID first
            group_id = int(context.args[0])
        except ValueError:
            # Try as group link
            group_link = context.args[0]
            try:
                if "@" in group_link:
                    group_username = group_link.split("@")[-1]
                    chat = await context.bot.get_chat(f"@{group_username}")
                    group_id = chat.id
                else:
                    await update.message.reply_text("❌ Invalid group ID or link format.")
                    return
            except:
                await update.message.reply_text("❌ Could not find group.")
                return
        
        db.remove_force_join_group(group_id)
        await update.message.reply_text(f"✅ Group {group_id} removed from force join list.")

    def run(self):
        self.application.run_polling()

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("BOT_TOKEN environment variable is required!")
        exit(1)
    
    bot = TelegramBot()
    print("Bot is starting...")
    bot.run()
