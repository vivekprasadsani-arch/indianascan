"""
Test script to check PC user notification system
Run this to verify notifications are being created and can be retrieved
"""
import asyncio
from supabase import create_client, Client
from backend_core import get_or_create_user_pc, get_pending_pc_users_list

# Supabase Configuration
SUPABASE_URL = "https://sgnnqvfoajqsfdyulolm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNnbm5xdmZvYWpxc2ZkeXVsb2xtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQxNzE1MjcsImV4cCI6MjA3OTc0NzUyN30.dFniV0odaT-7bjs5iQVFQ-N23oqTGMAgQKjswhaHSP4"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

async def test_notification_system():
    """Test the PC user notification system"""
    print("=" * 50)
    print("Testing PC User Notification System")
    print("=" * 50)
    
    # Test 1: Check existing notifications
    print("\n1. Checking existing notifications...")
    try:
        result = supabase.table('admin_notifications').select('*').eq('notification_type', 'new_pc_user').eq('is_processed', False).order('created_at', desc=True).execute()
        
        if result.data and len(result.data) > 0:
            print(f"   ✅ Found {len(result.data)} unprocessed notifications:")
            for notif in result.data:
                print(f"      - Mobile: {notif.get('mobile_number')}, Created: {notif.get('created_at')}")
        else:
            print("   ⚠️  No unprocessed notifications found")
    except Exception as e:
        print(f"   ❌ Error checking notifications: {e}")
    
    # Test 2: Check pending PC users
    print("\n2. Checking pending PC users...")
    try:
        pending_users = await get_pending_pc_users_list()
        if pending_users:
            print(f"   ✅ Found {len(pending_users)} pending PC users:")
            for user in pending_users:
                print(f"      - Mobile: {user.get('mobile_number')}, Status: {user.get('status')}")
        else:
            print("   ⚠️  No pending PC users found")
    except Exception as e:
        print(f"   ❌ Error checking pending users: {e}")
    
    # Test 3: Create a test notification (optional)
    print("\n3. Testing notification creation...")
    test_mobile = "+8801712345678"  # Test number
    try:
        # Check if test user exists
        existing = supabase.table('users').select('*').eq('mobile_number', test_mobile).eq('user_type', 'pc').execute()
        
        if existing.data and len(existing.data) > 0:
            print(f"   ℹ️  Test user already exists, skipping creation")
        else:
            print(f"   Creating test user: {test_mobile}")
            user = await get_or_create_user_pc(test_mobile, "Test", "User")
            if user:
                print(f"   ✅ Test user created successfully!")
                print(f"      User ID: {user.get('id')}, Status: {user.get('status')}")
                
                # Check if notification was created
                notif_result = supabase.table('admin_notifications').select('*').eq('mobile_number', test_mobile).eq('is_processed', False).order('created_at', desc=True).limit(1).execute()
                if notif_result.data:
                    print(f"   ✅ Notification created successfully!")
                else:
                    print(f"   ⚠️  Notification not found (may have been processed)")
            else:
                print(f"   ❌ Failed to create test user")
    except Exception as e:
        print(f"   ❌ Error in test: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 4: Check all notifications (processed and unprocessed)
    print("\n4. Checking all PC user notifications...")
    try:
        all_notifs = supabase.table('admin_notifications').select('*').eq('notification_type', 'new_pc_user').order('created_at', desc=True).limit(10).execute()
        if all_notifs.data:
            print(f"   Found {len(all_notifs.data)} recent notifications:")
            for notif in all_notifs.data:
                status = "✅ Processed" if notif.get('is_processed') else "⏳ Pending"
                print(f"      - Mobile: {notif.get('mobile_number')}, Status: {status}, Created: {notif.get('created_at')}")
        else:
            print("   ⚠️  No notifications found in database")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 50)
    print("Test Complete!")
    print("=" * 50)
    print("\nIf notifications are being created but not sent to admin:")
    print("1. Make sure Telegram bot is running")
    print("2. Check bot logs for errors")
    print("3. Admin should use /start or click 'Pending Users' button")
    print("4. Bot will check every 2 minutes automatically")

if __name__ == "__main__":
    asyncio.run(test_notification_system())

