@echo off
echo PDF Label Processor Installer
echo ============================
echo.
echo This will install PDF Label Processor to your system.
echo.

set /p choice="Do you want to install to Program Files? (y/n): "
if /i "%choice%"=="y" (
    set "install_dir=C:\Program Files\PDF Label Processor"
) else (
    set "install_dir=%USERPROFILE%\Desktop\PDF Label Processor"
)

echo.
echo Installing to: %install_dir%
echo.

if not exist "%install_dir%" mkdir "%install_dir%"

copy "dist\PDF_Label_Processor.exe" "%install_dir%\"
copy "README.md" "%install_dir%\" 2>nul
copy "GUI_README.md" "%install_dir%\" 2>nul

echo.
echo Installation complete!
echo.
echo You can find the application at: %install_dir%\PDF_Label_Processor.exe
echo.
pause
