import requests
import qrcode
import time
import json
import re
import asyncio
import signal
import sys
import os
import threading
import random
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta, time as dt_time
from qrcode import QRCode
from PIL import Image
import io
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import logging
import pytz
from supabase import create_client, Client
import cloudscraper
from fake_useragent import UserAgent

# ==================== HEALTH CHECK SERVER (for Render) ====================

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK - Bot is running')
    
    def log_message(self, format, *args):
        pass  # Suppress HTTP logs

def start_health_server():
    """Start health check HTTP server for Render"""
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    logger.info(f"Health check server started on port {port}")
    server.serve_forever()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================

# Telegram Bot Token
BOT_TOKEN = "8419074330:AAH6_JD6tHhZKt2Gc5iLQibkwc8nzKNIB6k"

# Admin Telegram User ID
ADMIN_USER_ID = 7325836764

# Supabase Configuration
SUPABASE_URL = "https://sgnnqvfoajqsfdyulolm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNnbm5xdmZvYWpxc2ZkeXVsb2xtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQxNzE1MjcsImV4cCI6MjA3OTc0NzUyN30.dFniV0odaT-7bjs5iQVFQ-N23oqTGMAgQKjswhaHSP4"

# SOCKS5 Proxy Configuration
PROXY_HOST = "103.166.187.88"
PROXY_PORT = 11311
PROXY_USER = "NextG"
PROXY_PASS = "NextG"
PROXY_URL = f"socks5://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"

# Bangladesh Timezone
BD_TIMEZONE = pytz.timezone('Asia/Dhaka')

# Earnings per completed number (in Taka)
EARNINGS_PER_NUMBER = 10.00

# Time restrictions (Bangladesh Time)
WORK_START_HOUR = 10  # 10:30 AM
WORK_START_MINUTE = 30
WORK_END_HOUR = 7  # 7:00 AM next day
WORK_END_MINUTE = 0
DAILY_RESET_HOUR = 8  # 8:00 AM
DAILY_RESET_MINUTE = 0
ADMIN_REPORT_HOUR = 15  # 3:00 PM
ADMIN_REPORT_MINUTE = 0

# ==================== KEYBOARD BUTTONS ====================

# User Menu Buttons
BTN_MY_STATS = "📊 My Stats"
BTN_HELP = "❓ Help"
BTN_WORKING_HOURS = "⏰ Working Hours"

# Admin Menu Buttons
BTN_ADMIN_REPORT = "📊 Today's Report"
BTN_ADMIN_USERS = "👥 All Users"
BTN_ADMIN_PENDING = "⏳ Pending Users"
BTN_ADMIN_STATS = "📈 Total Stats"

# ==================== KEYBOARDS ====================

def get_user_keyboard():
    """Get user reply keyboard"""
    keyboard = [
        [KeyboardButton(BTN_MY_STATS), KeyboardButton(BTN_WORKING_HOURS)],
        [KeyboardButton(BTN_HELP)]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)

def get_admin_keyboard():
    """Get admin reply keyboard"""
    keyboard = [
        [KeyboardButton(BTN_MY_STATS), KeyboardButton(BTN_ADMIN_REPORT)],
        [KeyboardButton(BTN_ADMIN_USERS), KeyboardButton(BTN_ADMIN_PENDING)],
        [KeyboardButton(BTN_ADMIN_STATS), KeyboardButton(BTN_WORKING_HOURS)],
        [KeyboardButton(BTN_HELP)]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)

def get_pending_keyboard():
    """Get keyboard for pending users"""
    keyboard = [
        [KeyboardButton(BTN_HELP)]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)

# ==================== SUPABASE CLIENT ====================

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Website configurations
WEBSITES = [
    {
        "name": "EarnBro",
        "base_url": "https://earnbro.net/pl3/2/ws",
        "code": "4CWA4HVE",
        "url": "https://earnbro.net/#/pages/gs/log?id=4CWA4HVE"
    },
    {
        "name": "ZapKaro",
        "base_url": "https://zapkaroapp.com/pl3/2/ws",
        "code": "R7XAR4HV",
        "url": "https://zapkaroapp.com/#/pages/gs/log?id=R7XAR4HV"
    },
    {
        "name": "CoinZa",
        "base_url": "https://coinzaapp.com/pl3/2/ws",
        "code": "972A9WYL",
        "url": "https://coinzaapp.com/#/pages/gs/log?id=972A9WYL"
    },
    {
        "name": "Kamate",
        "base_url": "https://kamate1.com/pl3/2/ws",
        "code": "p5dmet",
        "url": "https://kamate1.com/#/pages/gs/log?id=p5dmet"
    }
]

# Store active sessions per user with unique QR data
# Format: {user_id: {website_index: {"qr_token": str, "scraper": scraper_instance}}}
user_qr_sessions = {}

# Browser Profiles - Separate session for each user (like browser profiles)
# Each user gets their own isolated session with unique cookies, headers, fingerprint
# Format: {user_id: {"scraper": scraper, "fingerprint": str, "created_at": timestamp}}
user_browser_profiles = {}

# Website locks - only ONE user can scan each website at a time
# Format: {website_index: {"user_id": int, "phone": str, "locked_at": timestamp}}
website_locks = {}

# Queue for users waiting to scan a website
# Format: {website_index: [(user_id, phone, context), ...]}
website_queue = {0: [], 1: [], 2: [], 3: []}

import hashlib
import uuid

def generate_browser_fingerprint(user_id):
    """Generate a unique browser fingerprint for each user"""
    unique_string = f"{user_id}-{uuid.uuid4()}-{time.time()}"
    fingerprint = hashlib.md5(unique_string.encode()).hexdigest()[:16]
    return fingerprint

def get_user_browser_profile(user_id):
    """Get or create a unique browser profile for a user (like Chrome profiles)"""
    
    # Check if user already has a profile and it's not too old (max 1 hour)
    if user_id in user_browser_profiles:
        profile = user_browser_profiles[user_id]
        age = time.time() - profile.get("created_at", 0)
        if age < 3600:  # Profile valid for 1 hour
            logger.info(f"[PROFILE] Reusing existing browser profile for user {user_id}")
            return profile["scraper"], profile["fingerprint"]
    
    # Create new browser profile
    fingerprint = generate_browser_fingerprint(user_id)
    
    # Create scraper with unique browser signature
    browsers = ['chrome', 'firefox']
    platforms = ['windows', 'linux', 'darwin']
    
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': random.choice(browsers),
            'platform': random.choice(platforms),
            'mobile': False
        },
        delay=random.uniform(1, 2)
    )
    
    # Set proxy
    scraper.proxies = {
        'http': PROXY_URL,
        'https': PROXY_URL
    }
    
    # Store profile
    user_browser_profiles[user_id] = {
        "scraper": scraper,
        "fingerprint": fingerprint,
        "created_at": time.time()
    }
    
    logger.info(f"[PROFILE] Created NEW browser profile for user {user_id}, fingerprint: {fingerprint}")
    return scraper, fingerprint

def get_user_headers(user_id, website, fingerprint):
    """Generate unique headers for each user's browser profile"""
    base_url = website.get('base_url', '')
    domain = website.get('domain', base_url.split('/')[2] if '//' in base_url else '')
    
    # Use fingerprint to create consistent but unique headers per user
    user_agent_seed = int(fingerprint[:8], 16) % 100
    
    user_agents = [
        f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{120 + user_agent_seed % 10}.0.0.0 Safari/537.36",
        f"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{115 + user_agent_seed % 10}.0) Gecko/20100101 Firefox/{115 + user_agent_seed % 10}.0",
        f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{120 + user_agent_seed % 10}.0.0.0 Safari/537.36",
    ]
    
    selected_ua = user_agents[user_agent_seed % len(user_agents)]
    
    return {
        "content-type": "application/json",
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-US,en;q=0.9",
        "user-agent": selected_ua,
        "origin": base_url.rsplit('/', 3)[0] if base_url else "",
        "referer": website.get('url', base_url),
        "sec-ch-ua": f'"Chromium";v="{120 + user_agent_seed % 10}", "Not_A Brand";v="8"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "x-client-id": fingerprint,  # Unique identifier per user
        "x-request-id": str(uuid.uuid4()),  # Unique per request
    }

def reset_user_browser_profile(user_id):
    """Reset/delete a user's browser profile to start fresh"""
    if user_id in user_browser_profiles:
        del user_browser_profiles[user_id]
        logger.info(f"[PROFILE] Reset browser profile for user {user_id}")

def is_website_locked(website_index):
    """Check if a website is currently locked by another user"""
    if website_index not in website_locks:
        return False, None
    
    lock = website_locks[website_index]
    # Auto-expire locks after 3 minutes (180 seconds)
    if time.time() - lock.get("locked_at", 0) > 180:
        del website_locks[website_index]
        return False, None
    
    return True, lock

def lock_website(website_index, user_id, phone):
    """Lock a website for exclusive use by a user"""
    website_locks[website_index] = {
        "user_id": user_id,
        "phone": phone,
        "locked_at": time.time()
    }
    logger.info(f"[LOCK] Website {website_index} locked by user {user_id} for phone {phone}")

def unlock_website(website_index, user_id=None):
    """Unlock a website (only if locked by the same user, or force unlock)"""
    if website_index in website_locks:
        lock = website_locks[website_index]
        if user_id is None or lock.get("user_id") == user_id:
            del website_locks[website_index]
            logger.info(f"[UNLOCK] Website {website_index} unlocked")
            return True
    return False

