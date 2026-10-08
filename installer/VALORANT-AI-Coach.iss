#ifndef MyAppVersion
  #error MyAppVersion must be supplied by the release build
#endif
#ifndef SourceDir
  #error SourceDir must point to the PyInstaller onedir output
#endif
#ifndef OutputDir
  #error OutputDir must point to the release output directory
#endif

[Setup]
AppId={{9E6020A8-1C44-4C70-9CB7-78E694AA1B41}
AppName=VALORANT AI Coach
AppVersion={#MyAppVersion}
AppVerName=VALORANT AI Coach {#MyAppVersion}
DefaultDirName={localappdata}\Programs\VALORANT-AI-Coach
DefaultGroupName=VALORANT AI Coach
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputDir}
OutputBaseFilename=VALORANT-AI-Coach-Setup-{#MyAppVersion}-x64
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes
UsePreviousAppDir=yes
DirExistsWarning=no
CloseApplications=yes
RestartApplications=no
ChangesEnvironment=no
Uninstallable=yes
UninstallDisplayIcon={app}\VALORANT-AI-Coach.exe

[Tasks]
Name: "desktopicon"; Description: "デスクトップにショートカットを作成"; GroupDescription: "追加のショートカット:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\VALORANT AI Coach"; Filename: "{app}\VALORANT-AI-Coach.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\VALORANT AI Coach"; Filename: "{app}\VALORANT-AI-Coach.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\VALORANT-AI-Coach.exe"; Description: "VALORANT AI Coachを起動"; Flags: nowait postinstall skipifsilent
