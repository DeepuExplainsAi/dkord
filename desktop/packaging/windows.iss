#ifndef Version
  #error A version is required
#endif
#ifndef Source
  #error A source bundle is required
#endif
#ifndef Output
  #error An output directory is required
#endif
#ifndef Target
  #error An exact windows-x64 or windows-x86 target is required
#endif
[Setup]
#if Target == "windows-x86"
#define DisplayName "Dkord (32-bit)"
#define ShortcutName "Dkord (32-bit)"
AppId=app.dkord.desktop.x86
DefaultDirName={localappdata}\Programs\Dkord-x86
ArchitecturesAllowed=x86compatible
#elif Target == "windows-x64"
#define DisplayName "Dkord"
#define ShortcutName "Dkord"
AppId=app.dkord.desktop
DefaultDirName={localappdata}\Programs\Dkord
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
#else
  #error Unsupported Windows architecture
#endif
AppName={#DisplayName}
AppVersion={#Version}
AppPublisher=DeepuGupta
DefaultGroupName={#ShortcutName}
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
OutputDir={#Output}
OutputBaseFilename=Dkord-desktop-v{#Version}-{#Target}
SetupIconFile={#Source}\..\dkord.ico
UninstallDisplayIcon={app}\Dkord.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=yes
[Files]
Source: "{#Source}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{userprograms}\{#ShortcutName}"; Filename: "{app}\Dkord.exe"
Name: "{userdesktop}\{#ShortcutName}"; Filename: "{app}\Dkord.exe"; Tasks: desktopicon
[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked
[Run]
Filename: "{app}\Dkord.exe"; Description: "Open Dkord"; Flags: nowait postinstall skipifsilent
; User libraries live outside {app}; NEVER add user-data cleanup or uninstall-delete scripts.