def get_lock_owner(website_index):
    """Get the user who currently has the website locked"""
    if website_index in website_locks:
        return website_locks[website_index].get("user_id")
    return None

# Headers for API requests
HEADERS = {
    "content-type": "application/json",
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "authorization": "Bearer null",
    "origin": "https://earnbro.net",
    "referer": "https://earnbro.net/"
}

# User session data (in-memory cache)
user_sessions = {}
user_completed_websites = {}

# ==================== HELPER FUNCTIONS ====================

def get_bd_time():
    """Get current Bangladesh time"""
    return datetime.now(BD_TIMEZONE)

def get_bd_date():
    """Get current Bangladesh date"""
    return get_bd_time().date()

def is_within_working_hours():
    """Check if current time is within working hours (10:30 AM - 7:00 AM next day)"""
    now = get_bd_time()
    current_time = now.time()
    
    # Working hours: 10:30 AM to 7:00 AM next day
    # This means NOT working: 7:00 AM to 10:30 AM
    start_break = dt_time(7, 0)  # 7:00 AM
    end_break = dt_time(10, 30)  # 10:30 AM
    
    # If current time is between 7:00 AM and 10:30 AM, not working
    if start_break <= current_time < end_break:
        return False
    
    return True

def get_working_hours_message():
    """Get message about working hours"""
    return (
        "⏰ Working hours ended!\n\n"
        "📅 Working Schedule:\n"
        "• 10:30 AM to 7:00 AM (next day)\n\n"
        "⏳ Please try again after 10:30 AM."
    )

def normalize_phone_number(phone):
    """
    Normalize phone number to standard format: +XXXXXXXXXXX
    Accepts any format: (123) 456-7890, 123-456-7890, +1 234 567 890, etc.
    Returns: +15067898784 format
    """
    if not phone:
        return None
    
    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d]', '', str(phone))
    
    if not cleaned or len(cleaned) < 10:
        return None
    
    # Handle different country codes
    # Bangladesh numbers (starts with 01, 11 digits like 01738791149)
    if cleaned.startswith('01') and len(cleaned) == 11:
        return f"+88{cleaned}"
    
    # Bangladesh with country code but no + (8801738791149)
    if cleaned.startswith('880') and len(cleaned) == 13:
        return f"+{cleaned}"
    
    # India numbers (starts with 0, remove leading 0)
    if cleaned.startswith('0') and len(cleaned) == 11:
        return f"+91{cleaned[1:]}"
    
    # India with country code (91XXXXXXXXXX)
    if cleaned.startswith('91') and len(cleaned) == 12:
        return f"+{cleaned}"
    
    # US/Canada numbers (10 digits)
    if len(cleaned) == 10:
        return f"+1{cleaned}"
    
    # US/Canada with country code (1XXXXXXXXXX)
    if cleaned.startswith('1') and len(cleaned) == 11:
        return f"+{cleaned}"
    
    # For other international numbers, just add + if not present
    if len(cleaned) >= 10:
        return f"+{cleaned}"
    
    return None


def format_phone_number(phone):
    """Format phone number for display (with spaces for readability)"""
    if not phone:
        return phone
    
    # If already normalized, format for display
    if phone.startswith('+'):
        # Remove + for processing
        digits = phone[1:]
        
        # Bangladesh format: +88 01XX XXX XXXX
        if digits.startswith('880') and len(digits) == 13:
            return f"+88 {digits[2:6]} {digits[6:9]} {digits[9:]}"
        
        # US/Canada format: +1 XXX XXX XXXX
        if digits.startswith('1') and len(digits) == 11:
            return f"+1 {digits[1:4]} {digits[4:7]} {digits[7:]}"
        
        # India format: +91 XXXXX XXXXX
        if digits.startswith('91') and len(digits) == 12:
            return f"+91 {digits[2:7]} {digits[7:]}"
        
        # Generic format
        return phone
    
    return phone

def get_site_name(website_index: int):
    """Get site name in English format"""
    if 0 <= website_index < len(WEBSITES):
        return f"Site {website_index + 1}"
    return f"Site {website_index + 1}"

def get_keyboard_for_user(user_id: int):
    """Get appropriate keyboard based on user type"""
    if user_id == ADMIN_USER_ID:
        return get_admin_keyboard()
    return get_user_keyboard()

# ==================== DATABASE FUNCTIONS ====================

