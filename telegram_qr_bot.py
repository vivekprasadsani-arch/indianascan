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

# curl_cffi - Real browser TLS fingerprint impersonation!
# This is the KEY to session isolation - each session gets a unique browser fingerprint
try:
    from curl_cffi.requests import Session as CurlSession
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    CurlSession = None

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
BOT_TOKEN = "8419074330:AAGWTpWJd4YiySiOGjhJio4zdjvmrhR7h6Y"

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
WORK_END_HOUR = 23  # 11:00 PM same day
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

import asyncio

# ==================== QUEUE SYSTEM ====================
# Each website can only serve ONE user at a time
# Other users wait in queue - first come, first served!

# Queue structure for each website
# Format: {website_index: {"active_user": user_id or None, "queue": [user_id, ...], "lock": asyncio.Lock}}
website_queues = {}
for i in range(4):  # 4 websites
    website_queues[i] = {
        "active_user": None,
        "queue": [],
        "lock": None,  # Will be created when event loop is running
        "start_time": None
    }

# Maximum time a user can hold a website (10 minutes to match polling timeout)
WEBSITE_TIMEOUT = 600

def get_or_create_lock(website_index):
    """Get or create asyncio lock for a website"""
    if website_queues[website_index]["lock"] is None:
        website_queues[website_index]["lock"] = asyncio.Lock()
    return website_queues[website_index]["lock"]

async def acquire_website_lock(website_index: int, user_id: int, context=None) -> tuple:
    """
    Try to acquire a website for QR generation.
    Returns (success, position_in_queue)
    
    - If website is free: user gets it immediately
    - If website is busy: user waits in queue (returns False, position)
    """
    lock = get_or_create_lock(website_index)
    
    async with lock:
        queue_data = website_queues[website_index]
        current_time = time.time()
        
        # Check if current user's session has timed out
        if queue_data["active_user"] is not None and queue_data["start_time"]:
            if current_time - queue_data["start_time"] > WEBSITE_TIMEOUT:
                logger.info(f"[QUEUE] Timeout for user {queue_data['active_user']} on site {website_index}")
                queue_data["active_user"] = None
                queue_data["start_time"] = None
        
        # If website is free, this user gets it
        if queue_data["active_user"] is None:
            queue_data["active_user"] = user_id
            queue_data["start_time"] = current_time
            # Remove from queue if was waiting
            if user_id in queue_data["queue"]:
                queue_data["queue"].remove(user_id)
            logger.info(f"[QUEUE] ✅ User {user_id} acquired Site {website_index + 1}")
            return True, 0
        
        # If this user already has the website
        if queue_data["active_user"] == user_id:
            queue_data["start_time"] = current_time  # Refresh timeout
            return True, 0
        
        # Website is busy - add to queue
        if user_id not in queue_data["queue"]:
            queue_data["queue"].append(user_id)
        position = queue_data["queue"].index(user_id) + 1
        logger.info(f"[QUEUE] ⏳ User {user_id} waiting at position {position} for Site {website_index + 1}")
        return False, position

async def release_website_lock(website_index: int, user_id: int, context=None):
    """
    Release a website after QR code process is complete.
    Automatically gives access to next user in queue.
    Returns the next user_id if any, or None.
    """
    lock = get_or_create_lock(website_index)
    
    async with lock:
        queue_data = website_queues[website_index]
        
        if queue_data["active_user"] == user_id:
            logger.info(f"[QUEUE] 🔓 User {user_id} released Site {website_index + 1}")
            queue_data["active_user"] = None
            queue_data["start_time"] = None
            
            # Give to next user in queue
            if queue_data["queue"]:
                next_user = queue_data["queue"].pop(0)
                queue_data["active_user"] = next_user
                queue_data["start_time"] = time.time()
                logger.info(f"[QUEUE] ➡️ Site {website_index + 1} given to next user: {next_user}")
                return next_user
        
        return None

def get_queue_position(website_index: int, user_id: int) -> int:
    """Get user's position in queue. 0 = has access, 1+ = waiting, -1 = not in queue"""
    queue_data = website_queues[website_index]
    if queue_data["active_user"] == user_id:
        return 0
    if user_id in queue_data["queue"]:
        return queue_data["queue"].index(user_id) + 1
    return -1

def get_queue_length(website_index: int) -> int:
    """Get total users waiting for a website"""
    return len(website_queues[website_index]["queue"])

def refresh_website_lock_timer(website_index: int, user_id: int):
    """Refresh website lock timer to prevent premature timeout while user is active"""
    queue_data = website_queues.get(website_index)
    if queue_data and queue_data.get("active_user") == user_id:
        queue_data["start_time"] = time.time()

