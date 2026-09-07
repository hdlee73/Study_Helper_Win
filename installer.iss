#define AppName "Study Helper"
#ifndef AppVersion
#define AppVersion "2.1.0-rc.1"
#endif
[Setup]
AppId={{03633B7D-910C-4640-8DFE-8C1DF0B2B7DB}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\StudyHelper
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\StudyHelper.exe
OutputDir=installer_output
OutputBaseFilename=StudyHelper-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
[Files]
Source: "dist\StudyHelper\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
[Icons]
Name: "{group}\Study Helper"; Filename: "{app}\StudyHelper.exe"
Name: "{autodesktop}\Study Helper"; Filename: "{app}\StudyHelper.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\StudyHelper.exe"; Description: "Launch Study Helper"; Flags: nowait postinstall skipifsilent
