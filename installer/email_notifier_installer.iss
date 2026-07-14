#ifndef AppVersion
  #define AppVersion "1.1.1"
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
  ShellExec('open', 'taskkill.exe', '/f /im EmailNotifier.exe', '', SW_HIDE, ewWaitUntilTerminated, ErrorCode);
  Result := True;
end;