async def cleanup_old_sessions():
    """Clean up sessions older than 10 minutes"""
    global user_qr_sessions
    current_time = time.time()
    cleaned = 0
    
    for user_id in list(user_qr_sessions.keys()):
        for website_index in list(user_qr_sessions[user_id].keys()):
            session_data = user_qr_sessions[user_id].get(website_index, {})
            created_at = session_data.get("created_at", 0)
            if current_time - created_at > 600:  # 10 minutes
                del user_qr_sessions[user_id][website_index]
                cleaned += 1
        if not user_qr_sessions[user_id]:
            del user_qr_sessions[user_id]
    
    if cleaned > 0:
        logger.info(f"[SESSION_CLEANUP] Cleaned up {cleaned} old sessions")

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
    """Check if current time is within working hours (10:30 AM - 3:00 PM)"""
    now = get_bd_time()
    current_time = now.time()
    
    # Working hours: 10:30 AM to 3:00 PM same day
    start_time = dt_time(10, 30)  # 10:30 AM
    end_time = dt_time(15, 0)  # 3:00 PM
    
    # If current time is between 10:30 AM and 3:00 PM, working
    if start_time <= current_time < end_time:
        return True
    
    return False

def get_working_hours_message():
    """Get message about working hours"""
    return (
        "⏰ Working hours ended!\n\n"
        "📅 Working Schedule:\n"
        "• 10:30 AM to 3:00 PM\n\n"
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
    """Get list of pending users (both Telegram and PC)"""
    try:
        result = supabase.table('users').select('*').eq('status', 'pending').order('created_at', desc=True).execute()
        return result.data if result.data else []
    except Exception as e:
        logger.error(f"Error in get_pending_users_list: {e}")
        return []

async def get_pending_pc_users_list():
    """Get list of pending PC users"""
    try:
        result = supabase.table('users').select('*').eq('status', 'pending').eq('user_type', 'pc').order('created_at', desc=True).execute()
        return result.data if result.data else []
    except Exception as e:
        logger.error(f"Error in get_pending_pc_users_list: {e}")
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

# Available browser impersonations for curl_cffi
# Each impersonation has a UNIQUE TLS/JA3 fingerprint - just like real browsers!
BROWSER_IMPERSONATIONS = [
    "chrome110", "chrome107", "chrome104", "chrome101", "chrome100",
    "chrome99", "edge99", "edge101",
    "safari15_3", "safari15_5",
    "chrome99_android",
]

def create_scraper_session():
    """Create a new session with UNIQUE browser TLS fingerprint.
    
    Uses curl_cffi to impersonate real browser TLS fingerprints.
    This is the KEY difference from Python requests - each session
    looks like a DIFFERENT real browser to the API!
    
    Like opening different browser profiles - each has unique fingerprint.
    """
    
    if CURL_CFFI_AVAILABLE:
        # Use curl_cffi with random browser impersonation
        # Each impersonation = unique TLS/JA3 fingerprint!
        impersonate = random.choice(BROWSER_IMPERSONATIONS)
        session = CurlSession(impersonate=impersonate)
        
        # NO PROXY - curl_cffi has real browser fingerprint, should work without proxy!
        # Proxy disabled to test direct connection first
        # session.proxies = {
        #     'http': PROXY_URL,
        #     'https': PROXY_URL
        # }
        
        logger.info(f"[SESSION] Created curl_cffi session - impersonating: {impersonate} (NO PROXY)")
        return session
    else:
        # Fallback to cloudscraper if curl_cffi not available
        logger.warning("[SESSION] curl_cffi not available, using cloudscraper fallback")
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': random.choice(['chrome', 'firefox']),
                'platform': random.choice(['windows', 'linux', 'darwin']),
                'mobile': False
            },
            delay=random.uniform(1, 3)
        )
        scraper.proxies = {
            'http': PROXY_URL,
            'https': PROXY_URL
        }
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


def get_or_create_user_session(user_id, website_index, website):
    """Get existing session or create new one for user/website combination.
    
    CRITICAL: Each user gets a UNIQUE browser fingerprint!
    This is like different browser profiles - each has its own TLS fingerprint.
    """
    global user_qr_sessions
    
    # Initialize user dict if needed
    if user_id not in user_qr_sessions:
        user_qr_sessions[user_id] = {}
    
    # Check if we have an existing valid session (created within last 5 minutes)
    if website_index in user_qr_sessions[user_id]:
        session_data = user_qr_sessions[user_id][website_index]
        created_at = session_data.get("created_at", 0)
        if time.time() - created_at < 300:  # 5 minutes
            impersonate = session_data.get("impersonate", "unknown")
            logger.info(f"[SESSION] Reusing session for user {user_id}, website {website_index}, fingerprint: {impersonate}")
            return session_data["scraper"], session_data["headers"]
    
    # Assign a UNIQUE browser fingerprint to this user
    # Use user_id to deterministically select fingerprint (consistent per user)
    if CURL_CFFI_AVAILABLE:
        # Each user gets a consistent fingerprint based on their ID
        fingerprint_index = (user_id + website_index) % len(BROWSER_IMPERSONATIONS)
        impersonate = BROWSER_IMPERSONATIONS[fingerprint_index]
        
        session = CurlSession(impersonate=impersonate)
        # NO PROXY - real browser fingerprint should work without proxy
        # session.proxies = {
        #     'http': PROXY_URL,
        #     'https': PROXY_URL
        # }
        
        logger.info(f"[SESSION] NEW session for user {user_id}, website {website_index} - fingerprint: {impersonate} (NO PROXY)")
    else:
        # Fallback
        session = create_scraper_session()
        impersonate = "cloudscraper"
        logger.info(f"[SESSION] NEW session (fallback) for user {user_id}, website {website_index}")
    
    headers = get_headers_for_website(website)
    
    # Pre-store the session BEFORE any requests
    user_qr_sessions[user_id][website_index] = {
        "scraper": session,
        "headers": headers,
        "impersonate": impersonate,  # Track which fingerprint this user has
        "qr_data": None,
        "qr_token": None,
        "qr_unique_id": None,
        "session_id": None,
        "created_at": time.time()
    }
    
    return session, headers


