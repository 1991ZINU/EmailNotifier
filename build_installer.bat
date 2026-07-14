@echo off
chcp 65001 > nul
setlocal

echo ===================================================
echo  EmailNotifier Build Script
echo ===================================================
echo.

pyinstaller --clean --onefile --windowed ^
    --name=EmailNotifier ^
    --paths src ^
    --hidden-import notifier ^
    --hidden-import win32crypt ^
    --hidden-import win32cryptcon ^
    --hidden-import winotify ^
    --hidden-import winotify.audio ^
    --add-data "C:\Python314\tcl\tcl8.6;tcl8.6" ^
    --add-data "C:\Python314\tcl\tk8.6;tk8.6" ^
    --add-binary "C:\Python314\DLLs\tcl86t.dll;." ^
    --add-binary "C:\Python314\DLLs\tk86t.dll;." ^
    src\main.py

if %ERRORLEVEL% neq 0 (
    echo [ERROR] PyInstaller 
    pause
    exit /b %ERRORLEVEL%
)
echo [OK] dist\EmailNotifier.exe
echo.

set ISCC=""

if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
) else if exist "E:\Inno_Setup_6\ISCC.exe" (
    set "ISCC=E:\Inno_Setup_6\ISCC.exe"
)

"%ISCC%" installer\email_notifier_installer.iss
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Inno Setupy
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ===================================================
echo  Output: installer\Output\EmailNotifier_Installer.exe
echo ===================================================
echo.
pause
