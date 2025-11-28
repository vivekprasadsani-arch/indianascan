"""
Shared Backend Core Module
Contains all core functionality for both Telegram bot and PC GUI tool
"""
import requests
import qrcode
import time
import json
import re
import asyncio
import random
import logging
import pytz
from datetime import datetime, timedelta, time as dt_time
from qrcode import QRCode
from PIL import Image
import io
from supabase import create_client, Client
import cloudscraper
from fake_useragent import UserAgent

# curl_cffi - Real browser TLS fingerprint impersonation!
try:
    from curl_cffi.requests import Session as CurlSession
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    CurlSession = None

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================

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

# Browser impersonations for curl_cffi
BROWSER_IMPERSONATIONS = [
    "chrome110", "chrome111", "chrome112", "chrome113", "chrome114", "chrome115",
    "chrome116", "chrome117", "chrome118", "chrome119", "chrome120", "chrome121",
    "edge110", "edge111", "edge112", "edge113", "edge114", "edge115",
    "safari15_3", "safari15_5", "safari16_0", "safari17_0"
]

# User Agent
ua = UserAgent()

# ==================== SUPABASE CLIENT ====================

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==================== SESSION MANAGEMENT ====================

# Store active sessions per user with unique QR data
# Format: {user_id: {website_index: {"qr_token": str, "scraper": scraper_instance}}}
user_qr_sessions = {}

# ==================== QUEUE SYSTEM ====================

# Queue structure for each website
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

# ==================== HELPER FUNCTIONS ====================

def get_bd_time():
    """Get current Bangladesh time"""
    return datetime.now(BD_TIMEZONE)

def get_bd_date():
    """Get current Bangladesh date"""
    return get_bd_time().date()

def is_within_working_hours():
    """Check if current time is within working hours (10:30 AM - 11:00 PM)"""
    now = get_bd_time()
    current_time = now.time()
    
    # Working hours: 10:30 AM to 11:00 PM same day
    start_time = dt_time(WORK_START_HOUR, WORK_START_MINUTE)  # 10:30 AM
    end_time = dt_time(WORK_END_HOUR, WORK_END_MINUTE)  # 11:00 PM
    
    # If current time is between start and end, working
    if start_time <= current_time <= end_time:
        return True
    
    return False

def get_working_hours_message():
    """Get message about working hours"""
    return (
        "⏰ Working hours ended!\n\n"
        "📅 Working Schedule:\n"
        f"• {WORK_START_HOUR}:{WORK_START_MINUTE:02d} AM to {WORK_END_HOUR}:00 PM\n\n"
        f"⏳ Please try again after {WORK_START_HOUR}:{WORK_START_MINUTE:02d} AM."
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

# ==================== SESSION CREATION ====================

def create_scraper_session():
    """
    Create a scraper session with real browser TLS fingerprint impersonation.
    Uses curl_cffi to impersonate real browser TLS fingerprints.
    """
    if CURL_CFFI_AVAILABLE:
        impersonate = random.choice(BROWSER_IMPERSONATIONS)
        session = CurlSession(impersonate=impersonate)
        logger.info(f"[SESSION] Created curl_cffi session - impersonating: {impersonate} (NO PROXY)")
        return session
    else:
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
    ]
    return random.choice(user_agents)

def get_headers_for_website(website):
    """Get headers customized for each website"""
    domain = website['base_url'].split('/')[2]
    user_agent = get_random_user_agent()
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
    """Get existing session or create new one for user/website combination."""
    global user_qr_sessions
    
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
    if CURL_CFFI_AVAILABLE:
        fingerprint_index = (user_id + website_index) % len(BROWSER_IMPERSONATIONS)
        impersonate = BROWSER_IMPERSONATIONS[fingerprint_index]
        session = CurlSession(impersonate=impersonate)
        logger.info(f"[SESSION] NEW session for user {user_id}, website {website_index} - fingerprint: {impersonate} (NO PROXY)")
    else:
        session = create_scraper_session()
        impersonate = "cloudscraper"
        logger.info(f"[SESSION] NEW session (fallback) for user {user_id}, website {website_index}")
    
    headers = get_headers_for_website(website)
    
    # Pre-store the session BEFORE any requests
    user_qr_sessions[user_id][website_index] = {
        "scraper": session,
        "headers": headers,
        "impersonate": impersonate,
        "qr_data": None,
        "qr_token": None,
        "qr_unique_id": None,
        "session_id": None,
        "created_at": time.time()
    }
    
    return session, headers

# ==================== QR CODE GENERATION ====================