def generate_qr_code(website, user_id, website_index, max_retries=15):
    """Generate QR code for a website with retry mechanism using cloudscraper
    
    CRITICAL: Uses persistent session per user/website to maintain cookies like a browser.
    
    Args:
        website: Website configuration dict
        user_id: Telegram user ID for session isolation
        website_index: Index of website for session storage
        max_retries: Maximum number of retry attempts (increased for concurrent users)
    
    Returns:
        tuple: (qr_image_bytes, error_message)
    """
    base_url = website['base_url']
    code = website['code']  # Use the original referral code
    
    # Get or create persistent session for this user - SAME session used throughout!
    scraper, headers = get_or_create_user_session(user_id, website_index, website)
    
    for retry in range(max_retries):
        try:
            # IMPORTANT: Use the SAME scraper throughout - don't create new one!
            # This maintains cookies like a browser does
            
            # Add small random delay only on first attempt or after error
            if retry > 0:
                retry_delay = random.uniform(2 + (retry * 0.5), 4 + (retry * 1))
                logger.info(f"[GENERATE_QR] Retry {retry + 1}, waiting {retry_delay:.1f}s...")
                time.sleep(retry_delay)
            else:
                # Small initial delay to spread concurrent users
                time.sleep(random.uniform(0.1, 0.5))
            
            # Step 1: Generate QR code - using persistent session with cookies!
            generate_url = f"{base_url}/qrcode/generate"
            generate_payload = {"code": code}
            
            logger.info(f"[GENERATE_QR] User {user_id}, Attempt {retry + 1}/{max_retries} for {website['name']} (persistent session)")
            response = scraper.post(generate_url, json=generate_payload, headers=headers, timeout=30)
            
            if response.status_code != 200:
                if retry < max_retries - 1:
                    logger.warning(f"[GENERATE_QR] HTTP {response.status_code}, retrying with new session...")
                    time.sleep(random.uniform(3, 6))
                    continue
                return None, f"HTTP Error: {response.status_code}"
            
            generate_data = response.json()
            logger.info(f"[GENERATE_QR] User {user_id} - Generate response: {json.dumps(generate_data)[:500]}")
            
            if generate_data.get("code") != 0:
                error_msg = generate_data.get('msg', 'Unknown error')
                # Check if site is busy/in use - retry with longer delay
                is_busy = any(keyword in error_msg.lower() for keyword in ['in use', 'busy', 'wait', 'another user', 'try again'])
                
                if retry < max_retries - 1:
                    if is_busy:
                        # Site is busy - wait longer and retry
                        wait_time = random.uniform(5, 10)
                        logger.warning(f"[GENERATE_QR] Site busy for user {user_id}, waiting {wait_time:.1f}s before retry...")
                        time.sleep(wait_time)
                    else:
                        logger.warning(f"[GENERATE_QR] API error: {error_msg}, retrying...")
                        time.sleep(random.uniform(2, 4))
                    continue
                return None, f"Error: {error_msg}"
            
            # Extract session/token from generate response
            gen_data = generate_data.get("data", {})
            session_id = gen_data.get("sessionId") or gen_data.get("session_id") or gen_data.get("id") or gen_data.get("token")
            logger.info(f"[GENERATE_QR] User {user_id} - Session ID from generate: {session_id}")
            
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
                        # Get ALL possible unique identifiers from the response
                        qr_token = (
                            data.get("token") or data.get("id") or data.get("session_id") or
                            data.get("sessionId") or data.get("qr_id") or data.get("qrId") or
                            data.get("uuid") or data.get("key") or session_id
                        )
                        logger.info(f"[GENERATE_QR] User {user_id} - Retrieve data keys: {list(data.keys()) if isinstance(data, dict) else 'not dict'}")
                        logger.info(f"[GENERATE_QR] User {user_id} - QR token: {qr_token}, QR array length: {len(qrcode_array) if qrcode_array else 0}")
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
            
            # Extract unique ID from QR data (WhatsApp linking URL)
            # QR data format might be like: "2@UNIQUE_ID,timestamp,..." or "https://...?code=UNIQUE_ID"
            qr_unique_id = None
            if qr_data:
                # Try to extract ID from QR data string
                if "," in qr_data:
                    # Format: "2@ID,timestamp,..." 
                    parts = qr_data.split(",")
                    if parts:
                        qr_unique_id = parts[0].replace("2@", "").replace("1@", "")
                elif "code=" in qr_data:
                    # Format: URL with code parameter
                    import urllib.parse
                    parsed = urllib.parse.urlparse(qr_data)
                    params = urllib.parse.parse_qs(parsed.query)
                    qr_unique_id = params.get("code", [None])[0]
                else:
                    # Use first 32 chars as ID
                    qr_unique_id = qr_data[:32] if len(qr_data) > 32 else qr_data
            
            logger.info(f"[GENERATE_QR] User {user_id} - QR unique ID extracted: {qr_unique_id[:20] if qr_unique_id else None}...")
            
            # Update the existing session with QR data (session/cookies already stored)
            if user_id in user_qr_sessions and website_index in user_qr_sessions[user_id]:
                user_qr_sessions[user_id][website_index].update({
                    "qr_data": qr_data,
                    "qr_token": qr_token or qr_unique_id,
                    "qr_unique_id": qr_unique_id,
                    "session_id": session_id,
                })
            logger.info(f"[GENERATE_QR] Updated session for user {user_id}, website {website_index}, token: {qr_token or qr_unique_id}")
            
            # Log cookies for debugging - this is key to session isolation
            try:
                cookies = dict(scraper.cookies)
                logger.info(f"[GENERATE_QR] User {user_id} - Session cookies: {list(cookies.keys())}")
            except:
                pass
            
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
    """Check login status for a website using the user's PERSISTENT stored session
    
    CRITICAL: Must use the SAME scraper session (with cookies) that was used for QR generation!
    This is how browsers maintain session identity.
    
    Args:
        website: Website configuration dict
        user_id: Telegram user ID for session isolation
        website_index: Index of website to check status for
    """
    try:
        base_url = website['base_url']
        code = website['code']  # Use the original referral code
        
        # Get the stored session for this user/website - MUST exist from QR generation
        session_data = None
        if user_id in user_qr_sessions and website_index in user_qr_sessions[user_id]:
            session_data = user_qr_sessions[user_id][website_index]
        
        # MUST use the stored scraper session - this has the cookies!
        if session_data and session_data.get("scraper"):
            scraper = session_data["scraper"]
            headers = session_data.get("headers") or get_headers_for_website(website)
            logger.info(f"[CHECK_STATUS] Using PERSISTENT session for user {user_id}, website {website_index}")
            
            # Log cookies for debugging
            try:
                cookies = dict(scraper.cookies)
                logger.info(f"[CHECK_STATUS] User {user_id} - Session cookies: {list(cookies.keys())}")
            except:
                pass
        else:
            # This shouldn't happen - log error
            logger.error(f"[CHECK_STATUS] NO stored session for user {user_id}, website {website_index}! Creating new (may fail)")
            scraper = create_scraper_session()
            headers = get_headers_for_website(website)
        
        status_url = f"{base_url}/login/status"
        status_payload = {"code": code}
        
        # Add ALL possible session identifiers
        if session_data:
            if session_data.get("qr_token"):
                status_payload["token"] = session_data["qr_token"]
            if session_data.get("session_id"):
                status_payload["sessionId"] = session_data["session_id"]
                status_payload["session_id"] = session_data["session_id"]
            if session_data.get("qr_unique_id"):
                status_payload["qrId"] = session_data["qr_unique_id"]
                status_payload["id"] = session_data["qr_unique_id"]
        
        logger.info(f"[CHECK_STATUS] User {user_id} - Payload: {json.dumps(status_payload)[:200]}")
        response = scraper.post(status_url, json=status_payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            status_data = response.json()
            logger.info(f"[CHECK_STATUS] User {user_id} - Response: {json.dumps(status_data)[:500]}")
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
        
        # Check for pending PC user notifications
        await check_and_notify_pc_users(context)
        
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
            "⏰ Working Hours: 10:30 AM - 3:00 PM\n"
            "🔄 Daily reset at 8:00 AM"
            f"{stats_msg}"
        )
        
        await update.message.reply_text(welcome_msg, reply_markup=get_user_keyboard())


