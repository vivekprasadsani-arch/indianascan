"""
PC Tool Launcher
Double-click this file to run the QR Code Generator PC Tool
"""
import sys
import os

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    # Import and run the PC GUI tool
    from pc_gui_tool import main
    
    if __name__ == "__main__":
        print("Starting QR Code Generator PC Tool...")
        print("Please wait...")
        main()
except ImportError as e:
    print(f"Error: Missing required module: {e}")
    print("\nPlease install required packages:")
    print("pip install -r requirements.txt")
    input("\nPress Enter to exit...")
except Exception as e:
    print(f"Error starting application: {e}")
    print("\nPlease check the error message above.")
    input("\nPress Enter to exit...")