async def get_or_create_user(telegram_user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    """Get existing user or create new one"""
    try:
        # Check if user exists
        result = supabase.table('users').select('*').eq('telegram_user_id', telegram_user_id).execute()
        
        if result.data and len(result.data) > 0:
            return result.data[0]
        
        # Create new user
        new_user = {
            'telegram_user_id': telegram_user_id,
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'status': 'pending'
        }
        
        result = supabase.table('users').insert(new_user).execute()
        
        if result.data and len(result.data) > 0:
            return result.data[0]
        
        return None
    except Exception as e:
        logger.error(f"Error in get_or_create_user: {e}")
        return None

async def get_user_by_telegram_id(telegram_user_id: int):
    """Get user by Telegram ID"""
    try:
        result = supabase.table('users').select('*').eq('telegram_user_id', telegram_user_id).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Error in get_user_by_telegram_id: {e}")
        return None

async def update_user_status(telegram_user_id: int, status: str, admin_id: int = None):
    """Update user approval status"""
    try:
        update_data = {'status': status}
        
        if status == 'approved':
            update_data['approved_at'] = datetime.now(pytz.UTC).isoformat()
            update_data['approved_by'] = admin_id
        elif status == 'rejected':
            update_data['rejected_at'] = datetime.now(pytz.UTC).isoformat()
            update_data['rejected_by'] = admin_id
        
        result = supabase.table('users').update(update_data).eq('telegram_user_id', telegram_user_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Error in update_user_status: {e}")
        return None

async def add_phone_number(user_id: int, telegram_user_id: int, phone_number: str):
    """Add a new phone number for user"""
    try:
        today = get_bd_date()
        
        new_phone = {
            'user_id': user_id,
            'telegram_user_id': telegram_user_id,
            'phone_number': phone_number,
            'reset_date': today.isoformat(),
            'is_completed': False,
            'websites_completed': 0,
            'earnings_added': False
        }
        
        result = supabase.table('phone_numbers').insert(new_phone).execute()
        
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Error in add_phone_number: {e}")
        return None

async def add_website_completion(phone_number_id: int, website_index: int, website_name: str, phone_detected: str = None, name_detected: str = None):
    """Add website completion record"""
    try:
        completion = {
            'phone_number_id': phone_number_id,
            'website_index': website_index,
            'website_name': website_name,
            'phone_detected': phone_detected,
            'name_detected': name_detected
        }
        
        result = supabase.table('website_completions').insert(completion).execute()
        
        # Update phone_numbers table
        phone_result = supabase.table('phone_numbers').select('websites_completed').eq('id', phone_number_id).execute()
        if phone_result.data:
            current_count = phone_result.data[0].get('websites_completed', 0)
            supabase.table('phone_numbers').update({
                'websites_completed': current_count + 1
            }).eq('id', phone_number_id).execute()
        
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Error in add_website_completion: {e}")
        return None

async def mark_number_completed(phone_number_id: int, user_id: int, telegram_user_id: int, phone_number: str):
    """Mark phone number as completed (all 4 websites done)"""
    try:
        today = get_bd_date()
        
        # Update phone_numbers table
        supabase.table('phone_numbers').update({
            'is_completed': True,
            'completed_at': datetime.now(pytz.UTC).isoformat()
        }).eq('id', phone_number_id).execute()
        
        # Add to completed_numbers
        completed = {
            'phone_number_id': phone_number_id,
            'user_id': user_id,
            'telegram_user_id': telegram_user_id,
            'phone_number': phone_number,
            'earnings': EARNINGS_PER_NUMBER,
            'reset_date': today.isoformat()
        }
        
        result = supabase.table('completed_numbers').insert(completed).execute()
        
        # Update user's total earnings
        user = await get_user_by_telegram_id(telegram_user_id)
        if user:
            new_earnings = float(user.get('total_earnings', 0)) + EARNINGS_PER_NUMBER
            supabase.table('users').update({
                'total_earnings': new_earnings
            }).eq('telegram_user_id', telegram_user_id).execute()
        
        # Mark earnings as added
        supabase.table('phone_numbers').update({
            'earnings_added': True
        }).eq('id', phone_number_id).execute()
        
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Error in mark_number_completed: {e}")
        return None

async def get_user_stats(telegram_user_id: int):
    """Get user statistics for today"""
    try:
        today = get_bd_date()
        
        # Get user
        user = await get_user_by_telegram_id(telegram_user_id)
        if not user:
            return None
        
        # Get today's numbers added
        numbers_added = supabase.table('phone_numbers').select('id', count='exact').eq('telegram_user_id', telegram_user_id).eq('reset_date', today.isoformat()).execute()
        
        # Get today's completed numbers
        numbers_completed = supabase.table('completed_numbers').select('id', count='exact').eq('telegram_user_id', telegram_user_id).eq('reset_date', today.isoformat()).execute()
        
        # Get today's earnings
        earnings_result = supabase.table('completed_numbers').select('earnings').eq('telegram_user_id', telegram_user_id).eq('reset_date', today.isoformat()).execute()
        today_earnings = sum(float(e.get('earnings', 0)) for e in earnings_result.data) if earnings_result.data else 0
        
        return {
            'numbers_added': numbers_added.count if numbers_added else 0,
            'numbers_completed': numbers_completed.count if numbers_completed else 0,
            'today_earnings': today_earnings,
            'total_earnings': float(user.get('total_earnings', 0))
        }
    except Exception as e:
        logger.error(f"Error in get_user_stats: {e}")
        return None

async def get_all_users_list():
    """Get list of all users"""
    try:
        result = supabase.table('users').select('*').order('created_at', desc=True).execute()
        return result.data if result.data else []
    except Exception as e:
        logger.error(f"Error in get_all_users_list: {e}")
        return []

async def get_pending_users_list():
    """Get list of pending users"""
    try:
        result = supabase.table('users').select('*').eq('status', 'pending').order('created_at', desc=True).execute()
        return result.data if result.data else []
    except Exception as e:
        logger.error(f"Error in get_pending_users_list: {e}")
        return []

async def get_total_stats():
    """Get total statistics for admin"""
    try:
        today = get_bd_date()
        
        # Total users
        total_users = supabase.table('users').select('id', count='exact').execute()
        approved_users = supabase.table('users').select('id', count='exact').eq('status', 'approved').execute()
        pending_users = supabase.table('users').select('id', count='exact').eq('status', 'pending').execute()
        
        # Today's numbers
        today_added = supabase.table('phone_numbers').select('id', count='exact').eq('reset_date', today.isoformat()).execute()
        today_completed = supabase.table('completed_numbers').select('id', count='exact').eq('reset_date', today.isoformat()).execute()
        
        # Today's earnings
        today_earnings_result = supabase.table('completed_numbers').select('earnings').eq('reset_date', today.isoformat()).execute()
        today_earnings = sum(float(e.get('earnings', 0)) for e in today_earnings_result.data) if today_earnings_result.data else 0
        
        # Total earnings (all time)
        total_earnings_result = supabase.table('users').select('total_earnings').execute()
        total_earnings = sum(float(u.get('total_earnings', 0)) for u in total_earnings_result.data) if total_earnings_result.data else 0
        
        return {
            'total_users': total_users.count if total_users else 0,
            'approved_users': approved_users.count if approved_users else 0,
            'pending_users': pending_users.count if pending_users else 0,
            'today_added': today_added.count if today_added else 0,
            'today_completed': today_completed.count if today_completed else 0,
            'today_earnings': today_earnings,
            'total_earnings': total_earnings
        }
    except Exception as e:
        logger.error(f"Error in get_total_stats: {e}")
        return None

async def get_or_create_session(user_id: int, telegram_user_id: int):
    """Get or create bot session"""
    try:
        result = supabase.table('bot_sessions').select('*').eq('telegram_user_id', telegram_user_id).execute()
        
        if result.data and len(result.data) > 0:
            return result.data[0]
        
        # Create new session
        new_session = {
            'user_id': user_id,
            'telegram_user_id': telegram_user_id,
            'current_website_index': 0,
            'is_polling': False,
            'completed_websites': []
        }
        
        result = supabase.table('bot_sessions').insert(new_session).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Error in get_or_create_session: {e}")
        return None

async def update_session(telegram_user_id: int, **kwargs):
    """Update bot session"""
    try:
        result = supabase.table('bot_sessions').update(kwargs).eq('telegram_user_id', telegram_user_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Error in update_session: {e}")
        return None

async def get_daily_report_data():
    """Get daily report data for admin"""
    try:
        today = get_bd_date()
        
        # Get all approved users with their stats
        users = supabase.table('users').select('*').eq('status', 'approved').execute()
        
        report_data = []
        for user in users.data:
            telegram_user_id = user['telegram_user_id']
            
            # Get numbers added today
            numbers_added = supabase.table('phone_numbers').select('id', count='exact').eq('telegram_user_id', telegram_user_id).eq('reset_date', today.isoformat()).execute()
            
            # Get numbers completed today
            numbers_completed = supabase.table('completed_numbers').select('id', count='exact').eq('telegram_user_id', telegram_user_id).eq('reset_date', today.isoformat()).execute()
            
            # Get today's earnings
            earnings_result = supabase.table('completed_numbers').select('earnings').eq('telegram_user_id', telegram_user_id).eq('reset_date', today.isoformat()).execute()
            today_earnings = sum(float(e.get('earnings', 0)) for e in earnings_result.data) if earnings_result.data else 0
            
            added_count = numbers_added.count if numbers_added else 0
            completed_count = numbers_completed.count if numbers_completed else 0
            
            if added_count > 0 or completed_count > 0:
                report_data.append({
                    'telegram_user_id': telegram_user_id,
                    'username': user.get('username'),
                    'first_name': user.get('first_name'),
                    'numbers_added': added_count,
                    'numbers_completed': completed_count,
                    'earnings': today_earnings
                })
        
        return report_data
    except Exception as e:
        logger.error(f"Error in get_daily_report_data: {e}")
        return []

async def reset_daily_data():
    """Reset daily phone numbers (called at 8 AM)"""
    try:
        today = get_bd_date()
        
        # Delete phone numbers from previous days
        result = supabase.table('phone_numbers').delete().lt('reset_date', today.isoformat()).execute()
        
        # Reset all bot sessions
        supabase.table('bot_sessions').update({
            'current_phone_number': None,
            'current_phone_number_id': None,
            'current_website_index': 0,
            'completed_websites': [],
            'is_polling': False
        }).neq('telegram_user_id', 0).execute()
        
        # Clear in-memory sessions
        user_sessions.clear()
        user_completed_websites.clear()
        
        logger.info(f"Daily reset completed at {get_bd_time()}")
        return True
    except Exception as e:
        logger.error(f"Error in reset_daily_data: {e}")
        return False

async def get_all_approved_users():
    """Get all approved users"""
    try:
        result = supabase.table('users').select('telegram_user_id').eq('status', 'approved').execute()
        return [u['telegram_user_id'] for u in result.data] if result.data else []
    except Exception as e:
        logger.error(f"Error in get_all_approved_users: {e}")
        return []

# ==================== QR CODE FUNCTIONS ====================

# Initialize UserAgent for random user agents
try:
    ua = UserAgent()
except:
    ua = None

# Create cloudscraper session (bypasses Cloudflare and anti-bot)
def create_scraper_session():
    """Create a new cloudscraper session with SOCKS5 proxy and random browser profile"""
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': random.choice(['chrome', 'firefox']),
            'platform': random.choice(['windows', 'linux', 'darwin']),
            'mobile': False
        },
        delay=random.uniform(1, 3)
    )
    
    # Set SOCKS5 proxy
    scraper.proxies = {
        'http': PROXY_URL,
        'https': PROXY_URL
    }
    
    logger.info(f"[PROXY] Using SOCKS5 proxy: {PROXY_HOST}:{PROXY_PORT}")
    return scraper

def get_random_user_agent():
    """Get a random user agent"""
    if ua:
        try:
            return ua.random
        except:
            pass
    # Fallback user agents
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36 Edg/118.0.2088.76"
    ]
    return random.choice(user_agents)

def get_headers_for_website(website):
    """Get headers customized for each website"""
    # Extract domain from base_url
    domain = website['base_url'].split('/')[2]  # e.g., earnbro.net
    user_agent = get_random_user_agent()
    
    # Randomize Chrome version
    chrome_version = random.randint(118, 122)
    
    return {
        "content-type": "application/json",
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-US,en;q=0.9,bn;q=0.8",
        "accept-encoding": "gzip, deflate, br",
        "user-agent": user_agent,
        "sec-ch-ua": f'"Not_A Brand";v="8", "Chromium";v="{chrome_version}", "Google Chrome";v="{chrome_version}"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "authorization": "Bearer null",
        "origin": f"https://{domain}",
        "referer": f"https://{domain}/",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "x-requested-with": "XMLHttpRequest"
    }