async def check_and_notify_pc_users(context: ContextTypes.DEFAULT_TYPE):
    """Check for new PC user registrations and notify admin"""
    try:
        # Get unprocessed PC user notifications
        result = supabase.table('admin_notifications').select('*').eq('notification_type', 'new_pc_user').eq('is_processed', False).order('created_at', desc=True).execute()
        
        if not result.data or len(result.data) == 0:
            return
        
        # Get pending PC users
        from backend_core import get_pending_pc_users_list
        pending_pc_users = await get_pending_pc_users_list()
        
        # Send notification for each new PC user
        for notification in result.data:
            mobile_number = notification.get('mobile_number')
            if not mobile_number:
                continue
            
            # Find the user
            user = None
            for u in pending_pc_users:
                if u.get('mobile_number') == mobile_number:
                    user = u
                    break
            
            if not user:
                # Mark as processed even if user not found
                supabase.table('admin_notifications').update({'is_processed': True}).eq('id', notification['id']).execute()
                continue
            
            # Send notification to admin
            first_name = user.get('first_name', '')
            last_name = user.get('last_name', '')
            name = f"{first_name} {last_name}".strip() if (first_name or last_name) else "PC User"
            
            admin_msg = (
                "💻 New PC User Registration!\n\n"
                f"📱 Mobile Number: {mobile_number}\n"
                f"👤 Name: {name}\n"
                f"📅 Registered: {user.get('created_at', 'N/A')[:10] if user.get('created_at') else 'N/A'}\n\n"
                "What would you like to do?"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"approve_pc_{mobile_number}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject_pc_{mobile_number}")
                ]
            ]
            
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_USER_ID,
                    text=admin_msg,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                
                # Mark notification as processed
                supabase.table('admin_notifications').update({'is_processed': True}).eq('id', notification['id']).execute()
                logger.info(f"Admin notified about PC user: {mobile_number}")
            except Exception as e:
                logger.error(f"Error notifying admin about PC user: {e}")
    
    except Exception as e:
        logger.error(f"Error checking PC user notifications: {e}")