def generate_qr_code(website, user_id, website_index, max_retries=15):
    """Generate QR code for a website with retry mechanism"""
    base_url = website['base_url']
    code = website['code']
    
    # Get or create persistent session for this user
    scraper, headers = get_or_create_user_session(user_id, website_index, website)
    
    for retry in range(max_retries):
        try:
            if retry > 0:
                retry_delay = random.uniform(2 + (retry * 0.5), 4 + (retry * 1))
                logger.info(f"[GENERATE_QR] Retry {retry + 1}, waiting {retry_delay:.1f}s...")
                time.sleep(retry_delay)
            else:
                time.sleep(random.uniform(0.1, 0.5))
            
            # Step 1: Generate QR code
            generate_url = f"{base_url}/qrcode/generate"
            generate_payload = {"code": code}
            
            logger.info(f"[GENERATE_QR] User {user_id}, Attempt {retry + 1}/{max_retries} for {website['name']}")
            response = scraper.post(generate_url, json=generate_payload, headers=headers, timeout=30)
            
            if response.status_code != 200:
                if retry < max_retries - 1:
                    logger.warning(f"[GENERATE_QR] HTTP {response.status_code}, retrying...")
                    time.sleep(random.uniform(3, 6))
                    continue
                return None, f"HTTP Error: {response.status_code}"
            
            generate_data = response.json()
            logger.info(f"[GENERATE_QR] User {user_id} - Generate response: {json.dumps(generate_data)[:500]}")
            
            if generate_data.get("code") != 0:
                error_msg = generate_data.get('msg', 'Unknown error')
                is_busy = any(keyword in error_msg.lower() for keyword in ['in use', 'busy', 'wait', 'another user', 'try again'])
                
                if retry < max_retries - 1:
                    if is_busy:
                        wait_time = random.uniform(5, 10)
                        logger.warning(f"[GENERATE_QR] Site busy for user {user_id}, waiting {wait_time:.1f}s...")
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
                        qr_token = (
                            data.get("token") or data.get("id") or data.get("session_id") or
                            data.get("sessionId") or data.get("qr_id") or data.get("qrId") or
                            data.get("uuid") or data.get("key") or session_id
                        )
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
            
            # Extract unique ID from QR data
            qr_unique_id = None
            if qr_data:
                if "," in qr_data:
                    parts = qr_data.split(",")
                    if parts:
                        qr_unique_id = parts[0].replace("2@", "").replace("1@", "")
                elif "code=" in qr_data:
                    import urllib.parse
                    parsed = urllib.parse.urlparse(qr_data)
                    params = urllib.parse.parse_qs(parsed.query)
                    qr_unique_id = params.get("code", [None])[0]
                else:
                    qr_unique_id = qr_data[:32] if len(qr_data) > 32 else qr_data
            
            logger.info(f"[GENERATE_QR] User {user_id} - QR unique ID extracted: {qr_unique_id[:20] if qr_unique_id else None}...")
            
            # Update the existing session with QR data
            if user_id in user_qr_sessions and website_index in user_qr_sessions[user_id]:
                user_qr_sessions[user_id][website_index].update({
                    "qr_data": qr_data,
                    "qr_token": qr_token or qr_unique_id,
                    "qr_unique_id": qr_unique_id,
                    "session_id": session_id,
                })
            
            # Create QR code image
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
    """Check login status for a website using the user's PERSISTENT stored session"""
    try:
        base_url = website['base_url']
        code = website['code']
        
        # Get the stored session for this user/website
        session_data = None
        if user_id in user_qr_sessions and website_index in user_qr_sessions[user_id]:
            session_data = user_qr_sessions[user_id][website_index]
        
        # MUST use the stored scraper session
        if session_data and session_data.get("scraper"):
            scraper = session_data["scraper"]
            headers = session_data.get("headers") or get_headers_for_website(website)
            logger.info(f"[CHECK_STATUS] Using PERSISTENT session for user {user_id}, website {website_index}")
        else:
            logger.error(f"[CHECK_STATUS] NO stored session for user {user_id}, website {website_index}!")
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

# ==================== DATABASE FUNCTIONS ====================

async def get_or_create_user_pc(mobile_number: str, username: str = None, first_name: str = None, last_name: str = None):
    """Get existing PC user or create new one by mobile number"""
    try:
        # Check if user exists by mobile number
        result = supabase.table('users').select('*').eq('mobile_number', mobile_number).eq('user_type', 'pc').execute()
        
        if result.data and len(result.data) > 0:
            return result.data[0]
        
        # Create new PC user
        new_user = {
            'mobile_number': mobile_number,
            'user_type': 'pc',
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'status': 'pending',
            'telegram_user_id': None  # PC users don't have Telegram ID
        }
        
        result = supabase.table('users').insert(new_user).execute()
        
        if result.data and len(result.data) > 0:
            user = result.data[0]
            
            # Notify admin about new PC user registration
            try:
                notification = {
                    'notification_type': 'new_pc_user',
                    'user_id': user['id'],
                    'telegram_user_id': None,
                    'mobile_number': mobile_number,
                    'message': f"New PC user registration: {mobile_number}",
                    'is_processed': False
                }
                supabase.table('admin_notifications').insert(notification).execute()
                logger.info(f"Admin notification created for new PC user: {mobile_number}")
            except Exception as e:
                logger.error(f"Error creating admin notification: {e}")
            
            return user
        
        return None
    except Exception as e:
        logger.error(f"Error in get_or_create_user_pc: {e}")
        return None

