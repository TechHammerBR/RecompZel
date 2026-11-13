; Variante C do teste de empacotamento: instalador tradicional (Inno Setup) em vez do stub C# caseiro.
; So para o teste de deteccao do Defender em CI; nao e o instalador oficial.
#define MyAppName "RecompZel Launcher (teste C)"
#define MyAppVersion "0.0.0-test"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\RecompZel-TesteC
DisableProgramGroupPage=yes
OutputDir=..\..\out
OutputBaseFilename=C-inno-setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
SetupIconFile=..\recompzel.ico
ArchitecturesInstallIn64BitMode=x64

[Files]
Source: "..\launcher.ps1"; DestDir: "{app}"
Source: "..\build-game.ps1"; DestDir: "{app}"
Source: "..\env-recompzel.ps1"; DestDir: "{app}"
Source: "..\install-tools.ps1"; DestDir: "{app}"
Source: "..\post-install.ps1"; DestDir: "{app}"
Source: "..\criar-atalhos.ps1"; DestDir: "{app}"
Source: "..\medir-rodada.ps1"; DestDir: "{app}"
Source: "..\monitor-build.ps1"; DestDir: "{app}"
Source: "..\atualizar-fork.ps1"; DestDir: "{app}"
Source: "..\recompzel.ico"; DestDir: "{app}"

[Icons]
Name: "{autodesktop}\RecompZel Launcher"; Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File ""{app}\launcher.ps1"""; \
  WorkingDir: "{app}"; IconFilename: "{app}\recompzel.ico"
