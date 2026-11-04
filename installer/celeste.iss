; installer/celeste.iss — programme d'installation de Céleste pour Windows (Inno Setup 6)
;
; Construit par scripts/build_exe.py après PyInstaller (dist/Celeste/) :
;   ISCC.exe /DAppVersion=4.2 installer\celeste.iss
; donne dist\Celeste-4.2-Setup.exe. Le fichier est en UTF-8 avec BOM (accents).

#ifndef AppVersion
  #define AppVersion "dev"
#endif

[Setup]
; identifiant fixe : ne pas le changer, il relie les versions successives
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
; sans droits d'administrateur, ou pour tous les utilisateurs si on le choisit ;
; la mise à jour automatique (updater.py) reprend le même mode par /CURRENTUSER ou /ALLUSERS
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline dialog
; Céleste ouvert pendant une mise à jour : fermé, puis rouvert ([Run])
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
; mise à jour automatique (installation silencieuse) : Céleste se rouvre
Filename: "{app}\Celeste.exe"; Flags: nowait skipifnotsilent
