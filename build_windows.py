#!/usr/bin/env python3
"""
Windows Build Script for PDF Label Processor
This script packages the application for Windows distribution.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def check_dependencies():
    """Check if PyInstaller is installed."""
    try:
        import PyInstaller
        print("✓ PyInstaller is installed")
        return True
    except ImportError:
        print("✗ PyInstaller not found")
        return False

def install_pyinstaller():
    """Install PyInstaller if not present."""
    print("Installing PyInstaller...")
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])
        print("✓ PyInstaller installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install PyInstaller: {e}")
        return False

def create_spec_file():
    """Create a PyInstaller spec file for the application."""
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['pdf_gui.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'fitz',
        'PIL',
        'PIL._tkinter_finder'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PDF_Label_Processor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if os.path.exists('icon.ico') else None,
)
'''
    
    with open('pdf_processor.spec', 'w') as f:
        f.write(spec_content)
    print("✓ Created PyInstaller spec file")

def create_icon():
    """Create a simple icon file if it doesn't exist."""
    if not os.path.exists('icon.ico'):
        print("Creating placeholder icon...")
        # Create a simple text-based icon placeholder
        icon_content = '''# This is a placeholder for an icon file
# You can replace this with a proper .ico file
# Recommended size: 256x256 pixels
'''
        with open('icon_placeholder.txt', 'w') as f:
            f.write(icon_content)
        print("✓ Created icon placeholder (replace with proper .ico file)")

def build_application():
    """Build the application using PyInstaller."""
    print("Building application...")
    
    # Create spec file
    create_spec_file()
    
    # Create icon placeholder
    create_icon()
    
    # Build command
    cmd = [
        'pyinstaller',
        '--clean',
        '--onefile',
        '--windowed',
        '--name=PDF_Label_Processor',
        'pdf_gui.py'
    ]
    
    # Add icon if it exists
    if os.path.exists('icon.ico'):
        cmd.extend(['--icon=icon.ico'])
    
    try:
        subprocess.check_call(cmd)
        print("✓ Application built successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Build failed: {e}")
        return False

def create_installer_script():
    """Create a simple installer script."""
    installer_content = '''@echo off
echo PDF Label Processor Installer
echo ============================
echo.
echo This will install PDF Label Processor to your system.
echo.

set /p choice="Do you want to install to Program Files? (y/n): "
if /i "%choice%"=="y" (
    set "install_dir=C:\\Program Files\\PDF Label Processor"
) else (
    set "install_dir=%USERPROFILE%\\Desktop\\PDF Label Processor"
)

echo.
echo Installing to: %install_dir%
echo.

if not exist "%install_dir%" mkdir "%install_dir%"

copy "dist\\PDF_Label_Processor.exe" "%install_dir%\\"
copy "README.md" "%install_dir%\\" 2>nul
copy "GUI_README.md" "%install_dir%\\" 2>nul

echo.
echo Installation complete!
echo.
echo You can find the application at: %install_dir%\\PDF_Label_Processor.exe
echo.
pause
'''
    
    with open('install.bat', 'w') as f:
        f.write(installer_content)
    print("✓ Created installer script")

def create_readme_windows():
    """Create a Windows-specific README."""
    readme_content = '''# PDF Label Processor for Windows

## Installation

### Option 1: Simple Installation
1. Download the `PDF_Label_Processor.exe` file
2. Double-click to run (no installation required)

### Option 2: Full Installation
1. Run `install.bat` as administrator
2. Choose installation location
3. Application will be installed to your chosen directory

## Usage

1. **Double-click** `PDF_Label_Processor.exe` to start the application
2. **Select Input File**: Click "Browse" to choose your PDF file
3. **Process**: Click "Process PDF" to start processing
4. **View Results**: The processed file will be saved automatically

## Features

- **No Installation Required**: Runs directly from the executable
- **User-Friendly Interface**: Simple drag-and-drop file selection
- **Real-time Progress**: See processing status and logs
- **Automatic Output**: Files are saved with descriptive names

## System Requirements

- Windows 10 or later
- No additional software required
- Minimum 100MB free disk space

## Troubleshooting

### "Windows protected your PC" message
1. Click "More info"
2. Click "Run anyway"
3. This is normal for unsigned applications

### Application won't start
1. Ensure you have Windows 10 or later
2. Try running as administrator
3. Check Windows Defender settings

### Processing fails
1. Ensure your PDF file is not corrupted
2. Check that you have write permissions in the output directory
3. Try processing a smaller file first

## File Structure

```
PDF Label Processor/
├── PDF_Label_Processor.exe    # Main application
├── README.md                  # This file
├── GUI_README.md             # Detailed usage guide
└── install.bat               # Installer script
```

## Support

If you encounter issues:
1. Check the processing log in the application
2. Ensure your PDF file is valid
3. Try running the application as administrator

## Version Information

- Version: 1.0.0
- Built with: PyInstaller
- Python Version: 3.13
- Dependencies: PyMuPDF, tkinter
'''
    
    with open('README_Windows.md', 'w') as f:
        f.write(readme_content)
    print("✓ Created Windows README")

def create_distribution_package():
    """Create a complete distribution package."""
    print("Creating distribution package...")
    
    # Create dist directory structure
    dist_dir = Path("dist/PDF_Label_Processor")
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy executable
    if os.path.exists("dist/PDF_Label_Processor.exe"):
        shutil.copy("dist/PDF_Label_Processor.exe", dist_dir)
        print("✓ Copied executable")
    
    # Copy documentation
    for doc_file in ["README.md", "GUI_README.md", "README_Windows.md"]:
        if os.path.exists(doc_file):
            shutil.copy(doc_file, dist_dir)
            print(f"✓ Copied {doc_file}")
    
    # Copy installer
    if os.path.exists("install.bat"):
        shutil.copy("install.bat", dist_dir)
        print("✓ Copied installer")
    
    # Create zip file
    try:
        shutil.make_archive("PDF_Label_Processor_Windows", 'zip', dist_dir)
        print("✓ Created distribution ZIP file")
        return True
    except Exception as e:
        print(f"✗ Failed to create ZIP: {e}")
        return False

def main():
    """Main build process."""
    print("PDF Label Processor - Windows Build")
    print("=" * 40)
    
    # Check and install PyInstaller
    if not check_dependencies():
        if not install_pyinstaller():
            print("Failed to install PyInstaller. Please install it manually:")
            print("pip install pyinstaller")
            return
    
    # Build the application
    if not build_application():
        print("Build failed. Please check the error messages above.")
        return
    
    # Create installer and documentation
    create_installer_script()
    create_readme_windows()
    
    # Create distribution package
    if create_distribution_package():
        print("\n" + "=" * 40)
        print("BUILD COMPLETED SUCCESSFULLY!")
        print("=" * 40)
        print("\nDistribution files created:")
        print("- dist/PDF_Label_Processor.exe (standalone executable)")
        print("- PDF_Label_Processor_Windows.zip (complete package)")
        print("- install.bat (installer script)")
        print("- README_Windows.md (Windows-specific documentation)")
        print("\nYou can now distribute the ZIP file to Windows users.")
    else:
        print("Distribution package creation failed.")

if __name__ == "__main__":
    main() 