def generate_qr_code(website, user_id, website_index, max_retries=5):
    """Generate QR code for a website with retry mechanism using user's browser profile
    
    Args:
        website: Website configuration dict
        user_id: Telegram user ID for session isolation
        website_index: Index of website for session storage
        max_retries: Maximum number of retry attempts
    
    Returns:
        tuple: (qr_image_bytes, error_message)
    """
    base_url = website['base_url']
    code = website['code']  # Use the original referral code
    
    # Get user's unique browser profile (like separate Chrome profile)
    scraper, fingerprint = get_user_browser_profile(user_id)
    headers = get_user_headers(user_id, website, fingerprint)
    
    for retry in range(max_retries):
        try:
            
            # Add random delay to appear more human-like
            time.sleep(random.uniform(0.5, 2))
            
            # Step 1: Generate QR code
            generate_url = f"{base_url}/qrcode/generate"
            generate_payload = {"code": code}
            
            logger.info(f"[GENERATE_QR] User {user_id}, Attempt {retry + 1}/{max_retries} for {website['name']}")
            response = scraper.post(generate_url, json=generate_payload, headers=headers, timeout=30)
            
            if response.status_code != 200:
                if retry < max_retries - 1:
                    logger.warning(f"[GENERATE_QR] HTTP {response.status_code}, retrying with new session...")
                    time.sleep(random.uniform(2, 4))
                    continue
                return None, f"HTTP Error: {response.status_code}"
            
            generate_data = response.json()
            if generate_data.get("code") != 0:
                if retry < max_retries - 1:
                    logger.warning(f"[GENERATE_QR] API error: {generate_data.get('msg')}, retrying...")
                    time.sleep(2)
                    continue
                return None, f"Error: {generate_data.get('msg', 'Unknown error')}"
            
            # Step 2: Wait for QR code generation
            time.sleep(random.uniform(1.5, 3))
            
            # Step 3: Retrieve QR code data
            retrieve_url = f"{base_url}/qrcode/retrieve"
            retrieve_payload = {"code": code}
            
            qrcode_array = []
            qr_token = None
            retrieve_retries = 5
            for attempt in range(retrieve_retries):
                try:
                    response = scraper.post(retrieve_url, json=retrieve_payload, headers=headers, timeout=30)
                    retrieve_data = response.json()
                    
                    if retrieve_data.get("code") == 0:
                        data = retrieve_data.get("data", {})
                        qrcode_array = data.get("qrcode", [])
                        # Get the unique token from the response if available
                        qr_token = data.get("token") or data.get("id") or data.get("session_id")
                        if qrcode_array and len(qrcode_array) > 0:
                            break
                        elif attempt < retrieve_retries - 1:
                            time.sleep(random.uniform(1, 2))
                except (requests.exceptions.Timeout, Exception) as e:
                    if attempt < retrieve_retries - 1:
                        logger.warning(f"[GENERATE_QR] Retrieve error: {e}, retrying... ({attempt + 1}/{retrieve_retries})")
                        time.sleep(random.uniform(2, 4))
                        continue
                    else:
                        if retry < max_retries - 1:
                            logger.warning(f"[GENERATE_QR] All retrieve attempts failed, retrying generate...")
                            break
                        return None, "Timeout: Could not retrieve QR code data"
                except Exception as e:
                    if attempt < retrieve_retries - 1:
                        logger.warning(f"[GENERATE_QR] Retrieve error: {e}, retrying...")
                        time.sleep(1)
                        continue
                    else:
                        if retry < max_retries - 1:
                            break
                        return None, f"Error retrieving QR code: {str(e)}"
            
            if not qrcode_array or len(qrcode_array) == 0:
                if retry < max_retries - 1:
                    logger.warning(f"[GENERATE_QR] No QR data, retrying generate...")
                    time.sleep(2)
                    continue
                return None, "No QR code data found"
            
            # Step 4: Create QR code image
            qr_data = qrcode_array[0]
            
            # Store the session for this user/website for status checking
            # The qr_data contains the unique WhatsApp linking URL
            if user_id not in user_qr_sessions:
                user_qr_sessions[user_id] = {}
            user_qr_sessions[user_id][website_index] = {
                "scraper": scraper,
                "qr_data": qr_data,
                "qr_token": qr_token,
                "headers": headers,
                "created_at": time.time()
            }
            logger.info(f"[GENERATE_QR] Stored session for user {user_id}, website {website_index}")
            
            qr = QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=5,
            )
            qr.add_data(qr_data)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to bytes
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            
            logger.info(f"[GENERATE_QR] Successfully generated QR code for {website['name']} (user {user_id})")
            return img_bytes, None
            
        except requests.exceptions.Timeout as e:
            if retry < max_retries - 1:
                logger.warning(f"[GENERATE_QR] Timeout error, retrying... ({retry + 1}/{max_retries})")
                time.sleep(3)
                continue
            return None, f"Timeout: Connection to {website['name']} timed out. Please try again."
        except requests.exceptions.ConnectionError as e:
            if retry < max_retries - 1:
                logger.warning(f"[GENERATE_QR] Connection error, retrying... ({retry + 1}/{max_retries})")
                time.sleep(3)
                continue
            return None, f"Connection Error: Could not connect to {website['name']}. Please check your internet connection."
        except Exception as e:
            if retry < max_retries - 1:
                logger.warning(f"[GENERATE_QR] Error: {e}, retrying... ({retry + 1}/{max_retries})")
                time.sleep(2)
                continue
            return None, f"Error: {str(e)}"
    
    return None, f"Failed to generate QR code after {max_retries} attempts. Please try again later."


def check_login_status(website, user_id, website_index):
    """Check login status for a website using the user's browser profile
    
    Args:
        website: Website configuration dict
        user_id: Telegram user ID for session isolation
        website_index: Index of website to check status for
    """
    try:
        base_url = website['base_url']
        code = website['code']  # Use the original referral code
        
        # Use user's browser profile (same profile used for QR generation)
        scraper, fingerprint = get_user_browser_profile(user_id)
        headers = get_user_headers(user_id, website, fingerprint)
        
        logger.info(f"[CHECK_STATUS] Using browser profile for user {user_id}, fingerprint: {fingerprint[:8]}...")
        
        # Get any stored session data (for token)
        session_data = None
        if user_id in user_qr_sessions and website_index in user_qr_sessions[user_id]:
            session_data = user_qr_sessions[user_id][website_index]
        
        status_url = f"{base_url}/login/status"
        status_payload = {"code": code}
        
        # Add token and fingerprint if available
        if session_data and session_data.get("qr_token"):
            status_payload["token"] = session_data["qr_token"]
        
        # Add fingerprint to help server identify the session
        status_payload["client_id"] = fingerprint
        
        response = scraper.post(status_url, json=status_payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            status_data = response.json()
            status_code = status_data.get("code")
            msg = status_data.get("msg", "")
            msg_lower = msg.lower() if msg else ""
            data = status_data.get("data", {})
            
            is_success_message = "success" in msg_lower or "login success" in msg_lower
            is_success = (status_code == 0) or is_success_message
            
            if is_success:
                phone = None
                name = None
                
                possible_phone_fields = [
                    "phone", "phoneNumber", "mobile", "number", "mobileNumber",
                    "phone_number", "mobile_number", "tel", "telephone",
                    "wa", "whatsapp", "whatsappNumber", "waNumber"
                ]
                
                possible_name_fields = [
                    "name", "userName", "username", "displayName", "nickname",
                    "user_name", "display_name", "fullName", "full_name"
                ]
                
                if isinstance(data, dict):
                    for field in possible_phone_fields:
                        if field in data and data[field]:
                            phone = data[field]
                            break
                    
                    for field in possible_name_fields:
                        if field in data and data[field]:
                            name = data[field]
                            break
                
                logger.info(f"[CHECK_STATUS] Success detected - code: {status_code}, msg: {msg}, phone: {phone}, name: {name}")
                
                return {
                    "status": "success",
                    "phone": phone,
                    "name": name,
                    "message": msg,
                    "data": data
                }
            elif status_code == 20001 and ("waiting" in msg_lower or msg == "waiting"):
                return {"status": "waiting", "message": msg}
            else:
                if is_success_message:
                    logger.info(f"[CHECK_STATUS] Success message detected in 'other' status: {msg}")
                    return {
                        "status": "success",
                        "phone": None,
                        "name": None,
                        "message": msg,
                        "data": data
                    }
                return {"status": "other", "message": msg, "code": status_code}
        
        return {"status": "error", "message": f"HTTP {response.status_code}"}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==================== TELEGRAM HANDLERS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    user_id = user.id
    username = user.username
    first_name = user.first_name
    last_name = user.last_name
    
    # Check if admin
    if user_id == ADMIN_USER_ID:
        # Auto-approve admin
        db_user = await get_or_create_user(user_id, username, first_name, last_name)
        if db_user and db_user.get('status') != 'approved':
            await update_user_status(user_id, 'approved', user_id)
        
        # Get stats
        stats = await get_total_stats()
        stats_msg = ""
        if stats:
            stats_msg = (
                f"\n\n📈 System Stats:\n"
                f"👥 Total Users: {stats['total_users']}\n"
                f"✅ Approved: {stats['approved_users']}\n"
                f"⏳ Pending: {stats['pending_users']}\n"
                f"📱 Today Added: {stats['today_added']}\n"
                f"✅ Today Completed: {stats['today_completed']}\n"
                f"💰 Today Earnings: {stats['today_earnings']:.2f} Tk\n"
                f"💵 Total Earnings: {stats['total_earnings']:.2f} Tk"
            )
        
        await update.message.reply_text(
            f"👋 Welcome Admin!\n\n"
            f"You have full access to the bot."
            f"{stats_msg}",
            reply_markup=get_admin_keyboard()
        )
        return
    
    # Get or create user in database
    db_user = await get_or_create_user(user_id, username, first_name, last_name)
    
    if not db_user:
        await update.message.reply_text(
            "❌ System error occurred. Please try again later.",
            reply_markup=get_pending_keyboard()
        )
        return
    
    user_status = db_user.get('status', 'pending')
    
    if user_status == 'pending':
        # New user - notify admin
        await update.message.reply_text(
            "👋 Welcome!\n\n"
            "⏳ Your account is pending approval.\n"
            "Admin will review your request.\n\n"
            "📱 You will be notified once approved.",
            reply_markup=get_pending_keyboard()
        )
        
        # Notify admin
        admin_msg = (
            "🆕 New User Request!\n\n"
            f"👤 Name: {first_name or 'N/A'} {last_name or ''}\n"
            f"🔗 Username: @{username if username else 'N/A'}\n"
            f"🆔 User ID: {user_id}\n\n"
            "What would you like to do?"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}")
            ]
        ]
        
        try:
            await context.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text=admin_msg,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Error notifying admin: {e}")
        
    elif user_status == 'rejected':
        await update.message.reply_text(
            "❌ Your account has been rejected.\n"
            "Please contact admin for assistance.",
            reply_markup=get_pending_keyboard()
        )
        
    elif user_status == 'approved':
        # Initialize session
        user_sessions[user_id] = {
            "current_index": 0,
            "is_polling": False,
            "last_message_id": None,
            "current_phone_number": None,
            "current_phone_number_id": None
        }
        user_completed_websites[user_id] = []
        
        # Get user stats
        stats = await get_user_stats(user_id)
        stats_msg = ""
        if stats:
            stats_msg = (
                f"\n\n📊 Today's Statistics:\n"
                f"📱 Numbers Added: {stats['numbers_added']}\n"
                f"✅ Numbers Completed: {stats['numbers_completed']}\n"
                f"💰 Today's Earnings: {stats['today_earnings']:.2f} Taka\n"
                f"💵 Total Earnings: {stats['total_earnings']:.2f} Taka"
            )
        
        welcome_msg = (
            "👋 Welcome!\n\n"
            "📱 Send your phone number to start generating QR codes.\n\n"
            "🌐 Login to all 4 websites = 1 number completed\n"
            "💰 Earn 10 Taka per completed number\n\n"
            "⏰ Working Hours: 10:30 AM - 7:00 AM (next day)\n"
            "🔄 Daily reset at 8:00 AM"
            f"{stats_msg}"
        )
        
        await update.message.reply_text(welcome_msg, reply_markup=get_user_keyboard())


