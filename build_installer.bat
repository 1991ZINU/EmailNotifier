@echo off
chcp 65001 > nul
pyinstaller --clean --onefile --windowed --name=EmailNotifier --paths src --hidden-import notifier --hidden-import win32crypt --hidden-import win32cryptcon --hidden-import winotify --hidden-import winotify.audio src\main.py
if %ERRORLEVEL% neq 0 (
    echo PyInstaller ERROR
    pause
    exit /b %ERRORLEVEL%
)
echo PyInstaller OK!
echo.

E:\Inno_Setup_6\ISCC.exe "installer\email_notifier_installer.iss"
if %ERRORLEVEL% neq 0 (
    echo Inno Setup ERROR
    pause
    exit /b %ERRORLEVEL%
)
echo.
echo ===================================================
echo OK
echo Output : installer\Output\EmailNotifier_Installer.exe
echo ===================================================
echo.
pause
