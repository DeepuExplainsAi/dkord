#ifndef Version
  #error A version is required
#endif
#ifndef Source
  #error A source bundle is required
#endif
#ifndef Output
  #error An output directory is required
#endif
[Setup]
AppId=app.dkord.desktop
AppName=Dkord Desktop Preview
AppVersion={#Version}
AppPublisher=DeepuGupta
AppPublisherURL=https://github.com/DeepuExplainsAi/dkord
DefaultDirName={localappdata}\Programs\Dkord
DefaultGroupName=Dkord
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
OutputDir={#Output}
OutputBaseFilename=Dkord-desktop-v{#Version}-windows-x64
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
Name: "{userprograms}\Dkord"; Filename: "{app}\Dkord.exe"
Name: "{userdesktop}\Dkord"; Filename: "{app}\Dkord.exe"; Tasks: desktopicon
[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked
[Run]
Filename: "{app}\Dkord.exe"; Description: "Open Dkord"; Flags: nowait postinstall skipifsilent
; User libraries live outside {app}; NEVER add user-data cleanup or uninstall-delete scripts.