async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin approval/rejection callbacks"""
    query = update.callback_query
    await query.answer()
    
    admin_id = query.from_user.id
    
    # Check if user is admin
    if admin_id != ADMIN_USER_ID:
        await query.answer("❌ You are not an admin!", show_alert=True)
        return
    
    data = query.data
    
    if data.startswith("approve_"):
        target_user_id = int(data.split("_")[1])
        
        # Update user status
        await update_user_status(target_user_id, 'approved', admin_id)
        
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=(
                    "🎉 Congratulations!\n\n"
                    "✅ Your account has been approved!\n\n"
                    "📱 Send your phone number to start generating QR codes.\n\n"
                    "⏰ Working Hours: 10:30 AM - 7:00 AM (next day)"
                ),
                reply_markup=get_user_keyboard()
            )
        except Exception as e:
            logger.error(f"Error notifying user: {e}")
        
        # Update admin message
        await query.edit_message_text(
            f"{query.message.text}\n\n✅ Approved!"
        )
        
    elif data.startswith("reject_"):
        target_user_id = int(data.split("_")[1])
        
        # Update user status
        await update_user_status(target_user_id, 'rejected', admin_id)
        
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=(
                    "❌ Sorry!\n\n"
                    "Your account has been rejected.\n"
                    "Please contact admin for assistance."
                ),
                reply_markup=get_pending_keyboard()
            )
        except Exception as e:
            logger.error(f"Error notifying user: {e}")
        
        # Update admin message
        await query.edit_message_text(
            f"{query.message.text}\n\n❌ Rejected!"
        )


async def handle_menu_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle menu button clicks"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # Get user from database
    db_user = await get_user_by_telegram_id(user_id)
    
    # Handle Help button (available to all)
    if text == BTN_HELP:
        help_msg = (
            "❓ Help & Instructions\n\n"
            "📱 How to use:\n"
            "1. Send your phone number\n"
            "2. Scan QR code with WhatsApp\n"
            "3. Wait for success confirmation\n"
            "4. Click 'Next Site' for next QR\n"
            "5. Complete all 4 sites = 1 number done\n\n"
            "💰 Earnings:\n"
            "• 10 Taka per completed number\n\n"
            "⏰ Working Hours:\n"
            "• 10:30 AM to 7:00 AM (next day)\n"
            "• Daily reset at 8:00 AM\n\n"
            "📊 Commands:\n"
            "• /start - Restart bot\n"
            "• /stats - View your stats"
        )
        keyboard = get_keyboard_for_user(user_id)
        await update.message.reply_text(help_msg, reply_markup=keyboard)
        return True
    
    # Handle Working Hours button
    if text == BTN_WORKING_HOURS:
        now = get_bd_time()
        is_working = is_within_working_hours()
        status = "🟢 OPEN" if is_working else "🔴 CLOSED"
        
        hours_msg = (
            f"⏰ Working Hours Status: {status}\n\n"
            f"📅 Current Time: {now.strftime('%I:%M %p')}\n"
            f"📆 Date: {now.strftime('%Y-%m-%d')}\n\n"
            f"🕐 Working Schedule:\n"
            f"• Start: 10:30 AM\n"
            f"• End: 7:00 AM (next day)\n\n"
            f"🔄 Daily Reset: 8:00 AM\n"
            f"📊 Admin Report: 3:00 PM"
        )
        keyboard = get_keyboard_for_user(user_id)
        await update.message.reply_text(hours_msg, reply_markup=keyboard)
        return True
    
    # Check if user is approved for other buttons
    if not db_user or db_user.get('status') != 'approved':
        if db_user and db_user.get('status') == 'pending':
            await update.message.reply_text(
                "⏳ Your account is pending approval.",
                reply_markup=get_pending_keyboard()
            )
        else:
            await update.message.reply_text(
                "❌ Your account is not approved.",
                reply_markup=get_pending_keyboard()
            )
        return True
    
    # Handle My Stats button
    if text == BTN_MY_STATS:
        stats = await get_user_stats(user_id)
        if stats:
            msg = (
                "📊 Your Statistics:\n\n"
                f"📱 Numbers Added Today: {stats['numbers_added']}\n"
                f"✅ Numbers Completed Today: {stats['numbers_completed']}\n"
                f"💰 Today's Earnings: {stats['today_earnings']:.2f} Taka\n"
                f"💵 Total Earnings: {stats['total_earnings']:.2f} Taka\n\n"
                f"📅 Date: {get_bd_date()}"
            )
        else:
            msg = "❌ Error loading statistics."
        
        keyboard = get_keyboard_for_user(user_id)
        await update.message.reply_text(msg, reply_markup=keyboard)
        return True
    
    # Admin-only buttons
    if user_id == ADMIN_USER_ID:
        # Today's Report
        if text == BTN_ADMIN_REPORT:
            report_data = await get_daily_report_data()
            today = get_bd_date()
            
            if not report_data:
                report_msg = f"📊 Daily Report - {today}\n\nNo activity today."
            else:
                report_msg = f"📊 Daily Report - {today}\n\n"
                
                total_added = 0
                total_completed = 0
                total_earnings = 0
                
                for i, user_data in enumerate(report_data, 1):
                    username = user_data.get('username') or user_data.get('first_name') or f"User {user_data['telegram_user_id']}"
                    report_msg += (
                        f"{i}. {username}\n"
                        f"   📱 Added: {user_data['numbers_added']} | "
                        f"✅ Done: {user_data['numbers_completed']} | "
                        f"💰 {user_data['earnings']:.0f} Tk\n\n"
                    )
                    total_added += user_data['numbers_added']
                    total_completed += user_data['numbers_completed']
                    total_earnings += user_data['earnings']
                
                report_msg += (
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"📊 Total:\n"
                    f"📱 Added: {total_added}\n"
                    f"✅ Completed: {total_completed}\n"
                    f"💰 Earnings: {total_earnings:.0f} Taka"
                )
            
            await update.message.reply_text(report_msg, reply_markup=get_admin_keyboard())
            return True
        
        # All Users
        if text == BTN_ADMIN_USERS:
            users = await get_all_users_list()
            
            if not users:
                msg = "👥 No users found."
            else:
                msg = f"👥 All Users ({len(users)}):\n\n"
                for i, u in enumerate(users[:20], 1):  # Limit to 20
                    status_emoji = "✅" if u.get('status') == 'approved' else "⏳" if u.get('status') == 'pending' else "❌"
                    username = u.get('username') or u.get('first_name') or f"ID: {u['telegram_user_id']}"
                    earnings = float(u.get('total_earnings', 0))
                    msg += f"{i}. {status_emoji} {username} - {earnings:.0f} Tk\n"
                
                if len(users) > 20:
                    msg += f"\n... and {len(users) - 20} more"
            
            await update.message.reply_text(msg, reply_markup=get_admin_keyboard())
            return True
        
        # Pending Users
        if text == BTN_ADMIN_PENDING:
            users = await get_pending_users_list()
            
            if not users:
                msg = "⏳ No pending users."
            else:
                msg = f"⏳ Pending Users ({len(users)}):\n\n"
                for u in users:
                    username = u.get('username') or u.get('first_name') or f"ID: {u['telegram_user_id']}"
                    msg += f"• {username}\n"
                    
                    # Send approval buttons
                    keyboard = [
                        [
                            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{u['telegram_user_id']}"),
                            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{u['telegram_user_id']}")
                        ]
                    ]
                    await update.message.reply_text(
                        f"👤 {username}\n🆔 ID: {u['telegram_user_id']}",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
            
            await update.message.reply_text(msg, reply_markup=get_admin_keyboard())
            return True
        
        # Total Stats
        if text == BTN_ADMIN_STATS:
            stats = await get_total_stats()
            
            if stats:
                msg = (
                    "📈 Total System Statistics:\n\n"
                    f"👥 Total Users: {stats['total_users']}\n"
                    f"✅ Approved Users: {stats['approved_users']}\n"
                    f"⏳ Pending Users: {stats['pending_users']}\n\n"
                    f"📱 Today's Numbers Added: {stats['today_added']}\n"
                    f"✅ Today's Numbers Completed: {stats['today_completed']}\n"
                    f"💰 Today's Earnings: {stats['today_earnings']:.2f} Taka\n\n"
                    f"💵 Total Earnings (All Time): {stats['total_earnings']:.2f} Taka\n\n"
                    f"📅 Date: {get_bd_date()}"
                )
            else:
                msg = "❌ Error loading statistics."
            
            await update.message.reply_text(msg, reply_markup=get_admin_keyboard())
            return True
    
    return False


async def handle_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle phone number input"""
    user = update.effective_user
    user_id = user.id
    phone_text = update.message.text.strip()
    
    # First check if it's a menu button
    if await handle_menu_buttons(update, context):
        return
    
    # Check if user is approved
    db_user = await get_user_by_telegram_id(user_id)
    
    if not db_user:
        await update.message.reply_text(
            "❌ Please use /start command first.",
            reply_markup=get_pending_keyboard()
        )
        return
    
    if db_user.get('status') != 'approved':
        if db_user.get('status') == 'pending':
            await update.message.reply_text(
                "⏳ Your account is pending approval.\n"
                "Admin is reviewing your request.",
                reply_markup=get_pending_keyboard()
            )
        else:
            await update.message.reply_text(
                "❌ Your account has been rejected.",
                reply_markup=get_pending_keyboard()
            )
        return
    
    # Check working hours
    if not is_within_working_hours():
        await update.message.reply_text(
            get_working_hours_message(),
            reply_markup=get_keyboard_for_user(user_id)
        )
        return
    
    # Initialize session if not exists
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "current_index": 0,
            "is_polling": False,
            "last_message_id": None,
            "current_phone_number": None,
            "current_phone_number_id": None
        }
    if user_id not in user_completed_websites:
        user_completed_websites[user_id] = []
    
    # Normalize phone number to standard format (+XXXXXXXXXXX)
    phone = normalize_phone_number(phone_text)
    
    if not phone:
        await update.message.reply_text(
            "❌ Invalid phone number. Please enter a valid number.\n\n"
            "📱 Accepted formats:\n"
            "• +1 (506) 789-8784\n"
            "• 15067898784\n"
            "• +880 1738 791149\n"
            "• 01738791149",
            reply_markup=get_keyboard_for_user(user_id)
        )
        return
    
    # Reset completed websites for new number
    user_completed_websites[user_id] = []
    
    # Clear any existing QR sessions for this user
    if user_id in user_qr_sessions:
        user_qr_sessions[user_id] = {}
    
    # Add phone number to database
    phone_record = await add_phone_number(db_user['id'], user_id, phone)
    
    if not phone_record:
        await update.message.reply_text(
            "❌ Database error. Please try again.",
            reply_markup=get_keyboard_for_user(user_id)
        )
        return
    
    # Update session
    user_sessions[user_id]["current_phone_number"] = phone
    user_sessions[user_id]["current_phone_number_id"] = phone_record['id']
    user_sessions[user_id]["current_index"] = 0
    
    # Get current website
    current_index = 0
    website = WEBSITES[current_index]
    site_name = get_site_name(current_index)
    
    # Check if website is locked by another user
    is_locked, lock_info = is_website_locked(current_index)
    if is_locked and lock_info.get("user_id") != user_id:
        # Website is in use by another user
        await update.message.reply_text(
            f"⏳ {site_name} is currently in use by another user.\n\n"
            f"Please wait 1-2 minutes and try again.\n"
            f"📱 Your number: {format_phone_number(phone)}",
            reply_markup=get_keyboard_for_user(user_id)
        )
        return
    
    # Lock the website for this user
    lock_website(current_index, user_id, phone)
    
    # Send loading message first
    loading_msg = await update.message.reply_text(
        f"🔄 Generating QR code for {site_name}...\n"
        f"📱 Phone: {format_phone_number(phone)}"
    )
    
    # Generate QR code - session is stored per user/website automatically
    qr_image, error = generate_qr_code(website, user_id, current_index)
    
    if error:
        # Unlock website on error
        unlock_website(current_index, user_id)
        await loading_msg.edit_text(
            f"❌ Error: {error}\n\nPlease send your phone number again.",
            reply_markup=None
        )
        return
    
    # Delete loading message and send QR code image
    await loading_msg.delete()
    
    qr_image.seek(0)
    sent_message = await update.message.reply_photo(
        photo=qr_image,
        caption=(
            f"📱 {format_phone_number(phone)}\n\n"
            f"🌐 {site_name} - Scan with WhatsApp\n"
            f"⏳ Waiting for scan...\n\n"
            f"Progress: [{'✅' * 0}{'⬜' * 4}] 0/4"
        ),
        reply_markup=create_website_keyboard(current_index)
    )
    
    user_sessions[user_id]["last_message_id"] = sent_message.message_id
    
    # Start polling for login status
    user_sessions[user_id]["is_polling"] = True
    user_sessions[user_id]["poll_count"] = 0
    
    async def poll_job(ctx):
        await poll_login_status(ctx, user_id, website, current_index)
    
    context.job_queue.run_once(poll_job, when=5)


