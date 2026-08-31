; Inno Setup script — CRYPTO Installer Edition (Windows x64)
; Build with Inno Setup 6+: iscc packaging/CRYPTO.iss
; Expects dist\CRYPTO\ from PyInstaller One-Folder build.

#define MyAppName "CRYPTO"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "whatman42"
#define MyAppExeName "CRYPTO.exe"
#define MyAppId "{{A8F3C2E1-4B5D-6E7F-8A9B-0C1D2E3F4A5B}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; User data lives in {localappdata}\CRYPTO — never delete on uninstall by default
PrivilegesRequired=admin
OutputDir=..\dist\installer
OutputBaseFilename=CRYPTO-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
RestartApplications=no
; Do NOT add Windows Defender exclusions

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &Desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked
Name: "startupicon"; Description: "Start {#MyAppName} with Windows (PAPER mode)"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
; One-Folder payload from PyInstaller (no .portable marker → INSTALLED mode)
Source: "..\dist\CRYPTO\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Explicitly do not ship secrets

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Parameters: ""; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "--smoke"; Flags: runhidden waituntilterminated; StatusMsg: "Validating installation..."
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Only remove empty app dir leftovers — NEVER {localappdata}\CRYPTO user data
Type: filesandordirs; Name: "{app}\_internal"
; Optional user-data removal is a separate explicit checkbox in [Code] if desired

[Code]
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  // Stop running instance before upgrade if possible
  if Exec('taskkill', '/IM CRYPTO.exe /F', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    // best-effort; continue even if not running
  end;
end;

function InitializeUninstall(): Boolean;
begin
  Result := True;
  // User data in {localappdata}\CRYPTO is preserved unless future custom page requests otherwise
end;
