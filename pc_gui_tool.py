"""
PC GUI Tool for QR Code Generation
Desktop application for PC users to generate QR codes
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from PIL import Image, ImageTk
import asyncio
import threading
import time
from datetime import datetime
import io
import sys

# Import shared backend
from backend_core import (
    WEBSITES, is_within_working_hours, get_working_hours_message,
    normalize_phone_number, format_phone_number, get_site_name,
    generate_qr_code, check_login_status,
    get_or_create_user_pc,
    add_phone_number_pc, add_website_completion, mark_number_completed_pc,
    get_user_stats_pc, EARNINGS_PER_NUMBER
)

class PCQRTool:
    def __init__(self, root):
        self.root = root
        self.root.title("QR Code Generator - PC Tool")
        self.root.geometry("1000x750")
        self.root.resizable(True, True)
        self.root.configure(bg='#f0f0f0')
        
        # User state
        self.current_user = None
        self.current_mobile = None
        self.current_phone_number = None
        self.current_phone_number_id = None
        self.current_index = 0
        self.completed_websites = []
        self.session_user_id = None
        self.is_polling = False
        self.polling_thread = None
        
        # Create UI
        self.create_ui()
        
        # Check if user is logged in
        self.check_login_state()
    
    def create_ui(self):
        """Create the main UI with better organization"""
        # Configure root
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # ========== LEFT SIDEBAR ==========
        sidebar = ttk.Frame(self.root, width=280, padding="15")
        sidebar.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        sidebar.grid_propagate(False)
        self.root.columnconfigure(0, weight=0)
        
        # Title in sidebar
        title_label = ttk.Label(sidebar, text="QR Code\nGenerator", font=("Arial", 18, "bold"), justify=tk.CENTER)
        title_label.grid(row=0, column=0, pady=(0, 20))
        
        # User Information Section
        user_section = ttk.LabelFrame(sidebar, text="👤 User Account", padding="12")
        user_section.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        user_section.columnconfigure(0, weight=1)
        
        ttk.Label(user_section, text="Mobile Number:", font=("Arial", 9)).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        self.mobile_entry = ttk.Entry(user_section, width=25, font=("Arial", 10))
        self.mobile_entry.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        
        self.login_btn = ttk.Button(user_section, text="Login / Register", command=self.handle_login, width=25)
        self.login_btn.grid(row=2, column=0, pady=(0, 8))
        
        self.status_label = ttk.Label(user_section, text="Status: Not logged in", foreground="gray", font=("Arial", 9), wraplength=240)
        self.status_label.grid(row=3, column=0, sticky=tk.W, pady=(0, 8))
        
        self.stats_btn = ttk.Button(user_section, text="📊 View Statistics", command=self.show_stats, state=tk.DISABLED, width=25)
        self.stats_btn.grid(row=4, column=0)
        
        # Phone Number Section
        phone_section = ttk.LabelFrame(sidebar, text="📱 Scan Phone Number", padding="12")
        phone_section.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        phone_section.columnconfigure(0, weight=1)
        
        ttk.Label(phone_section, text="Enter Phone Number:", font=("Arial", 9)).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        self.phone_entry = ttk.Entry(phone_section, width=25, font=("Arial", 10))
        self.phone_entry.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 8))
        
        self.submit_btn = ttk.Button(phone_section, text="🚀 Generate QR Codes", command=self.handle_phone_submit, state=tk.DISABLED, width=25)
        self.submit_btn.grid(row=2, column=0)
        
        # Progress Section
        progress_section = ttk.LabelFrame(sidebar, text="📊 Progress", padding="12")
        progress_section.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        progress_section.columnconfigure(0, weight=1)
        
        self.progress_label = ttk.Label(progress_section, text="Progress: ⬜ ⬜ ⬜ ⬜\n(0/4)", font=("Arial", 11, "bold"), justify=tk.CENTER)
        self.progress_label.grid(row=0, column=0, pady=5)
        
        self.queue_label = ttk.Label(
            progress_section,
            text="🖥️ PC tool আলাদা মেশিনে চলে — এখানে কোনো queue নেই।",
            foreground="gray",
            font=("Arial", 8),
            wraplength=240,
            justify=tk.CENTER
        )
        self.queue_label.grid(row=1, column=0, pady=5)
        
        # Regenerate button in sidebar
        self.regenerate_btn = ttk.Button(sidebar, text="🔄 Regenerate QR", command=self.regenerate_qr, state=tk.DISABLED, width=25)
        self.regenerate_btn.grid(row=4, column=0, pady=(10, 0))
        
        # ========== MAIN AREA ==========
        main_area = ttk.Frame(self.root, padding="15")
        main_area.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_area.columnconfigure(0, weight=1)
        main_area.rowconfigure(1, weight=1)
        
        # QR Code Display Section
        qr_section = ttk.LabelFrame(main_area, text="📱 QR Code - Scan with WhatsApp", padding="20")
        qr_section.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        qr_section.columnconfigure(0, weight=1)
        qr_section.rowconfigure(0, weight=1)
        main_area.rowconfigure(0, weight=1)
        
        # QR code image label (centered, larger)
        self.qr_label = ttk.Label(qr_section, text="No QR code generated yet.\n\nPlease login and enter a phone number to start.", 
                                  anchor=tk.CENTER, font=("Arial", 11), foreground="gray", justify=tk.CENTER)
        self.qr_label.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=20)
        
        # Status/Log Section
        log_section = ttk.LabelFrame(main_area, text="📝 Activity Log", padding="10")
        log_section.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_section.columnconfigure(0, weight=1)
        log_section.rowconfigure(0, weight=1)
        main_area.rowconfigure(1, weight=1)
        
        self.status_text = scrolledtext.ScrolledText(log_section, height=8, wrap=tk.WORD, state=tk.DISABLED, 
                                                      font=("Consolas", 9), bg='#fafafa')
        self.status_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    
    def check_login_state(self):
        """Check if user should be auto-logged in (from previous session)"""
        # Could implement session persistence here
        pass
    
    def log_status(self, message):
        """Log status message"""
        self.status_text.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)
    
    def get_session_user_id(self):
        """Return stable session user ID for backend isolation."""
        if not self.current_mobile:
            return None
        if self.session_user_id is None:
            # Offset with large constant to avoid clashing with Telegram IDs
            base = abs(hash(self.current_mobile)) % (10**9)
            self.session_user_id = base + 5_000_000_000
        return self.session_user_id
    
    async def handle_login_async(self, mobile_number):
        """Handle login/registration asynchronously"""
        try:
            # Normalize mobile number
            normalized = normalize_phone_number(mobile_number)
            if not normalized:
                return False, "Invalid mobile number format"
            
            # Get or create user
            user = await get_or_create_user_pc(normalized)
            if not user:
                return False, "Database error. Please try again."
            
            self.current_user = user
            self.current_mobile = normalized
            self.session_user_id = None
            
            status = user.get('status', 'pending')
            
            if status == 'pending':
                return False, "Your account is pending approval. Admin will review your request."
            elif status == 'rejected':
                return False, "Your account has been rejected. Please contact admin."
            elif status == 'approved':
                return True, "Login successful!"
            else:
                return False, f"Unknown status: {status}"
        
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def handle_login(self):
        """Handle login button click"""
        mobile = self.mobile_entry.get().strip()
        if not mobile:
            messagebox.showerror("Error", "Please enter your mobile number")
            return
        
        self.login_btn.config(state=tk.DISABLED, text="Checking...")
        self.log_status("Checking login...")
        
        def login_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            success, message = loop.run_until_complete(self.handle_login_async(mobile))
            loop.close()
            
            self.root.after(0, lambda: self.login_callback(success, message))
        
        threading.Thread(target=login_thread, daemon=True).start()
    
    def login_callback(self, success, message):
        """Callback after login attempt"""
        self.login_btn.config(state=tk.NORMAL, text="Login / Register")
        
        if success:
            self.status_label.config(text=f"Status: ✅ Logged in as {format_phone_number(self.current_mobile)}", foreground="green")
            self.submit_btn.config(state=tk.NORMAL)
            self.stats_btn.config(state=tk.NORMAL)
            self.mobile_entry.config(state=tk.DISABLED)
            self.log_status(message)
            messagebox.showinfo("Success", message)
        else:
            self.status_label.config(text=f"Status: ❌ {message}", foreground="red")
            self.log_status(message)
            messagebox.showerror("Error", message)
    
    async def handle_phone_submit_async(self, phone_number):
        """Handle phone number submission asynchronously"""
        try:
            # Check working hours
            if not is_within_working_hours():
                return False, get_working_hours_message()
            
            # Normalize phone number
            normalized = normalize_phone_number(phone_number)
            if not normalized:
                return False, "Invalid phone number format"
            
            # Reset state
            self.completed_websites = []
            self.current_index = 0
            self.current_phone_number = normalized
            
            # Add phone number to database
            phone_record = await add_phone_number_pc(
                self.current_user['id'],
                self.current_mobile,
                normalized
            )
            
            if not phone_record:
                return False, "Database error. Please try again."
            
            self.current_phone_number_id = phone_record['id']
            
            # Start generating QR for first website
            return await self.generate_next_qr()
        
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def handle_phone_submit(self):
        """Handle phone number submit button click"""
        phone = self.phone_entry.get().strip()
        if not phone:
            messagebox.showerror("Error", "Please enter a phone number")
            return
        
        self.submit_btn.config(state=tk.DISABLED, text="Processing...")
        self.log_status(f"Processing phone number: {format_phone_number(phone)}")
        
        def submit_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            success, message = loop.run_until_complete(self.handle_phone_submit_async(phone))
            loop.close()
            
            self.root.after(0, lambda: self.submit_callback(success, message))
        
        threading.Thread(target=submit_thread, daemon=True).start()
    
    def submit_callback(self, success, message):
        """Callback after phone submit"""
        self.submit_btn.config(state=tk.NORMAL, text="Generate QR Codes")
        
        if not success:
            self.log_status(f"Error: {message}")
            messagebox.showerror("Error", message)
    
    async def generate_next_qr(self):
        """Generate QR code for next website"""
        try:
            # Find next uncompleted website
            next_index = None
            for i in range(len(WEBSITES)):
                if i not in self.completed_websites:
                    next_index = i
                    break
            
            if next_index is None:
                # All websites completed
                return True, "All websites completed!"
            
            self.current_index = next_index
            website = WEBSITES[next_index]
            site_name = get_site_name(next_index)
            
            user_id = self.get_session_user_id()
            if not user_id:
                return False, "Please log in again to continue."
            
            # Generate QR code
            self.root.after(0, lambda: self.log_status(f"Generating QR code for {site_name}..."))
            qr_image, error = generate_qr_code(website, user_id, next_index)
            
            if error:
                return False, error
            
            # Display QR code
            self.root.after(0, lambda: self.display_qr_code(qr_image, site_name))
            self.root.after(0, lambda: self.log_status(f"QR code generated for {site_name}. Please scan with WhatsApp."))
            
            # Start polling
            self.is_polling = True
            self.start_polling(user_id, next_index, website)
            
            return True, "QR code generated"
        
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def display_qr_code(self, qr_image_bytes, site_name):
        """Display QR code image"""
        try:
            # Convert bytes to PIL Image
            qr_image_bytes.seek(0)
            img = Image.open(qr_image_bytes)
            
            # Resize for display (max 400x400)
            max_size = 400
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(img)
            
            # Update label
            self.qr_label.config(image=photo, text="")
            self.qr_label.image = photo  # Keep a reference
            
            # Update progress
            self.update_progress()
            
            # Enable regenerate button
            self.regenerate_btn.config(state=tk.NORMAL)
        
        except Exception as e:
            self.log_status(f"Error displaying QR code: {str(e)}")
    
    def update_progress(self):
        """Update progress display"""
        completed = len(self.completed_websites)
        total = len(WEBSITES)
        
        progress_icons = []
        for i in range(total):
            if i in self.completed_websites:
                progress_icons.append("✅")
            else:
                progress_icons.append("⬜")
        
        progress_text = f"Progress: {' '.join(progress_icons)} ({completed}/{total})"
        self.progress_label.config(text=progress_text)
    
    def start_polling(self, user_id, website_index, website):
        """Start polling for login status"""
        if self.polling_thread and self.polling_thread.is_alive():
            return
        
        def poll_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.poll_login_status(user_id, website_index, website))
            loop.close()
        
        self.polling_thread = threading.Thread(target=poll_thread, daemon=True)
        self.polling_thread.start()
    
    async def poll_login_status(self, user_id, website_index, website):
        """Poll login status until success or timeout"""
        max_polls = 120  # 2 minutes max
        poll_count = 0
        
        while self.is_polling and poll_count < max_polls:
            await asyncio.sleep(2)  # Poll every 2 seconds
            poll_count += 1
            
            status = check_login_status(website, user_id, website_index)
            
            if status.get("status") == "success":
                # Success!
                phone = status.get("phone")
                name = status.get("name")
                
                self.root.after(0, lambda: self.handle_scan_success(website_index, website, phone, name))
                break
            
            elif status.get("status") == "waiting":
                # Still waiting
                if poll_count % 10 == 0:  # Update every 20 seconds
                    self.root.after(0, lambda: self.log_status(f"Waiting for scan... ({poll_count * 2}s)"))
            
            elif status.get("status") == "error":
                self.root.after(0, lambda: self.log_status(f"Error checking status: {status.get('message')}"))
                break
        
        if poll_count >= max_polls:
            self.root.after(0, lambda: self.handle_scan_timeout(website_index))
    
    def handle_scan_success(self, website_index, website, phone, name):
        """Handle successful scan"""
        self.is_polling = False
        
        site_name = get_site_name(website_index)
        self.log_status(f"✅ {site_name} - Scanned successfully!")
        if phone:
            self.log_status(f"Phone detected: {phone}")
        if name:
            self.log_status(f"Name detected: {name}")
        
        # Mark as completed
        self.completed_websites.append(website_index)
        self.update_progress()
        
        # Add to database
        def add_completion():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.add_completion_async(website_index, website, phone, name))
            loop.close()
        
        threading.Thread(target=add_completion, daemon=True).start()
        
        # Check if all completed
        if len(self.completed_websites) >= len(WEBSITES):
            self.handle_all_completed()
        else:
            # Generate next QR
            def generate_next():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.generate_next_qr())
                loop.close()
            
            threading.Thread(target=generate_next, daemon=True).start()
    
    async def add_completion_async(self, website_index, website, phone, name):
        """Add website completion to database"""
        try:
            await add_website_completion(
                self.current_phone_number_id,
                website_index,
                website['name'],
                phone,
                name
            )
        except Exception as e:
            self.root.after(0, lambda: self.log_status(f"Error adding completion: {str(e)}"))
    
    def handle_scan_timeout(self, website_index):
        """Handle scan timeout"""
        self.is_polling = False
        site_name = get_site_name(website_index)
        self.log_status(f"⏰ QR code expired for {site_name}. You can regenerate.")
        
    def handle_all_completed(self):
        """Handle all websites completed"""
        self.log_status("🎉 All websites completed!")
        
        # Mark number as completed
        def mark_completed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.mark_completed_async())
            loop.close()
        
        threading.Thread(target=mark_completed, daemon=True).start()
        
        messagebox.showinfo("Success", "All websites completed! Earnings added to your account.")
        
        # Reset for new number
        self.completed_websites = []
        self.current_index = 0
        self.current_phone_number = None
        self.current_phone_number_id = None
        self.phone_entry.delete(0, tk.END)
        self.qr_label.config(image="", text="No QR code generated yet")
        self.regenerate_btn.config(state=tk.DISABLED)
    
    async def mark_completed_async(self):
        """Mark phone number as completed"""
        try:
            await mark_number_completed_pc(
                self.current_phone_number_id,
                self.current_user['id'],
                self.current_mobile,
                self.current_phone_number
            )
        except Exception as e:
            self.root.after(0, lambda: self.log_status(f"Error marking completed: {str(e)}"))
    
    def regenerate_qr(self):
        """Regenerate current QR code"""
        if self.current_index is None:
            return
        
        self.is_polling = False
        self.regenerate_btn.config(state=tk.DISABLED)
        self.log_status("Regenerating QR code...")
        
        def regenerate():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.generate_next_qr())
            loop.close()
        
        threading.Thread(target=regenerate, daemon=True).start()
    
    def show_stats(self):
        """Show user statistics"""
        def get_stats():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            stats = loop.run_until_complete(get_user_stats_pc(self.current_mobile))
            loop.close()
            
            self.root.after(0, lambda: self.display_stats(stats))
        
        threading.Thread(target=get_stats, daemon=True).start()
    
    def display_stats(self, stats):
        """Display statistics in a message box"""
        if not stats:
            messagebox.showerror("Error", "Could not retrieve statistics")
            return
        
        stats_text = (
            f"📊 Your Statistics\n\n"
            f"📱 Numbers Added Today: {stats['numbers_added']}\n"
            f"✅ Numbers Completed Today: {stats['numbers_completed']}\n"
            f"💰 Today's Earnings: {stats['today_earnings']:.2f} Tk\n"
            f"💵 Total Earnings: {stats['total_earnings']:.2f} Tk"
        )
        
        messagebox.showinfo("Statistics", stats_text)

def main():
    root = tk.Tk()
    app = PCQRTool(root)
    root.mainloop()

if __name__ == "__main__":
    main()

