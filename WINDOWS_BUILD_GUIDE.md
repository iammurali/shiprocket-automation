# Windows Build Guide

This guide explains how to package your PDF Label Processor application for Windows distribution.

## Prerequisites

### On macOS/Linux (Cross-compilation)
- Python 3.8 or later
- PyInstaller
- All project dependencies

### On Windows (Native build - Recommended)
- Python 3.8 or later
- Windows 10 or later
- All project dependencies

## Building Methods

### Method 1: Automated Build (Recommended)

#### On Windows:
1. **Download the project files** to your Windows machine
2. **Double-click** `build_windows.bat`
3. **Wait for completion** - the script will:
   - Install dependencies
   - Build the executable
   - Create distribution package

#### On macOS/Linux:
1. **Run the build script**:
   ```bash
   python build_windows.py
   ```

### Method 2: Manual Build

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Build with PyInstaller**:
   ```bash
   pyinstaller --clean --onefile --windowed --name=PDF_Label_Processor pdf_gui.py
   ```

3. **Create distribution package**:
   ```bash
   python build_windows.py
   ```

## Build Output

After successful build, you'll get:

### Files Created:
- `dist/PDF_Label_Processor.exe` - Standalone executable
- `PDF_Label_Processor_Windows.zip` - Complete distribution package
- `install.bat` - Windows installer script
- `README_Windows.md` - Windows-specific documentation

### Distribution Package Contents:
```
PDF_Label_Processor_Windows.zip
├── PDF_Label_Processor.exe    # Main application
├── README.md                  # General documentation
├── GUI_README.md             # GUI usage guide
├── README_Windows.md         # Windows-specific guide
└── install.bat               # Installer script
```

## Customization Options

### Adding an Icon
1. Create a `.ico` file (256x256 pixels recommended)
2. Name it `icon.ico`
3. Place it in the project root
4. Rebuild the application

### Changing Application Name
Edit `build_windows.py` and modify:
```python
'--name=PDF_Label_Processor'
```

### Adding Additional Files
Edit the `datas` section in the spec file:
```python
datas=[
    ('additional_file.txt', '.'),
    ('config.json', '.'),
],
```

## Troubleshooting

### Common Issues

#### "PyInstaller not found"
```bash
pip install pyinstaller
```

#### "Module not found" errors
Add missing modules to `hiddenimports` in the spec file:
```python
hiddenimports=[
    'missing_module_name',
],
```

#### Large executable size
- Use `--onefile` for single file
- Use `--onedir` for smaller size (creates folder)
- Exclude unnecessary modules with `--exclude-module`

#### Windows Defender warnings
- This is normal for unsigned executables
- Users need to click "Run anyway"
- Consider code signing for production

### Build Optimization

#### Reduce executable size:
```bash
pyinstaller --clean --onefile --windowed --strip --upx-dir=/path/to/upx pdf_gui.py
```

#### Include specific files only:
```bash
pyinstaller --clean --onefile --windowed --add-data "config.json;." pdf_gui.py
```

#### Debug build:
```bash
pyinstaller --clean --onefile --console --debug=all pdf_gui.py
```

## Distribution

### For End Users
1. **Share the ZIP file** - contains everything needed
2. **Users extract and run** - no installation required
3. **Optional installer** - for system-wide installation

### For Enterprise
1. **Network deployment** - place executable on shared drive
2. **Group Policy** - deploy via Active Directory
3. **SCCM/Intune** - enterprise software management

## Testing

### Before Distribution
1. **Test on clean Windows VM** - ensure no dependencies missing
2. **Test on different Windows versions** - 10, 11, Server
3. **Test with various PDF files** - different sizes and formats
4. **Test user permissions** - standard user vs administrator

### Test Checklist
- [ ] Application starts without errors
- [ ] File selection works
- [ ] PDF processing completes successfully
- [ ] Output files are created correctly
- [ ] GUI remains responsive during processing
- [ ] Error handling works properly

## Security Considerations

### Code Signing
For production use, consider code signing:
1. Purchase a code signing certificate
2. Sign the executable before distribution
3. This eliminates Windows Defender warnings

### Antivirus Exclusions
Some antivirus software may flag PyInstaller executables:
1. Submit to antivirus vendors for whitelisting
2. Add to antivirus exclusions for enterprise deployment
3. Use code signing to improve trust

## Version Management

### Updating the Application
1. **Increment version** in the application
2. **Rebuild** using the same process
3. **Test thoroughly** before distribution
4. **Update documentation** if needed

### Backward Compatibility
- Keep old versions available
- Test with existing user files
- Provide migration guides if needed

## Support

### For Build Issues
1. Check PyInstaller documentation
2. Verify all dependencies are installed
3. Test with minimal example first
4. Check Python and PyInstaller versions

### For Distribution Issues
1. Test on target Windows version
2. Check user permissions
3. Verify antivirus settings
4. Test with different PDF files

## Advanced Configuration

### Custom PyInstaller Hooks
Create `hooks/hook-custom.py`:
```python
from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files('your_module')
```

### Environment Variables
Set before building:
```bash
export PYTHONPATH=/path/to/additional/modules
export PYINSTALLER_OPTS="--additional-hooks-dir=hooks"
```

### Build Scripts
Create custom build configurations:
```bash
# Development build
pyinstaller --debug=all --console pdf_gui.py

# Production build
pyinstaller --clean --onefile --windowed --optimize=2 pdf_gui.py
``` 