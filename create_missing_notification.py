"""
Create missing notification for existing PC user
"""
import asyncio
from backend_core import supabase

async def create_missing_notifications():
    """Create notifications for existing pending PC users"""
    print("Creating missing notifications for pending PC users...")
    
    # Get all pending PC users
    users = supabase.table('users').select('*').eq('status', 'pending').eq('user_type', 'pc').execute()
    
    if not users.data:
        print("No pending PC users found")
        return
    
    print(f"Found {len(users.data)} pending PC users")
    
    for user in users.data:
        mobile = user.get('mobile_number')
        user_id = user.get('id')
        
        # Check if notification already exists
        existing = supabase.table('admin_notifications').select('*').eq('mobile_number', mobile).eq('notification_type', 'new_pc_user').execute()
        
        if existing.data and len(existing.data) > 0:
            print(f"  ⏭️  Notification already exists for {mobile}")
            continue
        
        # Create notification
        try:
            notification = {
                'notification_type': 'new_pc_user',
                'user_id': user_id,
                'telegram_user_id': None,
                'mobile_number': mobile,
                'message': f"New PC user registration: {mobile}",
                'is_processed': False
            }
            result = supabase.table('admin_notifications').insert(notification).execute()
            print(f"  ✅ Created notification for {mobile}")
        except Exception as e:
            print(f"  ❌ Error creating notification for {mobile}: {e}")
    
    print("\nDone! Admin will receive notifications when bot checks (every 2 minutes or when /start is used)")

if __name__ == "__main__":
    asyncio.run(create_missing_notifications())

