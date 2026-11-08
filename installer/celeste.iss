; installer/celeste.iss — the Windows installer of Céleste (Inno Setup 6)
;
; Built by scripts/build_exe.py after PyInstaller (dist/Celeste/):
;   ISCC.exe /DAppVersion=4.7 installer\celeste.iss
; gives dist\Celeste-4.7-Setup.exe. The file is UTF-8 with a BOM (accents).

#ifndef AppVersion
  #define AppVersion "dev"
#endif

[Setup]
; fixed identifier: never change it, it links the successive versions
AppId={{0AF9FB2B-F885-482E-B583-14CBECBFE32F}
AppName=Céleste
AppVersion={#AppVersion}
AppVerName=Céleste {#AppVersion}
AppPublisher=Astræos
AppPublisherURL=https://astraeos-dev.github.io/personnal-site/
AppSupportURL=https://github.com/astraeos-dev/Celeste_App/issues
AppUpdatesURL=https://github.com/astraeos-dev/Celeste_App
DefaultDirName={autopf}\Celeste
DefaultGroupName=Céleste
DisableProgramGroupPage=yes
SetupIconFile=..\build\icons\celeste.ico
UninstallDisplayIcon={app}\Celeste.exe
UninstallDisplayName=Céleste
OutputDir=..\dist
OutputBaseFilename=Celeste-{#AppVersion}-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; without administrator rights, or for all users when chosen;
; the automatic update (updater.py) keeps the same mode with /CURRENTUSER or /ALLUSERS
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline dialog
; Céleste open during an update: closed, then reopened ([Run])
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "de"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\Celeste\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Céleste"; Filename: "{app}\Celeste.exe"; IconFilename: "{app}\Celeste.exe"
Name: "{group}\{cm:UninstallProgram,Céleste}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Céleste"; Filename: "{app}\Celeste.exe"; IconFilename: "{app}\Celeste.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Celeste.exe"; Description: "{cm:LaunchProgram,Céleste}"; Flags: nowait postinstall skipifsilent
; automatic update (silent installation): Céleste reopens
Filename: "{app}\Celeste.exe"; Flags: nowait skipifnotsilent