async def poll_login_status(context: ContextTypes.DEFAULT_TYPE, user_id: int, website: dict, website_index: int):
    """Poll login status and handle success
    
    Args:
        context: Telegram context
        user_id: User's Telegram ID
        website: Website configuration dict
        website_index: Index of the website in WEBSITES list
    """
    try:
        if user_id not in user_sessions or not user_sessions[user_id].get("is_polling"):
            logger.info(f"Polling stopped for user {user_id}")
            return
        
        logger.info(f"Polling status for user {user_id}, website: {website['name']}")
        status_result = check_login_status(website, user_id, website_index)
        
        logger.info(f"[POLL] Status result: {status_result}")
        
        is_success = (
            status_result["status"] == "success" or 
            "success" in status_result.get("message", "").lower() or
            "login success" in status_result.get("message", "").lower()
        )
        
        if is_success:
            logger.info(f"Login successful for user {user_id}, website: {website['name']}")
            user_sessions[user_id]["is_polling"] = False
            
            phone = status_result.get("phone")
            name = status_result.get("name")
            
            # Track completed website
            if user_id not in user_completed_websites:
                user_completed_websites[user_id] = []
            
            if website_index not in user_completed_websites[user_id]:
                user_completed_websites[user_id].append(website_index)
                
                # UNLOCK the website - user finished with this site
                unlock_website(website_index, user_id)
                logger.info(f"[POLL] Unlocked website {website_index} after success")
                
                # Add website completion to database
                phone_number_id = user_sessions[user_id].get("current_phone_number_id")
                if phone_number_id:
                    await add_website_completion(
                        phone_number_id, 
                        website_index, 
                        website['name'],
                        phone,
                        name
                    )
                
                logger.info(f"[POLL] User {user_id} completed website {website['name']} (index: {website_index})")
                logger.info(f"[POLL] Completed websites: {user_completed_websites[user_id]}")
            
            # Get progress info
            completed_count = len(user_completed_websites[user_id])
            progress = '✅' * completed_count + '⬜' * (4 - completed_count)
            current_phone = user_sessions[user_id].get("current_phone_number", "")
            phone_display = format_phone_number(current_phone) if current_phone else ""
            
            # Check if all websites are completed
            if completed_count >= len(WEBSITES):
                # All websites completed!
                logger.info(f"[POLL] All websites completed for user {user_id}")
                user_sessions[user_id]["is_polling"] = False
                
                # Mark number as completed and add earnings
                phone_number_id = user_sessions[user_id].get("current_phone_number_id")
                db_user = await get_user_by_telegram_id(user_id)
                
                if phone_number_id and db_user:
                    await mark_number_completed(
                        phone_number_id,
                        db_user['id'],
                        user_id,
                        current_phone
                    )
                
                # Get updated stats
                stats = await get_user_stats(user_id)
                
                # Build completion message for caption
                completion_caption = (
                    f"📱 {phone_display}\n\n"
                    f"🎉 ALL SITES COMPLETED!\n\n"
                    f"Progress: [{progress}] {completed_count}/4\n"
                    f"💰 +{EARNINGS_PER_NUMBER:.0f} Taka added!\n\n"
                )
                
                if stats:
                    completion_caption += (
                        f"📊 Today: {stats['numbers_completed']} completed\n"
                        f"💵 Total: {stats['total_earnings']:.2f} Taka"
                    )
                
                # Update last message with completion
                last_msg_id = user_sessions[user_id].get("last_message_id")
                if last_msg_id:
                    try:
                        await context.bot.edit_message_caption(
                            chat_id=user_id,
                            message_id=last_msg_id,
                            caption=completion_caption,
                            reply_markup=None
                        )
                    except Exception as e:
                        logger.error(f"Error editing message: {e}")
                
                # Send new number prompt
                try:
                    await context.bot.send_message(
                        chat_id=user_id, 
                        text="📱 Send a new phone number to continue.",
                        reply_markup=get_keyboard_for_user(user_id)
                    )
                except Exception as e:
                    logger.error(f"Error sending completion message: {e}")
                
                # Reset for new number
                user_completed_websites[user_id] = []
                user_sessions[user_id]["current_index"] = 0
                user_sessions[user_id]["current_phone_number"] = None
                user_sessions[user_id]["current_phone_number_id"] = None
                return
            
            # Not all sites completed - show success briefly and auto-move to next
            site_name = get_site_name(website_index)
            
            # Update message to show success
            last_msg_id = user_sessions[user_id].get("last_message_id")
            if last_msg_id:
                try:
                    await context.bot.edit_message_caption(
                        chat_id=user_id,
                        message_id=last_msg_id,
                        caption=(
                            f"📱 {phone_display}\n\n"
                            f"✅ {site_name} - Scanned!\n\n"
                            f"Progress: [{progress}] {completed_count}/4\n\n"
                            f"🔄 Loading next site..."
                        ),
                        reply_markup=None
                    )
                except Exception as e:
                    logger.error(f"Error editing message: {e}")
            
            # Find next uncompleted website
            next_index = None
            for i in range(len(WEBSITES)):
                if i not in user_completed_websites[user_id]:
                    next_index = i
                    break
            
            if next_index is not None:
                next_website = WEBSITES[next_index]
                user_sessions[user_id]["current_index"] = next_index
                
                logger.info(f"[POLL] Auto-moving to next website: {next_website['name']} (index: {next_index})")
                
                # Generate next QR code after short delay
                async def generate_next_job(ctx):
                    await generate_and_send_next(ctx, user_id, next_website, next_index)
                
                context.job_queue.run_once(generate_next_job, when=2)
            
            user_sessions[user_id]["is_polling"] = False
            
        elif status_result["status"] == "waiting":
            max_polls = 120  # 10 minutes
            poll_count = user_sessions[user_id].get("poll_count", 0)
            
            if poll_count < max_polls:
                user_sessions[user_id]["poll_count"] = poll_count + 1
                
                # Get progress info
                completed_count = len(user_completed_websites.get(user_id, []))
                progress = '✅' * completed_count + '⬜' * (4 - completed_count)
                current_phone = user_sessions[user_id].get("current_phone_number", "")
                phone_display = format_phone_number(current_phone) if current_phone else ""
                
                last_msg_id = user_sessions[user_id].get("last_message_id")
                if last_msg_id and poll_count % 6 == 0:  # Update every 30 seconds
                    try:
                        await context.bot.edit_message_caption(
                            chat_id=user_id,
                            message_id=last_msg_id,
                            caption=(
                                f"📱 {phone_display}\n\n"
                                f"🌐 {get_site_name(website_index)} - Scan with WhatsApp\n"
                                f"⏳ Waiting... ({poll_count * 5}s)\n\n"
                                f"Progress: [{progress}] {completed_count}/4"
                            ),
                            reply_markup=create_website_keyboard(website_index)
                        )
                    except Exception as e:
                        logger.error(f"Error updating message: {e}")
                
                async def next_poll_job(ctx):
                    await poll_login_status(ctx, user_id, website, website_index)
                
                context.job_queue.run_once(next_poll_job, when=5)
            else:
                user_sessions[user_id]["is_polling"] = False
                # UNLOCK the website on timeout
                unlock_website(website_index, user_id)
                logger.info(f"[POLL] Unlocked website {website_index} after timeout")
                
                site_name = get_site_name(website_index)
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"⏰ QR code for {site_name} has expired. Please generate a new one.",
                    reply_markup=get_keyboard_for_user(user_id)
                )
        else:
            status_msg = status_result.get("message", "").lower()
            if "success" in status_msg or "login success" in status_msg:
                logger.info(f"[POLL] Detected success in message: {status_msg}")
                status_result["status"] = "success"
                await poll_login_status(context, user_id, website, website_index)
                return
            
            logger.warning(f"[POLL] Status check returned: {status_result}, continuing to poll...")
            async def retry_poll_job(ctx):
                await poll_login_status(ctx, user_id, website, website_index)
            
            context.job_queue.run_once(retry_poll_job, when=5)
    except Exception as e:
        logger.error(f"Error in poll_login_status: {e}")
        import traceback
        traceback.print_exc()


