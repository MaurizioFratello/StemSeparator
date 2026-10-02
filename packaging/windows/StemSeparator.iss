; StemSeparator - Inno Setup installer script (Windows)
;
; Compiles the PyInstaller onedir produced by packaging/windows/StemSeparator-win.spec
; into a single installer. Build order (from the repository root, on Windows):
;
;     pyinstaller --noconfirm packaging\windows\StemSeparator-win.spec
;     "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" packaging\windows\StemSeparator.iss
;
; Needs Inno Setup 6.3 or newer (x64compatible architecture identifiers).
; Output: dist\installer\StemSeparator-<version>-win64.exe
;
; PKG-01  installs the onedir tree as-is; there is no onefile unpack step
; PKG-02  Qt plugins, torch, onnxruntime and the vendored bin\ffmpeg.exe arrive
;         inside {app} because the whole dist tree is copied
; PKG-05  the Visual C++ redistributable is probed in InitializeSetup and the
;         human-readable requirement is documented in docs/PACKAGING.md
;
; WHY a per-user install (PrivilegesRequired=lowest + dialog override): the app
; is distributed unsigned from GitHub Releases, and forcing elevation for every
; install of a desktop hobby app is the fastest way to lose users. Without admin
; rights Inno installs to %LOCALAPPDATA%\Programs\StemSeparator, which works
; because all writable state lives in %LOCALAPPDATA%\StemSeparator anyway
; (utils/platform_utils.py:user_data_dir) and never next to the binaries.

#define MyAppName "Stem Separator"
#define MyAppVersion "1.0.3"
#define MyAppPublisher "Maurizio Fratello"
#define MyAppURL "https://github.com/MaurizioFratello/StemSeparator"
#define MyAppExeName "StemSeparator.exe"
#define MyDistDir "..\..\dist\StemSeparator"

[Setup]
; WHY a fixed GUID: it is the identity Add/Remove Programs tracks. Changing it
; leaves the previous installation orphaned instead of upgrading it.
AppId={{8E4C6A1B-6F0B-4E55-9C2A-5D34F0D8C4E1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\StemSeparator
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableWelcomePage=no
LicenseFile=..\..\LICENSE
OutputDir=..\..\dist\installer
OutputBaseFilename=StemSeparator-{#MyAppVersion}-win64
SetupIconFile=StemSeparator.ico
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
; WHY opt-in and uninstall-only: personal settings, logs and the several-hundred
; MB model cache live in %LOCALAPPDATA%\StemSeparator and are worth keeping on a
; reinstall or upgrade.
Name: "deluserdata"; Description: "Remove personal settings, logs and downloaded models"; GroupDescription: "Keep or remove personal data:"; Flags: uninstall unchecked

[Files]
; The whole onedir tree, including _internal\ (Python, Qt plugins, torch,
; onnxruntime) and _internal\bin\ (vendored ffmpeg.exe / ffprobe.exe).
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Defensive clean-up inside {app}: a frozen run never writes here (config.py
; redirects all writable state to the per-user directory), but running the app
; with the install directory as the working directory from a source checkout
; does create these. Without these entries Inno refuses to remove a dirty tree
; and leaves the folder behind.
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\temp"
Type: files; Name: "{app}\.stemseparator.lock"
Type: files; Name: "{app}\user_settings.json"

[Code]
; WHY the data directory is created by the installer: the app would create it on
; first launch too, but doing it here gives the ACLs a chance to be set by
; Setup's own (possibly elevated) process instead of by a double-clicked app.
procedure CurStepChanged(CurStep: TSetupStep);
var
  LocalAppData: String;
  DataDir: String;
begin
  if CurStep = ssPostInstall then
  begin
    LocalAppData := GetEnv('LOCALAPPDATA');
    if LocalAppData = '' then
      LocalAppData := GetEnv('APPDATA');
    if LocalAppData <> '' then
    begin
      DataDir := AddBackslash(LocalAppData) + 'StemSeparator';
      if not ForceDirectories(DataDir) then
        Log('StemSeparator: could not pre-create ' + DataDir);
    end;
  end;
end;

; WHY in [Code] rather than [UninstallDelete]: those entries always fire, while
; the personal directory must only disappear when the user ticked the
; `deluserdata` task in the uninstall wizard.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  LocalAppData: String;
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if WizardIsTaskSelected('deluserdata') then
    begin
      LocalAppData := GetEnv('LOCALAPPDATA');
      if LocalAppData = '' then
        LocalAppData := GetEnv('APPDATA');
      if LocalAppData <> '' then
      begin
        DataDir := AddBackslash(LocalAppData) + 'StemSeparator';
        if DirExists(DataDir) then
          DelTree(DataDir, True, True, True);
      end;
    end;
  end;
end;

; PKG-05: the PyInstaller bootloader and every CUDA-enabled torch build need the
; Visual C++ 2015-2022 x64 runtime. Windows 11 and patched Windows 10 already
; ship vcruntime140.dll, so this informs instead of blocking the install.
function InitializeSetup(): Boolean;
begin
  Result := True;
  if not FileExists(ExpandConstant('{sys}\vcruntime140.dll')) then
    MsgBox(
      'The Microsoft Visual C++ 2015-2022 Redistributable (x64) is not installed.'#13#10#13#10 +
      'StemSeparator will install and start, but PyTorch inference may fail with ' +
      '"DLL load failed while importing _C".'#13#10 +
      'Install it from https://aka.ms/vs/17/release/vc_redist.x64.exe, then restart the app.'#13#10#13#10 +
      'Details: docs/PACKAGING.md, section "CUDA Installation".',
      mbInformation, OK);
end;
