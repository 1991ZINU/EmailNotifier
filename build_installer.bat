@echo off
chcp 65001 > nul
setlocal

echo ===================================================
echo  EmailNotifier Build Script
echo ===================================================
echo.

:: ── 1. PyInstaller 빌드 ──────────────────────────────
echo [1/2] PyInstaller로 EXE 빌드 중...
pyinstaller --clean --onefile --windowed ^
    --name=EmailNotifier ^
    --paths src ^
    --hidden-import notifier ^
    --hidden-import win32crypt ^
    --hidden-import win32cryptcon ^
    --hidden-import winotify ^
    --hidden-import winotify.audio ^
    src\main.py

if %ERRORLEVEL% neq 0 (
    echo [ERROR] PyInstaller 빌드 실패
    pause
    exit /b %ERRORLEVEL%
)
echo [OK] EXE 생성 완료: dist\EmailNotifier.exe
echo.

:: ── 2. Inno Setup 경로 자동 탐지 ────────────────────
echo [2/2] Inno Setup으로 인스톨러 빌드 중...
set ISCC=

if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
) else if exist "E:\Inno_Setup_6\ISCC.exe" (
    set "ISCC=E:\Inno_Setup_6\ISCC.exe"
)

if "%ISCC%"=="" (
    echo [ERROR] Inno Setup 6을 찾을 수 없습니다.
    echo         다음 경로 중 하나에 설치되어 있어야 합니다:
    echo           C:\Program Files (x86)\Inno Setup 6\ISCC.exe
    echo           C:\Program Files\Inno Setup 6\ISCC.exe
    pause
    exit /b 1
)

"%ISCC%" installer\email_notifier_installer.iss
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Inno Setup 빌드 실패
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ===================================================
echo  빌드 완료!
echo  Output: installer\Output\EmailNotifier_Installer.exe
echo ===================================================
echo.
pause
