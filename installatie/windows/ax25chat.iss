; =============================================================================
;  AX25Chat - Windows-installer (Inno Setup 6)
;
;  Wordt gebouwd door GitHub Actions (.github/workflows/windows.yml), na PyInstaller.
;  Met de hand:  iscc /DVersie=0.1 installatie\windows\ax25chat.iss   (vanuit de hoofdmap van de repo)
;
;  Installeert per gebruiker (geen beheerdersrechten nodig) in %LOCALAPPDATA%\Programs\AX25Chat:
;    AX25Chat.exe + _internal\   het programma (Python, pywebview, de AX25Chat-code)
;    direwolf\                   Direwolf (modem, GPLv2) - github.com/wb2osz/direwolf
;    hamlib\                     rigctl/rigctld (CAT, LGPL) - github.com/Hamlib/Hamlib
;  Instellingen staan apart in %APPDATA%\AX25Chat en blijven bij bijwerken en verwijderen bewaard.
; =============================================================================

#ifndef Versie
  #define Versie "0.0-test"
#endif

[Setup]
AppId={{6E0B5D2A-7C1F-4B7E-9C2D-5A2C4A7B0001}
AppName=AX25Chat
AppVersion={#Versie}
AppVerName=AX25Chat {#Versie}
AppPublisher=PD3PAM
AppPublisherURL=https://github.com/ieddev/AX25Chat
AppSupportURL=https://github.com/ieddev/AX25Chat/blob/main/docs/PROCEDURE.md
DefaultDirName={autopf}\AX25Chat
DefaultGroupName=AX25Chat
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\uitvoer
OutputBaseFilename=AX25Chat-setup-{#Versie}
SetupIconFile=ax25chat.ico
UninstallDisplayIcon={app}\AX25Chat.exe
LicenseFile=..\..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "nl"; MessagesFile: "compiler:Languages\Dutch.isl"

[Tasks]
Name: "bureaublad"; Description: "Pictogram op het bureaublad"; GroupDescription: "Extra:"

[Files]
Source: "..\..\dist\AX25Chat\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\AX25Chat"; Filename: "{app}\AX25Chat.exe"
Name: "{group}\AX25Chat verwijderen"; Filename: "{uninstallexe}"
Name: "{autodesktop}\AX25Chat"; Filename: "{app}\AX25Chat.exe"; Tasks: bureaublad

[Run]
Filename: "{app}\AX25Chat.exe"; Description: "AX25Chat nu starten"; Flags: nowait postinstall skipifsilent