async def get_user_by_mobile_number(mobile_number: str):
    """Get PC user by mobile number"""
    try:
        result = supabase.table('users').select('*').eq('mobile_number', mobile_number).eq('user_type', 'pc').execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Error in get_user_by_mobile_number: {e}")
        return None

async def update_user_status_pc(mobile_number: str, status: str, admin_id: int = None):
    """Update PC user approval status"""
    try:
        update_data = {'status': status}
        
        if status == 'approved':
            update_data['approved_at'] = datetime.now(pytz.UTC).isoformat()
            update_data['approved_by'] = admin_id
        elif status == 'rejected':
            update_data['rejected_at'] = datetime.now(pytz.UTC).isoformat()
            update_data['rejected_by'] = admin_id
        
        result = supabase.table('users').update(update_data).eq('mobile_number', mobile_number).eq('user_type', 'pc').execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Error in update_user_status_pc: {e}")
        return None

async def add_phone_number_pc(user_id: int, mobile_number: str, phone_number: str):
    """Add a new phone number for PC user"""
    try:
        today = get_bd_date()
        
        new_phone = {
            'user_id': user_id,
            'telegram_user_id': None,  # PC users don't have Telegram ID
            'mobile_number': mobile_number,  # PC user's mobile number
            'phone_number': phone_number,  # The phone number to scan
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
        logger.error(f"Error in add_phone_number_pc: {e}")
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

async def mark_number_completed_pc(phone_number_id: int, user_id: int, mobile_number: str, phone_number: str):
    """Mark phone number as completed for PC user"""
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
            'telegram_user_id': None,  # PC users don't have Telegram ID
            'mobile_number': mobile_number,  # PC user's mobile number
            'phone_number': phone_number,
            'earnings': EARNINGS_PER_NUMBER,
            'reset_date': today.isoformat()
        }
        
        result = supabase.table('completed_numbers').insert(completed).execute()
        
        # Update user's total earnings
        user = await get_user_by_mobile_number(mobile_number)
        if user:
            new_earnings = float(user.get('total_earnings', 0)) + EARNINGS_PER_NUMBER
            supabase.table('users').update({
                'total_earnings': new_earnings
            }).eq('mobile_number', mobile_number).eq('user_type', 'pc').execute()
        
        # Mark earnings as added
        supabase.table('phone_numbers').update({
            'earnings_added': True
        }).eq('id', phone_number_id).execute()
        
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Error in mark_number_completed_pc: {e}")
        return None

async def get_user_stats_pc(mobile_number: str):
    """Get PC user statistics for today"""
    try:
        today = get_bd_date()
        
        # Get user
        user = await get_user_by_mobile_number(mobile_number)
        if not user:
            return None
        
        # Get today's numbers added
        numbers_added = supabase.table('phone_numbers').select('id', count='exact').eq('mobile_number', mobile_number).eq('reset_date', today.isoformat()).execute()
        
        # Get today's completed numbers
        numbers_completed = supabase.table('completed_numbers').select('id', count='exact').eq('mobile_number', mobile_number).eq('reset_date', today.isoformat()).execute()
        
        # Get today's earnings
        earnings_result = supabase.table('completed_numbers').select('earnings').eq('mobile_number', mobile_number).eq('reset_date', today.isoformat()).execute()
        today_earnings = sum(float(e.get('earnings', 0)) for e in earnings_result.data) if earnings_result.data else 0
        
        return {
            'numbers_added': numbers_added.count if numbers_added else 0,
            'numbers_completed': numbers_completed.count if numbers_completed else 0,
            'today_earnings': today_earnings,
            'total_earnings': float(user.get('total_earnings', 0))
        }
    except Exception as e:
        logger.error(f"Error in get_user_stats_pc: {e}")
        return None

async def get_pending_pc_users_list():
    """Get list of pending PC users"""
    try:
        result = supabase.table('users').select('*').eq('status', 'pending').eq('user_type', 'pc').order('created_at', desc=True).execute()
        return result.data if result.data else []
    except Exception as e:
        logger.error(f"Error in get_pending_pc_users_list: {e}")
        return []

