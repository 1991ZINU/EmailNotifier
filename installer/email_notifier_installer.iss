[Setup]
AppName=Email Notifier
AppVersion=1.0.0
DefaultDirName={userdesktop}\EmailNotifier
DefaultGroupName=Email Notifier
OutputBaseFilename=EmailNotifier_Installer
Compression=lzma
SolidCompression=yes
ArchitecturesAllowed=x64
PrivilegesRequired=admin

[Files]
Source: "E:\EmailNotifier\dist\EmailNotifier.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Email Notifier"; Filename: "{app}\EmailNotifier.exe"
Name: "{group}\Uninstall Email Notifier"; Filename: "{uninstallexe}";

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