async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin approval/rejection callbacks (both Telegram and PC users)"""
    query = update.callback_query
    await query.answer()
    
    admin_id = query.from_user.id
    
    # Check if user is admin
    if admin_id != ADMIN_USER_ID:
        await query.answer("❌ You are not an admin!", show_alert=True)
        return
    
    data = query.data
    
    if data.startswith("approve_"):
        identifier = data.split("_", 1)[1]  # Get everything after "approve_"
        
        # Check if it's a PC user (starts with "pc_")
        if identifier.startswith("pc_"):
            # PC user - use mobile number
            mobile_number = identifier.replace("pc_", "")
            
            # Import PC user functions from backend_core
            from backend_core import update_user_status_pc
            
            # Update PC user status
            result = await update_user_status_pc(mobile_number, 'approved', admin_id)
            
            if result:
                # PC users can't be notified via Telegram, so just log
                logger.info(f"PC user {mobile_number} approved by admin {admin_id}")
                
                await query.edit_message_text(
                    f"{query.message.text}\n\n✅ Approved! (PC User)\n📱 Mobile: {mobile_number}"
                )
                await query.answer("✅ PC User approved successfully!", show_alert=True)
            else:
                await query.answer("❌ Error approving user. Please try again.", show_alert=True)
        else:
            # Telegram user - use Telegram ID
            target_user_id = int(identifier)
            
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
                        "⏰ Working Hours: 10:30 AM - 3:00 PM"
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
        identifier = data.split("_", 1)[1]  # Get everything after "reject_"
        
        # Check if it's a PC user
        if identifier.startswith("pc_"):
            # PC user - use mobile number
            mobile_number = identifier.replace("pc_", "")
            
            # Import PC user functions from backend_core
            from backend_core import update_user_status_pc
            
            # Update PC user status
            result = await update_user_status_pc(mobile_number, 'rejected', admin_id)
            
            if result:
                logger.info(f"PC user {mobile_number} rejected by admin {admin_id}")
                
                await query.edit_message_text(
                    f"{query.message.text}\n\n❌ Rejected! (PC User)\n📱 Mobile: {mobile_number}"
                )
                await query.answer("❌ PC User rejected", show_alert=True)
            else:
                await query.answer("❌ Error rejecting user. Please try again.", show_alert=True)
        else:
            # Telegram user
            target_user_id = int(identifier)
            
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
            "• 10:30 AM to 3:00 PM\n"
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
            f"• End: 3:00 PM\n\n"
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
            # Check for new PC user notifications first
            await check_and_notify_pc_users(context)
            
            users = await get_pending_users_list()
            
            if not users:
                msg = "⏳ No pending users."
            else:
                msg = f"⏳ Pending Users ({len(users)}):\n\n"
                for u in users:
                    # Check if PC user (has mobile_number and no telegram_user_id or user_type is 'pc')
                    mobile = u.get('mobile_number')
                    telegram_id = u.get('telegram_user_id')
                    user_type = u.get('user_type', 'telegram')
                    
                    # Determine if PC user
                    is_pc_user = (user_type == 'pc') or (mobile and not telegram_id)
                    
                    if is_pc_user:
                        # PC user - show mobile number
                        mobile = mobile or 'N/A'
                        username = f"PC User"
                        display_name = f"PC User: {mobile}"
                        identifier = f"pc_{mobile}"  # Use mobile number as identifier
                        user_type_emoji = "💻"
                        display_msg = f"👤 {display_name}\n📱 Mobile: {mobile}"
                    else:
                        # Telegram user
                        username = u.get('username') or u.get('first_name') or 'Telegram User'
                        telegram_id = telegram_id or 'N/A'
                        display_name = username
                        identifier = str(telegram_id) if telegram_id != 'N/A' else 'unknown'
                        user_type_emoji = "📱"
                        display_msg = f"👤 {display_name}\n🆔 Telegram ID: {telegram_id}"
                    
                    msg += f"{user_type_emoji} {display_name}\n"
                    
                    # Send approval buttons
                    keyboard = [
                        [
                            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{identifier}"),
                            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{identifier}")
                        ]
                    ]
                    
                    await update.message.reply_text(
                        display_msg,
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
    
    # Try to acquire lock for this website
    got_lock, queue_position = await acquire_website_lock(current_index, user_id)
    
    # Show progress message (same message whether waiting or not)
    progress_bar = "▓▓▓░░░░░░░"  # Initial progress
    loading_msg = await update.message.reply_text(
        f"📱 {format_phone_number(phone)}\n\n"
        f"🔄 Generating QR Code for {site_name}...\n"
        f"{progress_bar}\n\n"
        f"⏳ Please wait...",
        reply_markup=get_keyboard_for_user(user_id)
    )
    user_sessions[user_id]["last_message_id"] = loading_msg.message_id
    
    if not got_lock:
        # User needs to wait in queue - but we don't tell them "busy"
        # Just show "generating" and wait for their turn
        user_sessions[user_id]["waiting_for_lock"] = True
        user_sessions[user_id]["phone_for_queue"] = phone
        
        # Start checking for lock availability
        async def check_queue_job(ctx):
            await check_and_proceed_from_queue(ctx, user_id, current_index, loading_msg.message_id)
        
        context.job_queue.run_once(check_queue_job, when=3)
        return
    
    # Got lock immediately - update progress message
    try:
        await loading_msg.edit_text(
            f"📱 {format_phone_number(phone)}\n\n"
            f"🔄 Generating QR Code for {site_name}...\n"
            f"▓▓▓▓▓▓▓▓▓▓\n\n"
            f"✨ Almost ready..."
        )
    except:
        pass
    
    # Generate QR code - session is stored per user/website automatically
    qr_image, error = generate_qr_code(website, user_id, current_index)
    
    if error:
        await release_website_lock(current_index, user_id)
        await loading_msg.edit_text(
            f"❌ Error: {error}\n\nPlease send your phone number again.",
            reply_markup=get_keyboard_for_user(user_id)
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


async def check_and_proceed_from_queue(context: ContextTypes.DEFAULT_TYPE, user_id: int, website_index: int, msg_id: int = None):
    """Check if user can proceed from queue and start QR generation.
    Shows only progress bar - no 'busy' message to user!
    """
    try:
        if user_id not in user_sessions:
            return
        
        # Try to get the lock
        got_lock, queue_position = await acquire_website_lock(website_index, user_id)
        
        website = WEBSITES[website_index]
        site_name = get_site_name(website_index)
        phone = user_sessions[user_id].get("current_phone_number", "")
        phone_display = format_phone_number(phone) if phone else ""
        last_msg_id = msg_id or user_sessions[user_id].get("last_message_id")
        
        # Get progress animation frame
        wait_count = user_sessions[user_id].get("wait_count", 0) + 1
        user_sessions[user_id]["wait_count"] = wait_count
        
        # Animated progress bar
        progress_frames = [
            "▓░░░░░░░░░",
            "▓▓░░░░░░░░",
            "▓▓▓░░░░░░░",
            "▓▓▓▓░░░░░░",
            "▓▓▓▓▓░░░░░",
            "▓▓▓▓▓▓░░░░",
            "▓▓▓▓▓▓▓░░░",
            "▓▓▓▓▓▓▓▓░░",
            "▓▓▓▓▓▓▓▓▓░",
            "░▓▓▓▓▓▓▓▓▓",
            "░░▓▓▓▓▓▓▓▓",
            "░░░▓▓▓▓▓▓▓",
        ]
        progress_bar = progress_frames[wait_count % len(progress_frames)]
        
        if not got_lock:
            # Still waiting - show animated progress (no "busy" message!)
            if last_msg_id:
                try:
                    await context.bot.edit_message_text(
                        chat_id=user_id,
                        message_id=last_msg_id,
                        text=(
                            f"📱 {phone_display}\n\n"
                            f"🔄 Generating QR Code for {site_name}...\n"
                            f"{progress_bar}\n\n"
                            f"⏳ Please wait..."
                        ),
                        reply_markup=get_keyboard_for_user(user_id)
                    )
                except:
                    pass
            
            # Check again in 3 seconds
            async def check_again(ctx):
                await check_and_proceed_from_queue(ctx, user_id, website_index, last_msg_id)
            
            context.job_queue.run_once(check_again, when=3)
            return
        
        # Got the lock! Generate QR code
        user_sessions[user_id]["waiting_for_lock"] = False
        user_sessions[user_id]["wait_count"] = 0
        
        # Update message to show generating (almost done!)
        if last_msg_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=user_id,
                    message_id=last_msg_id,
                    text=(
                        f"📱 {phone_display}\n\n"
                        f"🔄 Generating QR Code for {site_name}...\n"
                        f"▓▓▓▓▓▓▓▓▓▓\n\n"
                        f"✨ Almost ready..."
                    )
                )
            except:
                pass
        
        logger.info(f"[QUEUE] User {user_id} got lock, generating QR for {site_name}")
        
        # Generate QR code
        qr_image, error = generate_qr_code(website, user_id, website_index)
        
        if error:
            await release_website_lock(website_index, user_id)
            if last_msg_id:
                try:
                    await context.bot.edit_message_text(
                        chat_id=user_id,
                        message_id=last_msg_id,
                        text=f"❌ Error: {error}\n\nPlease send your phone number again.",
                        reply_markup=get_keyboard_for_user(user_id)
                    )
                except:
                    pass
            return
        
        # Get completed count for progress bar
        completed_count = len(user_completed_websites.get(user_id, []))
        progress = '✅' * completed_count + '⬜' * (4 - completed_count)
        
        # Send QR code image
        qr_image.seek(0)
        sent_message = await context.bot.send_photo(
            chat_id=user_id,
            photo=qr_image,
            caption=(
                f"📱 {phone_display}\n\n"
                f"🌐 {site_name} - Scan with WhatsApp\n"
                f"⏳ Waiting for scan...\n\n"
                f"Progress: [{progress}] {completed_count}/4"
            ),
            reply_markup=create_website_keyboard(website_index)
        )
        
        # Delete old waiting message
        if last_msg_id:
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=last_msg_id)
            except:
                pass
        
        user_sessions[user_id]["last_message_id"] = sent_message.message_id
        user_sessions[user_id]["is_polling"] = True
        user_sessions[user_id]["poll_count"] = 0
        
        # Start polling
        async def poll_job(ctx):
            await poll_login_status(ctx, user_id, website, website_index)
        
        context.job_queue.run_once(poll_job, when=5)
        
    except Exception as e:
        logger.error(f"[QUEUE] Error in check_and_proceed_from_queue: {e}")
        import traceback
        traceback.print_exc()


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
        
        # Keep the queue lock alive while this user is actively waiting
        refresh_website_lock_timer(website_index, user_id)
        
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
            
            # Release lock for this website since user completed it
            await release_website_lock(website_index, user_id)
            logger.info(f"[QUEUE] Released lock for website {website_index} after user {user_id} completed")
            
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
                
                # Store completed phone for re-scan
                user_sessions[user_id]["last_completed_phone"] = current_phone
                user_sessions[user_id]["last_completed_phone_display"] = phone_display
                
                # Send re-scan options message
                try:
                    await context.bot.send_message(
                        chat_id=user_id, 
                        text=(
                            f"🎉 All 4 sites completed for {phone_display}!\n\n"
                            f"📱 Send a new phone number to continue.\n\n"
                            f"🔄 Or re-scan any site if needed (for unlinked accounts):"
                        ),
                        reply_markup=create_rescan_keyboard()
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
                # Release lock since QR expired
                await release_website_lock(website_index, user_id)
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
        
        # Get completed count for progress bar
        completed_count = len(user_completed_websites.get(user_id, []))
        progress = '✅' * completed_count + '⬜' * (4 - completed_count)
        
        # Get phone number for display
        phone = user_sessions[user_id].get("current_phone_number", "")
        phone_display = format_phone_number(phone) if phone else ""
        site_name = get_site_name(website_index)
        
        # Try to acquire lock for this website
        got_lock, queue_position = await acquire_website_lock(website_index, user_id)
        
        if not got_lock:
            # User needs to wait in queue - show progress bar, not "busy"
            wait_count = user_sessions[user_id].get("wait_count_next", 0) + 1
            user_sessions[user_id]["wait_count_next"] = wait_count
            
            # Animated progress bar
            progress_frames = ["▓░░░░░░░░░", "▓▓░░░░░░░░", "▓▓▓░░░░░░░", "▓▓▓▓░░░░░░", 
                              "▓▓▓▓▓░░░░░", "▓▓▓▓▓▓░░░░", "▓▓▓▓▓▓▓░░░", "▓▓▓▓▓▓▓▓░░"]
            progress_bar = progress_frames[wait_count % len(progress_frames)]
            
            last_msg_id = user_sessions[user_id].get("last_message_id")
            if last_msg_id:
                try:
                    await context.bot.edit_message_caption(
                        chat_id=user_id,
                        message_id=last_msg_id,
                        caption=(
                            f"📱 {phone_display}\n\n"
                            f"🔄 Generating QR Code for {site_name}...\n"
                            f"{progress_bar}\n\n"
                            f"Progress: [{progress}] {completed_count}/4\n"
                            f"⏳ Please wait..."
                        ),
                        reply_markup=None
                    )
                except:
                    pass
            
            # Check queue again in 3 seconds
            async def check_queue_next(ctx):
                await generate_and_send_next(ctx, user_id, website, website_index)
            
            context.job_queue.run_once(check_queue_next, when=3)
            return
        
        # Got lock - reset wait count
        user_sessions[user_id]["wait_count_next"] = 0
        
        logger.info(f"[GENERATE_NEXT] Generating QR code for {website['name']} (user {user_id})...")
        qr_image, error = generate_qr_code(website, user_id, website_index)
        
        if error:
            logger.error(f"[GENERATE_NEXT] Error generating QR: {error}")
            site_name = get_site_name(website_index)
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


def create_website_keyboard(website_index: int, show_next=False, is_rescan=False):
    """Create inline keyboard for QR code actions"""
    keyboard = []
    
    # Navigation buttons for re-scan mode
    if is_rescan:
        nav_row = []
        if website_index > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"rescan_{website_index - 1}"))
        if website_index < len(WEBSITES) - 1:
            nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"rescan_{website_index + 1}"))
        if nav_row:
            keyboard.append(nav_row)
    
    # Regenerate button
    keyboard.append([InlineKeyboardButton("🔄 Regenerate QR", callback_data=f"generate_new_{website_index}")])
    
    return InlineKeyboardMarkup(keyboard)


def create_rescan_keyboard():
    """Create keyboard for re-scanning after completion"""
    keyboard = []
    
    # Create buttons for each website
    for i, website in enumerate(WEBSITES):
        site_name = get_site_name(i)
        keyboard.append([InlineKeyboardButton(f"🔄 Re-scan {site_name}", callback_data=f"rescan_{i}")])
    
    keyboard.append([InlineKeyboardButton("📱 Add New Number", callback_data="new_number")])
    
    return InlineKeyboardMarkup(keyboard)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    # Handle admin callbacks (both approve_ and reject_)
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
    
    # Handle re-scan for completed numbers (unlinked accounts)
    elif data.startswith("rescan_"):
        website_index = int(data.split("_")[-1])
        website = WEBSITES[website_index]
        site_name = get_site_name(website_index)
        
        # Get the last completed phone number
        last_phone = user_sessions.get(user_id, {}).get("last_completed_phone")
        last_phone_display = user_sessions.get(user_id, {}).get("last_completed_phone_display", "")
        
        if not last_phone:
            await query.answer("❌ No completed number found. Please add a new number first.", show_alert=True)
            return
        
        # Set re-scan mode
        user_sessions[user_id]["is_rescan_mode"] = True
        user_sessions[user_id]["current_phone_number"] = last_phone
        user_sessions[user_id]["current_index"] = website_index
        user_sessions[user_id]["is_polling"] = False
        
        # Update message
        try:
            await query.edit_message_text(
                text=f"🔄 Re-scanning {site_name} for {last_phone_display}...\n\n⏳ Generating QR code..."
            )
        except:
            pass
        
        # Generate QR code for re-scan (no queue needed, no success tracking)
        await generate_rescan_qr(context, user_id, website, website_index)
    
    # Handle new number request
    elif data == "new_number":
        # Clear re-scan mode
        if user_id in user_sessions:
            user_sessions[user_id]["is_rescan_mode"] = False
            user_sessions[user_id]["last_completed_phone"] = None
        
        await query.edit_message_text(
            text="📱 Send a new phone number to start adding.",
            reply_markup=None
        )


async def generate_rescan_qr(context: ContextTypes.DEFAULT_TYPE, user_id: int, website: dict, website_index: int):
    """Generate QR code for re-scanning (no success tracking, no queue)
    
    This is for users who completed all 4 sites but need to re-scan
    because WhatsApp got unlinked.
    """
    try:
        site_name = get_site_name(website_index)
        phone = user_sessions[user_id].get("current_phone_number", "")
        phone_display = format_phone_number(phone) if phone else ""
        
        # Generate QR code directly (no queue for re-scan)
        qr_image, error = generate_qr_code(website, user_id, website_index)
        
        if error:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"❌ Error generating QR: {error}\n\nPlease try again.",
                reply_markup=create_rescan_keyboard()
            )
            return
        
        # Send QR code with navigation buttons
        qr_image.seek(0)
        sent_message = await context.bot.send_photo(
            chat_id=user_id,
            photo=qr_image,
            caption=(
                f"🔄 Re-scan Mode\n\n"
                f"📱 {phone_display}\n"
                f"🌐 {site_name}\n\n"
                f"📲 Scan with WhatsApp to re-link.\n"
                f"(No success tracking - just scan and you're done!)\n\n"
                f"Use ⬅️/➡️ to switch sites."
            ),
            reply_markup=create_website_keyboard(website_index, is_rescan=True)
        )
        
        user_sessions[user_id]["last_message_id"] = sent_message.message_id
        
        # No polling for re-scan mode - user just scans and moves on
        
    except Exception as e:
        logger.error(f"Error in generate_rescan_qr: {e}")
        import traceback
        traceback.print_exc()


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
                        "⏰ Working Hours: 10:30 AM - 3:00 PM\n\n"
                        "📱 Send a phone number to start adding."
                    ),
                    reply_markup=get_keyboard_for_user(user_id)
                )
            except Exception as e:
                logger.error(f"Error notifying user {user_id} about reset: {e}")
        
        logger.info("Daily reset completed successfully")
    else:
        logger.error("Daily reset failed")


async def check_pc_users_periodic(context: ContextTypes.DEFAULT_TYPE):
    """Periodically check for new PC user registrations and notify admin"""
    try:
        await check_and_notify_pc_users(context)
    except Exception as e:
        logger.error(f"Error in periodic PC user check: {e}")


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
    
    # Check for PC user notifications every 2 minutes
    job_queue.run_repeating(check_pc_users_periodic, interval=120, first=10, name="check_pc_users")
    logger.info("Scheduled PC user notification check every 2 minutes")


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
