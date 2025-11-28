# PC GUI Tool - Installation and Usage Guide

## 📋 Overview

This PC GUI tool allows PC users to generate QR codes for scanning, just like the Telegram bot. The tool uses the same backend system and database.

## 🗄️ Database Setup

**IMPORTANT:** Before using the PC tool, you must update your Supabase database.

1. Go to Supabase Dashboard > SQL Editor
2. Open the file `database_update_pc_users.sql`
3. Copy and paste the entire SQL script
4. Click "Run"

This will add support for PC users in your database.

## 📦 Installation

### Requirements

The PC tool requires the same dependencies as the Telegram bot:

```bash
pip install -r requirements.txt
```

Key dependencies:
- `tkinter` (usually comes with Python)
- `Pillow` (for image display)
- `supabase` (for database)
- `curl_cffi` or `cloudscraper` (for API requests)
- `qrcode` (for QR code generation)

## 🚀 Running the PC Tool

### Easy Method (Recommended):
1. Make sure the database is updated (see above)
2. **Double-click `run.py`** (or `run.bat` on Windows)
3. The tool will start automatically!

### Alternative Method:
1. Make sure the database is updated (see above)
2. Open terminal/command prompt in the project folder
3. Run:
```bash
python run.py
```

Or directly:
```bash
python pc_gui_tool.py
```

## 👤 User Flow

### 1. Registration/Login

- Enter your mobile number in the "Your Mobile Number" field
- Click "Login / Register"
- If you're a new user, your account will be created with "pending" status
- Wait for admin approval via Telegram bot

### 2. After Approval

- Once approved by admin, you can log in with your mobile number
- The status will show "✅ Logged in"

### 3. Generating QR Codes

- Enter a phone number to scan in the "Phone Number to Scan" field
- Click "Generate QR Codes"
- The tool will generate QR codes for all 4 websites sequentially
- Scan each QR code with WhatsApp
- Progress is tracked automatically

### 4. Viewing Statistics

- Click "📊 My Stats" to see your earnings and completed numbers

## 🔧 Features

- ✅ Mobile number-based authentication
- ✅ QR code generation for 4 websites
- ✅ Automatic progress tracking
- ✅ Queue system (same as Telegram bot)
- ✅ Working hours validation (10:30 AM - 3:00 PM)
- ✅ Statistics display
- ✅ Error handling

## 🔐 Admin Approval

Admins can approve PC users via the Telegram bot:

1. Admin clicks "⏳ Pending Users" in Telegram bot
2. PC users will show with 💻 icon and mobile number
3. Admin can approve/reject PC users
4. PC users will see updated status when they try to log in again

## ⚠️ Important Notes

- PC users are identified by mobile number (not Telegram ID)
- PC users cannot receive Telegram notifications
- Same queue system applies - PC users and Telegram users share the same queue
- Working hours: 10:30 AM - 3:00 PM (Bangladesh time)

## 🐛 Troubleshooting

### "Invalid mobile number format"
- Make sure you enter a valid phone number
- Supported formats: +8801712345678, 01712345678, +1234567890, etc.

### "Account pending approval"
- Your account is waiting for admin approval
- Contact admin to get approved

### "Working hours ended"
- The tool only works between 10:30 AM - 3:00 PM (Bangladesh time)
- Try again during working hours

### QR code not generating
- Check your internet connection
- The website might be busy (queue system will handle this)
- Try regenerating the QR code

## 📝 Files

- `pc_gui_tool.py` - Main GUI application
- `backend_core.py` - Shared backend functions
- `database_update_pc_users.sql` - Database migration script
- `telegram_qr_bot.py` - Telegram bot (updated to support PC users)

## 🔄 Updates

The PC tool uses the same backend as the Telegram bot, so any improvements to the backend will automatically benefit both tools.