async def generate_and_send_next(context: ContextTypes.DEFAULT_TYPE, user_id: int, website: dict, website_index: int):
    """Generate QR code and update the same message (or send new if no existing message)"""
    try:
        logger.info(f"[GENERATE_NEXT] Starting for user {user_id}, website: {website['name']}, index: {website_index}")
        
        if user_id not in user_sessions:
            user_sessions[user_id] = {
                "current_index": website_index,
                "is_polling": False,
                "last_message_id": None,
                "poll_count": 0
            }
        
        # Get phone number for display
        phone = user_sessions[user_id].get("current_phone_number", "")
        phone_display = format_phone_number(phone) if phone else ""
        site_name = get_site_name(website_index)
        
        # Check if website is locked by another user
        is_locked, lock_info = is_website_locked(website_index)
        if is_locked and lock_info.get("user_id") != user_id:
            # Website is in use - notify user
            await context.bot.send_message(
                chat_id=user_id,
                text=f"⏳ {site_name} is currently in use.\nPlease wait 1-2 minutes...",
                reply_markup=get_keyboard_for_user(user_id)
            )
            return
        
        # Lock the website for this user
        lock_website(website_index, user_id, phone)
        
        # Get completed count for progress bar
        completed_count = len(user_completed_websites.get(user_id, []))
        progress = '✅' * completed_count + '⬜' * (4 - completed_count)
        
        logger.info(f"[GENERATE_NEXT] Generating QR code for {website['name']} (user {user_id})...")
        qr_image, error = generate_qr_code(website, user_id, website_index)
        
        if error:
            logger.error(f"[GENERATE_NEXT] Error generating QR: {error}")
            # Unlock on error
            unlock_website(website_index, user_id)
            last_msg_id = user_sessions[user_id].get("last_message_id")
            if last_msg_id:
                try:
                    await context.bot.edit_message_caption(
                        chat_id=user_id,
                        message_id=last_msg_id,
                        caption=f"❌ Error generating QR code for {site_name}: {error}",
                        reply_markup=create_website_keyboard(website_index)
                    )
                except:
                    pass
            return
        
        logger.info(f"[GENERATE_NEXT] QR code generated successfully...")
        
        qr_image.seek(0)
        site_name = get_site_name(website_index)
        last_msg_id = user_sessions[user_id].get("last_message_id")
        
        caption = (
            f"📱 {phone_display}\n\n"
            f"🌐 {site_name} - Scan with WhatsApp\n"
            f"⏳ Waiting for scan...\n\n"
            f"Progress: [{progress}] {completed_count}/4"
        )
        
        # Try to update existing message, if fails send new
        if last_msg_id:
            try:
                await context.bot.edit_message_media(
                    chat_id=user_id,
                    message_id=last_msg_id,
                    media=InputMediaPhoto(media=qr_image, caption=caption),
                    reply_markup=create_website_keyboard(website_index)
                )
                logger.info(f"[GENERATE_NEXT] Message updated successfully")
            except Exception as e:
                logger.error(f"[GENERATE_NEXT] Error updating message: {e}, sending new...")
                qr_image.seek(0)
                sent_message = await context.bot.send_photo(
                    chat_id=user_id,
                    photo=qr_image,
                    caption=caption,
                    reply_markup=create_website_keyboard(website_index)
                )
                user_sessions[user_id]["last_message_id"] = sent_message.message_id
        else:
            qr_image.seek(0)
            sent_message = await context.bot.send_photo(
                chat_id=user_id,
                photo=qr_image,
                caption=caption,
                reply_markup=create_website_keyboard(website_index)
            )
            user_sessions[user_id]["last_message_id"] = sent_message.message_id
        
        user_sessions[user_id]["is_polling"] = True
        user_sessions[user_id]["poll_count"] = 0
        user_sessions[user_id]["current_index"] = website_index
        
        logger.info(f"[GENERATE_NEXT] Session updated, starting polling in 5 seconds...")
        
        async def start_poll_job(ctx):
            logger.info(f"[POLL_JOB] Starting poll job for user {user_id}, website: {website['name']}")
            await poll_login_status(ctx, user_id, website, website_index)
        
        context.job_queue.run_once(start_poll_job, when=5)
        
        logger.info(f"[GENERATE_NEXT] Poll job scheduled successfully")
        
    except Exception as e:
        logger.error(f"[GENERATE_NEXT] Exception: {e}")
        import traceback
        traceback.print_exc()
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ Error generating QR code: {str(e)}\n\nPlease try again.",
                reply_markup=get_keyboard_for_user(user_id)
            )
        except:
            pass


