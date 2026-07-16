#!/usr/bin/env python3
"""
PDF Label Processor GUI Launcher
This script launches the GUI application for processing PDF files.
"""

import sys
import subprocess

def check_dependencies():
    """Check if required packages are installed."""
    required_packages = ['fitz', 'tkinter']
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'fitz':
                import fitz
            elif package == 'tkinter':
                import tkinter
        except ImportError:
            missing_packages.append(package)
    
    return missing_packages

def check_macos_tk():
    """Check for macOS Tk 8.5 which has known blank-window bugs."""
    if sys.platform != 'darwin':
        return
    try:
        import tkinter
        if tkinter.TkVersion < 8.6:
            print("WARNING: You are using Tk {} which has known issues on macOS.".format(tkinter.TkVersion))
            print("The GUI may appear blank. To fix this, install Python from")
            print("  https://www.python.org/downloads/  (bundles Tk 8.6)")
            print("Or via Homebrew:  brew install python-tk")
            print()
    except Exception:
        pass

def install_dependencies():
    """Install missing dependencies."""
    print("Installing missing dependencies...")
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
        print("Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error installing dependencies: {e}")
        return False

def main():
    print("PDF Label Processor GUI")
    print("=" * 30)
    
    # Check dependencies
    missing = check_dependencies()
    
    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        response = input("Would you like to install them now? (y/n): ")
        if response.lower() in ['y', 'yes']:
            if install_dependencies():
                print("Dependencies installed. Starting GUI...")
            else:
                print("Failed to install dependencies. Please install them manually:")
                print("pip install -r requirements.txt")
                return
        else:
            print("Please install the required dependencies before running the GUI.")
            return
    
    # Check for macOS Tk issues
    check_macos_tk()
    
    # Import and run the GUI
    try:
        from pdf_gui import main as run_gui
        run_gui()
    except ImportError as e:
        print(f"Error importing GUI module: {e}")
        print("Make sure pdf_gui.py is in the same directory.")
    except Exception as e:
        print(f"Error running GUI: {e}")

if __name__ == "__main__":
    main() 