; ============================================================
; Email Notifier - Inno Setup Script
; 버전은 빌드 시 외부에서 주입: ISCC.exe /DAppVersion=1.2.3 ...
; 로컬 빌드 시 기본값 1.0.0 사용
; ============================================================
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppName=Email Notifier
AppVersion={#AppVersion}
AppPublisher=1991ZINU
AppPublisherURL=https://github.com/1991ZINU/EmailNotifier
AppSupportURL=https://github.com/1991ZINU/EmailNotifier/issues
DefaultDirName={userdesktop}\EmailNotifier
DefaultGroupName=Email Notifier
OutputBaseFilename=EmailNotifier_Installer
OutputDir=Output
Compression=lzma
SolidCompression=yes
ArchitecturesAllowed=x64
PrivilegesRequired=admin

[Files]
; 경로는 이 ISS 파일 위치(installer/)를 기준으로 한 상대 경로
Source: "..\dist\EmailNotifier.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Email Notifier"; Filename: "{app}\EmailNotifier.exe"
Name: "{group}\Uninstall Email Notifier"; Filename: "{uninstallexe}"

[UninstallDelete]
Type: files; Name: "{app}\config.yaml"
Type: files; Name: "{app}\EmailNotifier.lock"
Type: files; Name: "{app}\seen_ids.json"
Type: filesandordirs; Name: "{app}\logs"

[Run]
Filename: "{app}\EmailNotifier.exe"; Description: "Launch Email Notifier"; Flags: nowait postinstall

[Code]
function InitializeUninstall(): Boolean;
var
  ErrorCode: Integer;
begin
  // 삭제 진행 전 실행 중인 EmailNotifier.exe 강제 종료
  ShellExec('open', 'taskkill.exe', '/f /im EmailNotifier.exe', '', SW_HIDE, ewWaitUntilTerminated, ErrorCode);
  Result := True;
end;