async def generate_and_update_same_message(context: ContextTypes.DEFAULT_TYPE, user_id: int, website: dict, website_index: int, message_id: int):
    """Generate QR code and update the same message"""
    try:
        logger.info(f"[UPDATE_SAME] Starting for user {user_id}, website: {website['name']}, index: {website_index}, message_id: {message_id}")
        
        if user_id not in user_sessions:
            user_sessions[user_id] = {
                "current_index": website_index,
                "is_polling": False,
                "last_message_id": message_id,
                "poll_count": 0
            }
        
        logger.info(f"[UPDATE_SAME] Generating QR code for {website['name']} (user {user_id})...")
        qr_image, error = generate_qr_code(website, user_id, website_index)
        
        if error:
            logger.error(f"[UPDATE_SAME] Error generating QR: {error}")
            site_name = get_site_name(website_index)
            try:
                await context.bot.edit_message_caption(
                    chat_id=user_id,
                    message_id=message_id,
                    caption=f"❌ Error generating QR code for {site_name}: {error}",
                    reply_markup=create_website_keyboard(website_index)
                )
            except:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"❌ Error generating QR code for {site_name}: {error}",
                    reply_markup=get_keyboard_for_user(user_id)
                )
            return
        
        logger.info(f"[UPDATE_SAME] QR code generated successfully, updating message...")
        
        qr_image.seek(0)
        site_name = get_site_name(website_index)
        
        try:
            await context.bot.edit_message_media(
                chat_id=user_id,
                message_id=message_id,
                media=InputMediaPhoto(
                    media=qr_image,
                    caption=(
                        f"📱 QR Code for {site_name}\n\n"
                        f"Scan with WhatsApp to link your number.\n"
                        f"⏳ Waiting for scan..."
                    )
                ),
                reply_markup=create_website_keyboard(website_index)
            )
            logger.info(f"[UPDATE_SAME] Message updated successfully")
        except Exception as e:
            logger.error(f"[UPDATE_SAME] Error updating message: {e}")
            qr_image.seek(0)
            sent_message = await context.bot.send_photo(
                chat_id=user_id,
                photo=qr_image,
                caption=(
                    f"📱 QR Code for {site_name}\n\n"
                    f"Scan with WhatsApp to link your number.\n"
                    f"⏳ Waiting for scan..."
                ),
                reply_markup=create_website_keyboard(website_index)
            )
            message_id = sent_message.message_id
        
        user_sessions[user_id]["last_message_id"] = message_id
        user_sessions[user_id]["is_polling"] = True
        user_sessions[user_id]["poll_count"] = 0
        user_sessions[user_id]["current_index"] = website_index
        
        logger.info(f"[UPDATE_SAME] Session updated, starting polling in 5 seconds...")
        
        async def start_poll_job(ctx):
            logger.info(f"[POLL_JOB] Starting poll job for user {user_id}, website: {website['name']}")
            await poll_login_status(ctx, user_id, website, website_index)
        
        context.job_queue.run_once(start_poll_job, when=5)
        
        logger.info(f"[UPDATE_SAME] Poll job scheduled successfully")
        
    except Exception as e:
        logger.error(f"[UPDATE_SAME] Exception: {e}")
        import traceback
        traceback.print_exc()
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ Error generating QR code: {str(e)}\n\nPlease try again.",
                reply_markup=get_keyboard_for_user(user_id)
            )
        except:
            pass


def create_website_keyboard(website_index: int, show_next=False):
    """Create inline keyboard for QR code actions"""
    keyboard = [
        [InlineKeyboardButton("🔄 Regenerate QR", callback_data=f"generate_new_{website_index}")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    # Handle admin callbacks
    if data.startswith("approve_") or data.startswith("reject_"):
        await handle_admin_callback(update, context)
        return
    
    # Check if user is approved
    db_user = await get_user_by_telegram_id(user_id)
    if not db_user or db_user.get('status') != 'approved':
        await query.answer("❌ Your account is not approved!", show_alert=True)
        return
    
    # Check working hours
    if not is_within_working_hours():
        await query.answer("⏰ Working hours ended! Come back after 10:30 AM.", show_alert=True)
        return
    
    # Handle regenerate QR code
    if data.startswith("generate_new_"):
        website_index = int(data.split("_")[-1])
        website = WEBSITES[website_index]
        
        user_sessions[user_id]["is_polling"] = False
        
        site_name = get_site_name(website_index)
        await query.edit_message_caption(
            caption=f"🔄 Generating new QR code for {site_name}..."
        )
        
        await generate_and_send_next(context, user_id, website, website_index)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command"""
    user_id = update.effective_user.id
    
    # Check if user is approved
    db_user = await get_user_by_telegram_id(user_id)
    if not db_user or db_user.get('status') != 'approved':
        await update.message.reply_text(
            "❌ Your account is not approved!",
            reply_markup=get_pending_keyboard()
        )
        return
    
    stats = await get_user_stats(user_id)
    
    if stats:
        msg = (
            "📊 Your Statistics:\n\n"
            f"📱 Numbers Added Today: {stats['numbers_added']}\n"
            f"✅ Numbers Completed Today: {stats['numbers_completed']}\n"
            f"💰 Today's Earnings: {stats['today_earnings']:.2f} Taka\n"
            f"💵 Total Earnings: {stats['total_earnings']:.2f} Taka\n\n"
            f"📅 Date: {get_bd_date()}"
        )
    else:
        msg = "❌ Error loading statistics."
    
    await update.message.reply_text(msg, reply_markup=get_keyboard_for_user(user_id))


# ==================== SCHEDULED JOBS ====================

async def daily_reset_job(context: ContextTypes.DEFAULT_TYPE):
    """Daily reset at 8 AM Bangladesh time"""
    logger.info("Running daily reset job...")
    
    success = await reset_daily_data()
    
    if success:
        # Notify all approved users
        users = await get_all_approved_users()
        for user_id in users:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        "🔄 Daily Reset Complete!\n\n"
                        "📅 A new day has started.\n"
                        "⏰ Working Hours: 10:30 AM - 7:00 AM (next day)\n\n"
                        "📱 Send a phone number to start adding."
                    ),
                    reply_markup=get_keyboard_for_user(user_id)
                )
            except Exception as e:
                logger.error(f"Error notifying user {user_id} about reset: {e}")
        
        logger.info("Daily reset completed successfully")
    else:
        logger.error("Daily reset failed")


async def admin_report_job(context: ContextTypes.DEFAULT_TYPE):
    """Send daily report to admin at 3 PM Bangladesh time"""
    logger.info("Running admin report job...")
    
    report_data = await get_daily_report_data()
    
    today = get_bd_date()
    
    if not report_data:
        report_msg = (
            f"📊 Daily Report - {today}\n\n"
            "No activity today."
        )
    else:
        report_msg = f"📊 Daily Report - {today}\n\n"
        
        total_added = 0
        total_completed = 0
        total_earnings = 0
        
        for i, user_data in enumerate(report_data, 1):
            username = user_data.get('username') or user_data.get('first_name') or f"User {user_data['telegram_user_id']}"
            report_msg += (
                f"{i}. {username}\n"
                f"   📱 Added: {user_data['numbers_added']} | "
                f"✅ Completed: {user_data['numbers_completed']} | "
                f"💰 Earnings: {user_data['earnings']:.0f} Tk\n\n"
            )
            total_added += user_data['numbers_added']
            total_completed += user_data['numbers_completed']
            total_earnings += user_data['earnings']
        
        report_msg += (
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📊 Total:\n"
            f"📱 Added: {total_added}\n"
            f"✅ Completed: {total_completed}\n"
            f"💰 Earnings: {total_earnings:.0f} Taka"
        )
    
    try:
        await context.bot.send_message(
            chat_id=ADMIN_USER_ID,
            text=report_msg,
            reply_markup=get_admin_keyboard()
        )
        logger.info("Admin report sent successfully")
    except Exception as e:
        logger.error(f"Error sending admin report: {e}")


def setup_scheduled_jobs(application: Application):
    """Setup scheduled jobs"""
    job_queue = application.job_queue
    
    if job_queue is None:
        logger.warning("JobQueue not available. Scheduled jobs will not run.")
        logger.warning("Install with: pip install 'python-telegram-bot[job-queue]'")
        return
    
    # Daily reset at 8:00 AM Bangladesh time
    reset_time = dt_time(hour=DAILY_RESET_HOUR, minute=DAILY_RESET_MINUTE, tzinfo=BD_TIMEZONE)
    job_queue.run_daily(daily_reset_job, time=reset_time, name="daily_reset")
    logger.info(f"Scheduled daily reset at {reset_time}")
    
    # Admin report at 3:00 PM Bangladesh time
    report_time = dt_time(hour=ADMIN_REPORT_HOUR, minute=ADMIN_REPORT_MINUTE, tzinfo=BD_TIMEZONE)
    job_queue.run_daily(admin_report_job, time=report_time, name="admin_report")
    logger.info(f"Scheduled admin report at {report_time}")


# ==================== MAIN ====================

bot_application = None

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    if bot_application:
        try:
            asyncio.create_task(bot_application.stop())
        except:
            pass
    sys.exit(0)

def main():
    """Start the bot"""
    global bot_application
    
    # Start health check server for Render (in background thread)
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()
    
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
    
    # Create application
    bot_application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    bot_application.add_handler(CommandHandler("start", start))
    bot_application.add_handler(CommandHandler("stats", stats_command))
    bot_application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone_number))
    bot_application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Setup scheduled jobs
    setup_scheduled_jobs(bot_application)
    
    # Start the bot
    logger.info("Bot started!")
    logger.info(f"Admin User ID: {ADMIN_USER_ID}")
    logger.info(f"Working hours: {WORK_START_HOUR}:{WORK_START_MINUTE:02d} - {WORK_END_HOUR}:{WORK_END_MINUTE:02d}")
    logger.info(f"Daily reset at: {DAILY_RESET_HOUR}:{DAILY_RESET_MINUTE:02d}")
    logger.info(f"Admin report at: {ADMIN_REPORT_HOUR}:{ADMIN_REPORT_MINUTE:02d}")
    
    try:
        bot_application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            stop_signals=None
        )
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (KeyboardInterrupt)")
    except Exception as e:
        logger.error(f"Bot error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        logger.info("Bot shutdown complete")
        if bot_application:
            try:
                bot_application.stop()
            except:
                pass


if __name__ == "__main__":
    main()
