# PDF Label Processor for Windows

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
