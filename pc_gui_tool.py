"""
PC GUI Tool for QR Code Generation
Desktop application for PC users to generate QR codes
Modern UI with WhatsApp theme
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
import base64

# Import shared backend
from backend_core import (
    WEBSITES, is_within_working_hours, get_working_hours_message,
    normalize_phone_number, format_phone_number, get_site_name,
    generate_qr_code, check_login_status,
    get_or_create_user_pc,
    add_phone_number_pc, add_website_completion, mark_number_completed_pc,
    get_user_stats_pc, EARNINGS_PER_NUMBER
)

# WhatsApp logo as base64 (green circle with phone icon)
WHATSAPP_ICON_BASE64 = """
iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAACXBIWXMAAAsTAAALEwEAmpwYAAAD
iklEQVR4nO2WS2hcVRjHf+fOTGYmmUzeo0nTtPWBVhS7EBQXIrgRXYgg4kJBcOFCcCHiQnDhQnDh
QlyIICKIiCC4EJFCFxYRoS4sKFIoUltrtLVNm6TNZDKZx517j4uZSSaTyUOn0o0/OHDv/c73/77/
9zi3cJObXM8SoAuYBQTwDrAMzAOLwAXgPLAIXAHOAOeBAnAZuAb8BswBl4ALwCJwGbgKLAFLwFVg
EbgCXAQuAYvAEnAN+A1YBK4A1+rXKwALwEWgCFwCrgLL1FkALoO9BrwB/AhsAt4GngQOAvcD9wH7
gPuBfcA9wL3A3cDdQC/QB3QDPUAPsAnYBGwBeoFeoA/oBbqBLqATyAPtwCZgM9AN5IAOIJ/+zwFt
QBbIpvdzQBuQAXJADsimuawNiOvPdFt7bwLIAJn0WQ7IpnPp/zYgk9bZZrUB7ek6swpsCcgAmbTO
ZlKdbUBb+rwN8GhLyG6jLaNNYzQjjBuG85ZxTmhcVjHWBM4Jws8KwbkmpCgFZ4C5NMlcGrMA/J7+
ngcKwCKwmM5fSHMXgCvpXI2ZNE8BuExzLQAl4GpjnOXBtpq00w3gu5TwDPBbmvy3dP53miMdfxPw
M/AT8CPwI/ATMJeOC2n8BWAZ+C2Nvwz8CpwDfknPfgKuNqx7FVhO1znXuKYL+AXLy/8zZhXwXgvw
C/CuMAaFkADSq4SQMEawhOYi4WEBDrq0Y3gS69KOOvSJzJ0Ep1F8JGKOhQr3xwn3uI6bBnFCOBQm
7HMDdifK+4BXcSgKz+DIu1g6dF0b4Dn8CHznEn8q+BK4G8P3kj6PMGLxaJAw1pYwQDnkXhwG8XkA
+E7YfSrCj+p8JuxelEGFx1A6NawGbIqT/ADcKux2YTiEMoJPjPCQJBxJFI/7Lr3VhC5VBnA5DmNY
wvCiCP0iPKXQhyMThC+Jz2EsEwgnJOEBPAZJ+ALFQZRBlE9J+AKYTCa4L1H6SJQT6ZqDKIMqDKF8
gvI+yieofCQqHyh8hPKRyidY+lBGUD7Esp+EPoVeQekXuJNq0EdiX1f4VuFjYQzlQyyDWA4gdKDc
h/Cpwq2Ofj+Ou7F0ovSJpdfRb8eyH0UF0BJ7g7/TlZBTmLuwu1H6UPpJ6HQ09+HQC9yC5TYs/cAI
yr0onQp9otwH9KT1bUXoAQ5geQB4ELgD5XYStmHZguU2EoZR7sMyjOVBhD4suxK1/cA2Em4HbgcG
FAbSehhhBKWPhAEs3Q7tHm4XMADcAdwF3AnchXIHll4sd2LZjWU3lruBISy7sfSlde6ij/8AvuCf
lF/5H9YfRvgYJVTBj5UAAAAASUVORK5CYII=
"""

# Modern color scheme (WhatsApp inspired)
COLORS = {
    'bg_dark': '#0a1014',           # Very dark background
    'bg_main': '#111b21',           # Main background (WhatsApp dark)
    'bg_sidebar': '#1f2c34',        # Sidebar background
    'bg_card': '#202c33',           # Card background
    'bg_input': '#2a3942',          # Input background
    'accent': '#00a884',            # WhatsApp green
    'accent_hover': '#06cf9c',      # Lighter green for hover
    'accent_dark': '#008069',       # Darker green
    'text_primary': '#e9edef',      # Primary text (light)
    'text_secondary': '#8696a0',    # Secondary text (gray)
    'text_muted': '#667781',        # Muted text
    'success': '#00a884',           # Success green
    'error': '#f15c6d',             # Error red
    'warning': '#f7c94a',           # Warning yellow
    'border': '#2a3942',            # Border color
    'highlight': '#005c4b',         # Highlight/selection
}


class ModernButton(tk.Canvas):
    """Custom modern rounded button"""
    def __init__(self, parent, text, command=None, width=200, height=40, 
                 bg=COLORS['accent'], fg='white', hover_bg=COLORS['accent_hover'],
                 disabled_bg=COLORS['bg_input'], font_size=11, **kwargs):
        super().__init__(parent, width=width, height=height, 
                        bg=parent.cget('bg') if hasattr(parent, 'cget') else COLORS['bg_main'],
                        highlightthickness=0, **kwargs)
        
        self.command = command
        self.text = text
        self.width = width
        self.height = height
        self.bg = bg
        self.fg = fg
        self.hover_bg = hover_bg
        self.disabled_bg = disabled_bg
        self.font_size = font_size
        self._state = 'normal'
        self._current_bg = bg
        
        self.draw_button()
        
        self.bind('<Enter>', self.on_enter)
        self.bind('<Leave>', self.on_leave)
        self.bind('<Button-1>', self.on_click)
    
    def draw_button(self):
        self.delete('all')
        radius = 8
        
        # Draw rounded rectangle
        self.create_rounded_rect(2, 2, self.width-2, self.height-2, radius, 
                                fill=self._current_bg, outline='')
        
        # Draw text
        self.create_text(self.width//2, self.height//2, text=self.text,
                        fill=self.fg if self._state == 'normal' else COLORS['text_muted'],
                        font=('Segoe UI', self.font_size, 'bold'))
    
    def create_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        points = [
            x1+radius, y1, x2-radius, y1,
            x2, y1, x2, y1+radius,
            x2, y2-radius, x2, y2,
            x2-radius, y2, x1+radius, y2,
            x1, y2, x1, y2-radius,
            x1, y1+radius, x1, y1
        ]
        return self.create_polygon(points, smooth=True, **kwargs)
    
    def on_enter(self, event):
        if self._state == 'normal':
            self._current_bg = self.hover_bg
            self.draw_button()
            self.config(cursor='hand2')
    
    def on_leave(self, event):
        if self._state == 'normal':
            self._current_bg = self.bg
            self.draw_button()
            self.config(cursor='')
    
    def on_click(self, event):
        if self._state == 'normal' and self.command:
            self.command()
    
    def configure(self, **kwargs):
        if 'state' in kwargs:
            self._state = kwargs.pop('state')
            self._current_bg = self.bg if self._state == 'normal' else self.disabled_bg
            self.draw_button()
        if 'text' in kwargs:
            self.text = kwargs.pop('text')
            self.draw_button()
        super().configure(**kwargs)
    
    def config(self, **kwargs):
        self.configure(**kwargs)


class ModernEntry(tk.Frame):
    """Custom modern entry with rounded border"""
    def __init__(self, parent, placeholder="", width=25, **kwargs):
        super().__init__(parent, bg=COLORS['bg_input'], highlightthickness=2,
                        highlightbackground=COLORS['border'], highlightcolor=COLORS['accent'])
        
        self.placeholder = placeholder
        self.placeholder_color = COLORS['text_muted']
        self.text_color = COLORS['text_primary']
        self.has_placeholder = True
        
        self.entry = tk.Entry(self, bg=COLORS['bg_input'], fg=self.placeholder_color,
                             insertbackground=COLORS['text_primary'],
                             font=('Segoe UI', 11), relief='flat', width=width,
                             bd=8)
        self.entry.pack(fill='both', expand=True, padx=2, pady=2)
        
        if placeholder:
            self.entry.insert(0, placeholder)
            self.entry.bind('<FocusIn>', self.on_focus_in)
            self.entry.bind('<FocusOut>', self.on_focus_out)
    
    def on_focus_in(self, event):
        if self.has_placeholder:
            self.entry.delete(0, 'end')
            self.entry.config(fg=self.text_color)
            self.has_placeholder = False
    
    def on_focus_out(self, event):
        if not self.entry.get():
            self.entry.insert(0, self.placeholder)
            self.entry.config(fg=self.placeholder_color)
            self.has_placeholder = True
    
    def get(self):
        if self.has_placeholder:
            return ""
        return self.entry.get()
    
    def delete(self, first, last):
        self.entry.delete(first, last)
        if not self.entry.get():
            self.entry.insert(0, self.placeholder)
            self.entry.config(fg=self.placeholder_color)
            self.has_placeholder = True
    
    def insert(self, index, string):
        if self.has_placeholder:
            self.entry.delete(0, 'end')
            self.has_placeholder = False
            self.entry.config(fg=self.text_color)
        self.entry.insert(index, string)
    
    def configure(self, **kwargs):
        if 'state' in kwargs:
            self.entry.config(state=kwargs['state'])


class PCQRTool:
    def __init__(self, root):
        self.root = root
        self.root.title("WhatsApp QR Scanner")
        self.root.geometry("1100x700")
        self.root.minsize(900, 600)
        self.root.configure(bg=COLORS['bg_main'])
        
        # Set window icon
        self.set_window_icon()
        
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
        self.is_rescan_mode = False
        self.last_completed_phone = None
        self.rescan_nav_frame = None
        
        # Create UI
        self.create_ui()
        
        # Check if user is logged in
        self.check_login_state()
    
    def set_window_icon(self):
        """Set WhatsApp icon as window icon"""
        import os
        try:
            # Try to use .ico file first (works best on Windows)
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'whatsapp.ico')
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
            else:
                # Fallback to base64 PNG
                icon_data = base64.b64decode(WHATSAPP_ICON_BASE64)
                icon_image = Image.open(io.BytesIO(icon_data))
                icon_photo = ImageTk.PhotoImage(icon_image)
                self.root.iconphoto(True, icon_photo)
                self.icon_photo = icon_photo  # Keep reference
        except Exception as e:
            print(f"Could not set icon: {e}")
    
    def create_ui(self):
        """Create the modern UI"""
        # Configure root grid
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # ========== LEFT SIDEBAR ==========
        sidebar = tk.Frame(self.root, bg=COLORS['bg_sidebar'], width=320)
        sidebar.grid(row=0, column=0, sticky='nsew')
        sidebar.grid_propagate(False)
        
        # Sidebar inner padding
        sidebar_inner = tk.Frame(sidebar, bg=COLORS['bg_sidebar'])
        sidebar_inner.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Logo and Title
        logo_frame = tk.Frame(sidebar_inner, bg=COLORS['bg_sidebar'])
        logo_frame.pack(fill='x', pady=(0, 30))
        
        # WhatsApp-style header
        header_text = tk.Label(logo_frame, text="📱 WhatsApp", 
                              font=('Segoe UI', 22, 'bold'),
                              bg=COLORS['bg_sidebar'], fg=COLORS['accent'])
        header_text.pack(anchor='w')
        
        subtitle = tk.Label(logo_frame, text="QR Code Scanner Tool",
                           font=('Segoe UI', 11),
                           bg=COLORS['bg_sidebar'], fg=COLORS['text_secondary'])
        subtitle.pack(anchor='w', pady=(5, 0))
        
        # Divider
        divider = tk.Frame(sidebar_inner, bg=COLORS['border'], height=1)
        divider.pack(fill='x', pady=(0, 20))
        
        # ===== User Account Section =====
        user_section = tk.Frame(sidebar_inner, bg=COLORS['bg_card'])
        user_section.pack(fill='x', pady=(0, 15))
        
        # Section header
        section_header = tk.Frame(user_section, bg=COLORS['bg_card'])
        section_header.pack(fill='x', padx=15, pady=(15, 10))
        
        tk.Label(section_header, text="👤 User Account",
                font=('Segoe UI', 12, 'bold'),
                bg=COLORS['bg_card'], fg=COLORS['text_primary']).pack(anchor='w')
        
        # Mobile input
        input_frame = tk.Frame(user_section, bg=COLORS['bg_card'])
        input_frame.pack(fill='x', padx=15, pady=(0, 10))
        
        tk.Label(input_frame, text="Mobile Number",
                font=('Segoe UI', 9),
                bg=COLORS['bg_card'], fg=COLORS['text_secondary']).pack(anchor='w', pady=(0, 5))
        
        self.mobile_entry = ModernEntry(input_frame, placeholder="Enter your mobile number", width=28)
        self.mobile_entry.pack(fill='x')
        
        # Login button
        btn_frame = tk.Frame(user_section, bg=COLORS['bg_card'])
        btn_frame.pack(fill='x', padx=15, pady=(10, 15))
        
        self.login_btn = ModernButton(btn_frame, text="🔐 Login / Register", 
                                      command=self.handle_login, width=258, height=42)
        self.login_btn.pack(fill='x')
        
        # Status label
        self.status_label = tk.Label(user_section, text="Status: Not logged in",
                                    font=('Segoe UI', 9),
                                    bg=COLORS['bg_card'], fg=COLORS['text_muted'],
                                    wraplength=250, justify='left')
        self.status_label.pack(anchor='w', padx=15, pady=(0, 15))
        
        # ===== Phone Number Section =====
        phone_section = tk.Frame(sidebar_inner, bg=COLORS['bg_card'])
        phone_section.pack(fill='x', pady=(0, 15))
        
        section_header2 = tk.Frame(phone_section, bg=COLORS['bg_card'])
        section_header2.pack(fill='x', padx=15, pady=(15, 10))
        
        tk.Label(section_header2, text="📱 Scan Phone Number",
                font=('Segoe UI', 12, 'bold'),
                bg=COLORS['bg_card'], fg=COLORS['text_primary']).pack(anchor='w')
        
        input_frame2 = tk.Frame(phone_section, bg=COLORS['bg_card'])
        input_frame2.pack(fill='x', padx=15, pady=(0, 10))
        
        tk.Label(input_frame2, text="Phone Number to Add",
                font=('Segoe UI', 9),
                bg=COLORS['bg_card'], fg=COLORS['text_secondary']).pack(anchor='w', pady=(0, 5))
        
        self.phone_entry = ModernEntry(input_frame2, placeholder="Enter phone number", width=28)
        self.phone_entry.pack(fill='x')
        
        btn_frame2 = tk.Frame(phone_section, bg=COLORS['bg_card'])
        btn_frame2.pack(fill='x', padx=15, pady=(10, 15))
        
        self.submit_btn = ModernButton(btn_frame2, text="🚀 Generate QR Codes",
                                       command=self.handle_phone_submit, width=258, height=42)
        self.submit_btn.configure(state='disabled')
        self.submit_btn.pack(fill='x')
        
        # ===== Progress Section =====
        progress_section = tk.Frame(sidebar_inner, bg=COLORS['bg_card'])
        progress_section.pack(fill='x', pady=(0, 15))
        
        section_header3 = tk.Frame(progress_section, bg=COLORS['bg_card'])
        section_header3.pack(fill='x', padx=15, pady=(15, 10))
        
        tk.Label(section_header3, text="📊 Progress",
                font=('Segoe UI', 12, 'bold'),
                bg=COLORS['bg_card'], fg=COLORS['text_primary']).pack(anchor='w')
        
        # Progress indicators
        self.progress_frame = tk.Frame(progress_section, bg=COLORS['bg_card'])
        self.progress_frame.pack(fill='x', padx=15, pady=(0, 10))
        
        # Create progress circles
        self.progress_indicators = []
        progress_row = tk.Frame(self.progress_frame, bg=COLORS['bg_card'])
        progress_row.pack(anchor='center')
        
        for i in range(4):
            indicator = tk.Label(progress_row, text="○", font=('Segoe UI', 24),
                               bg=COLORS['bg_card'], fg=COLORS['text_muted'])
            indicator.pack(side='left', padx=8)
            self.progress_indicators.append(indicator)
        
        self.progress_label = tk.Label(progress_section, text="0 / 4 Completed",
                                       font=('Segoe UI', 10),
                                       bg=COLORS['bg_card'], fg=COLORS['text_secondary'])
        self.progress_label.pack(pady=(0, 15))
        
        # ===== Action Buttons =====
        action_frame = tk.Frame(sidebar_inner, bg=COLORS['bg_sidebar'])
        action_frame.pack(fill='x', pady=(0, 10))
        
        self.regenerate_btn = ModernButton(action_frame, text="🔄 Regenerate QR",
                                           command=self.regenerate_qr, width=280, height=38,
                                           bg=COLORS['bg_card'], hover_bg=COLORS['highlight'])
        self.regenerate_btn.configure(state='disabled')
        self.regenerate_btn.pack(fill='x', pady=(0, 10))
        
        self.stats_btn = ModernButton(action_frame, text="📈 View Statistics",
                                      command=self.show_stats, width=280, height=38,
                                      bg=COLORS['bg_card'], hover_bg=COLORS['highlight'])
        self.stats_btn.configure(state='disabled')
        self.stats_btn.pack(fill='x')
        
        # ========== MAIN AREA ==========
        main_area = tk.Frame(self.root, bg=COLORS['bg_main'])
        main_area.grid(row=0, column=1, sticky='nsew', padx=20, pady=20)
        main_area.columnconfigure(0, weight=1)
        main_area.rowconfigure(0, weight=3)
        main_area.rowconfigure(1, weight=1)
        
        # ===== QR Code Display =====
        qr_frame = tk.Frame(main_area, bg=COLORS['bg_card'])
        qr_frame.grid(row=0, column=0, sticky='nsew', pady=(0, 15))
        qr_frame.columnconfigure(0, weight=1)
        qr_frame.rowconfigure(1, weight=1)
        
        # QR section header
        qr_header = tk.Frame(qr_frame, bg=COLORS['bg_card'])
        qr_header.grid(row=0, column=0, sticky='ew', padx=20, pady=(20, 10))
        
        tk.Label(qr_header, text="📱 Scan QR Code with WhatsApp",
                font=('Segoe UI', 14, 'bold'),
                bg=COLORS['bg_card'], fg=COLORS['text_primary']).pack(anchor='w')
        
        tk.Label(qr_header, text="Open WhatsApp > Settings > Linked Devices > Link a Device",
                font=('Segoe UI', 10),
                bg=COLORS['bg_card'], fg=COLORS['text_secondary']).pack(anchor='w', pady=(5, 0))
        
        # QR code container
        qr_container = tk.Frame(qr_frame, bg=COLORS['bg_card'])
        qr_container.grid(row=1, column=0, sticky='nsew', padx=20, pady=(10, 20))
        qr_container.columnconfigure(0, weight=1)
        qr_container.rowconfigure(0, weight=1)
        
        # QR code display area with border - larger for better QR visibility
        qr_display = tk.Frame(qr_container, bg=COLORS['bg_input'], 
                             highlightthickness=2, highlightbackground=COLORS['border'])
        qr_display.place(relx=0.5, rely=0.5, anchor='center', width=320, height=320)
        
        self.qr_label = tk.Label(qr_display, 
                                text="🔒\n\nNo QR Code Generated\n\nLogin and enter a phone number\nto start scanning",
                                font=('Segoe UI', 12),
                                bg=COLORS['bg_input'], fg=COLORS['text_muted'],
                                justify='center')
        self.qr_label.pack(expand=True, fill='both', padx=5, pady=5)
        
        # Current site indicator
        self.site_indicator = tk.Label(qr_frame, text="",
                                       font=('Segoe UI', 11, 'bold'),
                                       bg=COLORS['bg_card'], fg=COLORS['accent'])
        self.site_indicator.grid(row=2, column=0, pady=(0, 15))
        
        # ===== Activity Log =====
        log_frame = tk.Frame(main_area, bg=COLORS['bg_card'])
        log_frame.grid(row=1, column=0, sticky='nsew')
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(1, weight=1)
        
        log_header = tk.Frame(log_frame, bg=COLORS['bg_card'])
        log_header.grid(row=0, column=0, sticky='ew', padx=15, pady=(15, 10))
        
        tk.Label(log_header, text="📝 Activity Log",
                font=('Segoe UI', 12, 'bold'),
                bg=COLORS['bg_card'], fg=COLORS['text_primary']).pack(anchor='w')
        
        # Custom styled text widget
        log_container = tk.Frame(log_frame, bg=COLORS['bg_input'])
        log_container.grid(row=1, column=0, sticky='nsew', padx=15, pady=(0, 15))
        log_container.columnconfigure(0, weight=1)
        log_container.rowconfigure(0, weight=1)
        
        self.status_text = tk.Text(log_container, height=6, wrap='word',
                                   bg=COLORS['bg_input'], fg=COLORS['text_secondary'],
                                   font=('Consolas', 10), relief='flat',
                                   insertbackground=COLORS['text_primary'],
                                   selectbackground=COLORS['highlight'],
                                   padx=10, pady=10)
        self.status_text.grid(row=0, column=0, sticky='nsew')
        self.status_text.config(state='disabled')
        
        # Scrollbar
        scrollbar = tk.Scrollbar(log_container, command=self.status_text.yview,
                                bg=COLORS['bg_input'], troughcolor=COLORS['bg_input'])
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.status_text.config(yscrollcommand=scrollbar.set)
    
    def check_login_state(self):
        """Check if user should be auto-logged in (from previous session)"""
        # Could implement session persistence here
        pass
    
    def log_status(self, message, msg_type='info'):
        """Log status message with color coding"""
        self.status_text.config(state='normal')
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Add tag for coloring
        tag_name = f"tag_{len(self.status_text.get('1.0', 'end'))}"
        
        if msg_type == 'success':
            color = COLORS['success']
        elif msg_type == 'error':
            color = COLORS['error']
        elif msg_type == 'warning':
            color = COLORS['warning']
        else:
            color = COLORS['text_secondary']
        
        self.status_text.tag_config(tag_name, foreground=color)
        self.status_text.insert('end', f"[{timestamp}] {message}\n", tag_name)
        self.status_text.see('end')
        self.status_text.config(state='disabled')
    
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
                return False, "Your account is pending approval.\nAdmin will review your request soon."
            elif status == 'rejected':
                return False, "Your account has been rejected.\nPlease contact admin."
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
            self.show_modern_message("Error", "Please enter your mobile number", "error")
            return
        
        self.login_btn.configure(state='disabled', text="⏳ Checking...")
        self.log_status("Checking login credentials...")
        
        def login_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            success, message = loop.run_until_complete(self.handle_login_async(mobile))
            loop.close()
            
            self.root.after(0, lambda: self.login_callback(success, message))
        
        threading.Thread(target=login_thread, daemon=True).start()
    
    def login_callback(self, success, message):
        """Callback after login attempt"""
        self.login_btn.configure(state='normal', text="🔐 Login / Register")
        
        if success:
            self.status_label.config(text=f"✅ Logged in: {format_phone_number(self.current_mobile)}", 
                                    fg=COLORS['success'])
            self.submit_btn.configure(state='normal')
            self.stats_btn.configure(state='normal')
            self.mobile_entry.configure(state='disabled')
            self.log_status(message, 'success')
            self.show_modern_message("Success", message, "success")
        else:
            self.status_label.config(text=f"❌ {message}", fg=COLORS['error'])
            self.log_status(message, 'error')
            self.show_modern_message("Error", message, "error")
    
    def show_modern_message(self, title, message, msg_type='info'):
        """Show a modern-styled message dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("400x200")
        dialog.configure(bg=COLORS['bg_card'])
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 200) // 2
        dialog.geometry(f"+{x}+{y}")
        
        # Icon
        if msg_type == 'success':
            icon = "✅"
            color = COLORS['success']
        elif msg_type == 'error':
            icon = "❌"
            color = COLORS['error']
        else:
            icon = "ℹ️"
            color = COLORS['accent']
        
        tk.Label(dialog, text=icon, font=('Segoe UI', 36),
                bg=COLORS['bg_card'], fg=color).pack(pady=(20, 10))
        
        tk.Label(dialog, text=message, font=('Segoe UI', 11),
                bg=COLORS['bg_card'], fg=COLORS['text_primary'],
                wraplength=350, justify='center').pack(pady=(0, 20))
        
        ok_btn = ModernButton(dialog, text="OK", command=dialog.destroy,
                             width=100, height=35)
        ok_btn.pack()
    
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
            self.show_modern_message("Error", "Please enter a phone number", "error")
            return
        
        self.submit_btn.configure(state='disabled', text="⏳ Processing...")
        self.log_status(f"Processing: {format_phone_number(phone)}")
        
        def submit_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            success, message = loop.run_until_complete(self.handle_phone_submit_async(phone))
            loop.close()
            
            self.root.after(0, lambda: self.submit_callback(success, message))
        
        threading.Thread(target=submit_thread, daemon=True).start()
    
    def submit_callback(self, success, message):
        """Callback after phone submit"""
        self.submit_btn.configure(state='normal', text="🚀 Generate QR Codes")
        
        if not success:
            self.log_status(f"Error: {message}", 'error')
            self.show_modern_message("Error", message, "error")
    
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
            self.root.after(0, lambda: self.log_status(f"Generating QR for {site_name}..."))
            self.root.after(0, lambda: self.site_indicator.config(text=f"🔄 Current: {site_name}"))
            qr_image, error = generate_qr_code(website, user_id, next_index)
            
            if error:
                return False, error
            
            # Display QR code
            self.root.after(0, lambda: self.display_qr_code(qr_image, site_name))
            self.root.after(0, lambda: self.log_status(f"QR ready for {site_name} - Please scan!", 'success'))
            
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
            
            # Resize for display - fit within container
            max_size = 300
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(img)
            
            # Update label
            self.qr_label.config(image=photo, text="", bg='white')
            self.qr_label.image = photo  # Keep a reference
            
            # Update progress
            self.update_progress()
            
            # Enable regenerate button
            self.regenerate_btn.configure(state='normal')
            
            # Update site indicator
            self.site_indicator.config(text=f"📍 Scanning: {site_name}")
        
        except Exception as e:
            self.log_status(f"Error displaying QR: {str(e)}", 'error')
    
    def update_progress(self):
        """Update progress display"""
        completed = len(self.completed_websites)
        total = len(WEBSITES)
        
        # Update progress indicators
        for i, indicator in enumerate(self.progress_indicators):
            if i in self.completed_websites:
                indicator.config(text="●", fg=COLORS['success'])
            elif i == self.current_index:
                indicator.config(text="◉", fg=COLORS['accent'])
            else:
                indicator.config(text="○", fg=COLORS['text_muted'])
        
        self.progress_label.config(text=f"{completed} / {total} Completed")
    
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
                    self.root.after(0, lambda pc=poll_count: self.log_status(f"Waiting for scan... ({pc * 2}s)"))
            
            elif status.get("status") == "error":
                self.root.after(0, lambda s=status: self.log_status(f"Error: {s.get('message')}", 'error'))
                break
        
        if poll_count >= max_polls:
            self.root.after(0, lambda: self.handle_scan_timeout(website_index))
    
    def handle_scan_success(self, website_index, website, phone, name):
        """Handle successful scan"""
        self.is_polling = False
        
        site_name = get_site_name(website_index)
        self.log_status(f"✅ {site_name} - Success!", 'success')
        if phone:
            self.log_status(f"📱 Phone: {phone}", 'success')
        if name:
            self.log_status(f"👤 Name: {name}", 'success')
        
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
            self.root.after(0, lambda: self.log_status(f"DB Error: {str(e)}", 'error'))
    
    def handle_scan_timeout(self, website_index):
        """Handle scan timeout"""
        self.is_polling = False
        site_name = get_site_name(website_index)
        self.log_status(f"⏰ QR expired for {site_name}", 'warning')
        self.site_indicator.config(text=f"⏰ Expired: {site_name} - Click Regenerate")
        
    def handle_all_completed(self):
        """Handle all websites completed"""
        self.log_status("🎉 All websites completed!", 'success')
        
        # Mark number as completed
        def mark_completed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.mark_completed_async())
            loop.close()
        
        threading.Thread(target=mark_completed, daemon=True).start()
        
        # Store completed phone for re-scan
        self.last_completed_phone = self.current_phone_number
        
        # Show completion dialog with re-scan option
        self.show_completion_dialog()
        
        # Reset state but keep last_completed_phone
        self.completed_websites = []
        self.current_index = 0
        self.current_phone_number = None
        self.current_phone_number_id = None
        self.phone_entry.delete(0, 'end')
        self.qr_label.config(image="", text="🔒\n\nNo QR Code Generated\n\nEnter another phone number\nor use Re-scan for unlinked accounts", bg=COLORS['bg_input'])
        self.qr_label.image = None
        self.regenerate_btn.configure(state='disabled')
        self.site_indicator.config(text="")
        self.update_progress()
    
    def show_completion_dialog(self):
        """Show completion dialog with re-scan options"""
        dialog = tk.Toplevel(self.root)
        dialog.title("All Sites Completed!")
        dialog.geometry("450x400")
        dialog.configure(bg=COLORS['bg_card'])
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 450) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 400) // 2
        dialog.geometry(f"+{x}+{y}")
        
        # Header
        tk.Label(dialog, text="🎉", font=('Segoe UI', 48),
                bg=COLORS['bg_card'], fg=COLORS['success']).pack(pady=(20, 10))
        
        tk.Label(dialog, text="All 4 Sites Completed!",
                font=('Segoe UI', 16, 'bold'),
                bg=COLORS['bg_card'], fg=COLORS['text_primary']).pack()
        
        phone_display = format_phone_number(self.last_completed_phone) if self.last_completed_phone else ""
        tk.Label(dialog, text=f"📱 {phone_display}\n💰 Earnings added to your account!",
                font=('Segoe UI', 11),
                bg=COLORS['bg_card'], fg=COLORS['text_secondary'],
                justify='center').pack(pady=(10, 20))
        
        # Re-scan section
        tk.Label(dialog, text="🔄 Re-scan if WhatsApp got unlinked:",
                font=('Segoe UI', 10),
                bg=COLORS['bg_card'], fg=COLORS['text_muted']).pack(pady=(0, 10))
        
        # Re-scan buttons frame
        rescan_frame = tk.Frame(dialog, bg=COLORS['bg_card'])
        rescan_frame.pack(fill='x', padx=30, pady=(0, 15))
        
        for i in range(len(WEBSITES)):
            site_name = get_site_name(i)
            btn = ModernButton(rescan_frame, text=f"🔄 {site_name}",
                              command=lambda idx=i, d=dialog: self.start_rescan(idx, d),
                              width=180, height=35,
                              bg=COLORS['bg_input'], hover_bg=COLORS['highlight'],
                              font_size=10)
            btn.pack(pady=3)
        
        # New number button
        new_btn = ModernButton(dialog, text="📱 Add New Number",
                              command=dialog.destroy,
                              width=200, height=40)
        new_btn.pack(pady=(10, 20))
    
    def start_rescan(self, website_index, dialog=None):
        """Start re-scanning a specific website"""
        if dialog:
            dialog.destroy()
        
        if not self.last_completed_phone:
            self.show_modern_message("Error", "No completed number found.\nPlease add a new number first.", "error")
            return
        
        self.is_rescan_mode = True
        self.current_phone_number = self.last_completed_phone
        self.current_index = website_index
        
        site_name = get_site_name(website_index)
        self.log_status(f"🔄 Re-scanning {site_name}...")
        self.site_indicator.config(text=f"🔄 Re-scan: {site_name}")
        
        # Generate QR for re-scan
        def rescan():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.generate_rescan_qr(website_index))
            loop.close()
        
        threading.Thread(target=rescan, daemon=True).start()
    
    async def generate_rescan_qr(self, website_index):
        """Generate QR code for re-scanning (no success tracking)"""
        try:
            website = WEBSITES[website_index]
            site_name = get_site_name(website_index)
            
            user_id = self.get_session_user_id()
            if not user_id:
                self.root.after(0, lambda: self.log_status("Session error. Please login again.", 'error'))
                return
            
            # Generate QR code
            qr_image, error = generate_qr_code(website, user_id, website_index)
            
            if error:
                self.root.after(0, lambda: self.log_status(f"Error: {error}", 'error'))
                self.root.after(0, lambda: self.show_modern_message("Error", error, "error"))
                return
            
            # Display QR code
            self.root.after(0, lambda: self.display_rescan_qr(qr_image, site_name, website_index))
            self.root.after(0, lambda: self.log_status(f"🔄 Re-scan QR for {site_name} ready!", 'success'))
            
        except Exception as e:
            self.root.after(0, lambda: self.log_status(f"Error: {str(e)}", 'error'))
    
    def display_rescan_qr(self, qr_image_bytes, site_name, website_index):
        """Display QR code for re-scan with navigation"""
        try:
            # Convert bytes to PIL Image
            qr_image_bytes.seek(0)
            img = Image.open(qr_image_bytes)
            
            # Resize for display - fit within container
            max_size = 300
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(img)
            
            # Update label
            self.qr_label.config(image=photo, text="", bg='white')
            self.qr_label.image = photo
            
            # Update site indicator with navigation hint
            phone_display = format_phone_number(self.current_phone_number) if self.current_phone_number else ""
            self.site_indicator.config(text=f"🔄 Re-scan: {site_name} | 📱 {phone_display}")
            
            # Show re-scan navigation buttons
            self.show_rescan_navigation(website_index)
            
        except Exception as e:
            self.log_status(f"Error displaying QR: {str(e)}", 'error')
    
    def show_rescan_navigation(self, current_index):
        """Show navigation buttons for re-scan mode"""
        # Create navigation frame if not exists
        if hasattr(self, 'rescan_nav_frame') and self.rescan_nav_frame:
            self.rescan_nav_frame.destroy()
        
        self.rescan_nav_frame = tk.Frame(self.root, bg=COLORS['bg_main'])
        self.rescan_nav_frame.place(relx=0.65, rely=0.75, anchor='center')
        
        nav_frame = tk.Frame(self.rescan_nav_frame, bg=COLORS['bg_main'])
        nav_frame.pack()
        
        # Previous button
        if current_index > 0:
            prev_btn = ModernButton(nav_frame, text="⬅️ Previous",
                                   command=lambda: self.navigate_rescan(current_index - 1),
                                   width=100, height=35,
                                   bg=COLORS['bg_card'], hover_bg=COLORS['highlight'],
                                   font_size=10)
            prev_btn.pack(side='left', padx=5)
        
        # Next button
        if current_index < len(WEBSITES) - 1:
            next_btn = ModernButton(nav_frame, text="Next ➡️",
                                   command=lambda: self.navigate_rescan(current_index + 1),
                                   width=100, height=35,
                                   bg=COLORS['bg_card'], hover_bg=COLORS['highlight'],
                                   font_size=10)
            next_btn.pack(side='left', padx=5)
        
        # Done button
        done_btn = ModernButton(nav_frame, text="✅ Done",
                               command=self.exit_rescan_mode,
                               width=80, height=35,
                               font_size=10)
        done_btn.pack(side='left', padx=5)
    
    def navigate_rescan(self, website_index):
        """Navigate to another site in re-scan mode"""
        self.current_index = website_index
        site_name = get_site_name(website_index)
        self.log_status(f"🔄 Switching to {site_name}...")
        
        def rescan():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.generate_rescan_qr(website_index))
            loop.close()
        
        threading.Thread(target=rescan, daemon=True).start()
    
    def exit_rescan_mode(self):
        """Exit re-scan mode"""
        self.is_rescan_mode = False
        
        # Remove navigation frame
        if hasattr(self, 'rescan_nav_frame') and self.rescan_nav_frame:
            self.rescan_nav_frame.destroy()
            self.rescan_nav_frame = None
        
        # Reset UI
        self.qr_label.config(image="", text="🔒\n\nNo QR Code Generated\n\nEnter a phone number to start", bg=COLORS['bg_input'])
        self.qr_label.image = None
        self.site_indicator.config(text="")
        self.log_status("Re-scan mode ended. Ready for new number.", 'success')
    
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
            self.root.after(0, lambda: self.log_status(f"Error: {str(e)}", 'error'))
    
    def regenerate_qr(self):
        """Regenerate current QR code"""
        if self.current_index is None:
            return
        
        self.is_polling = False
        self.regenerate_btn.configure(state='disabled')
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
        """Display statistics in a modern dialog"""
        if not stats:
            self.show_modern_message("Error", "Could not retrieve statistics", "error")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Your Statistics")
        dialog.geometry("450x350")
        dialog.configure(bg=COLORS['bg_card'])
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 450) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 350) // 2
        dialog.geometry(f"+{x}+{y}")
        
        # Header
        tk.Label(dialog, text="📊 Your Statistics",
                font=('Segoe UI', 18, 'bold'),
                bg=COLORS['bg_card'], fg=COLORS['text_primary']).pack(pady=(25, 20))
        
        # Stats grid
        stats_frame = tk.Frame(dialog, bg=COLORS['bg_card'])
        stats_frame.pack(fill='x', padx=40, pady=(0, 20))
        
        stat_items = [
            ("📱 Numbers Added Today", stats['numbers_added']),
            ("✅ Numbers Completed Today", stats['numbers_completed']),
            ("💰 Today's Earnings", f"{stats['today_earnings']:.2f} Tk"),
            ("💵 Total Earnings", f"{stats['total_earnings']:.2f} Tk"),
        ]
        
        for label, value in stat_items:
            row = tk.Frame(stats_frame, bg=COLORS['bg_input'])
            row.pack(fill='x', pady=5)
            
            tk.Label(row, text=label, font=('Segoe UI', 11),
                    bg=COLORS['bg_input'], fg=COLORS['text_secondary'],
                    anchor='w').pack(side='left', fill='x', expand=True, padx=15, pady=12)
            
            tk.Label(row, text=str(value), font=('Segoe UI', 12, 'bold'),
                    bg=COLORS['bg_input'], fg=COLORS['accent'],
                    anchor='e').pack(side='right', padx=15, pady=12)
        
        # Close button
        close_btn = ModernButton(dialog, text="Close", command=dialog.destroy,
                                width=120, height=38)
        close_btn.pack(pady=(10, 25))


def main():
    root = tk.Tk()
    app = PCQRTool(root)
    root.mainloop()


if __name__ == "__main__":
    main()
