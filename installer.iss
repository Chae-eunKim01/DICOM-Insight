[Setup]
AppId={{8DA30B13-66A4-4B31-96EC-7B5794A00D01}
AppName=DICOM Insight
AppVersion=1.0.3
AppPublisher=Chae-eunKim01
DefaultDirName={autopf}\DICOM Insight
DefaultGroupName=DICOM Insight
OutputDir=installer
OutputBaseFilename=DICOM_Insight_Setup_v1.0.3
SetupIconFile=assets\DICOM_Insight.ico
UninstallDisplayIcon={app}\DICOM Insight.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 DICOM Insight 바로가기 만들기"; GroupDescription: "추가 옵션:"

[Files]
Source: "dist\DICOM Insight.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\DICOM Insight"; Filename: "{app}\DICOM Insight.exe"
Name: "{autodesktop}\DICOM Insight"; Filename: "{app}\DICOM Insight.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\DICOM Insight.exe"; Description: "DICOM Insight 실행"; Flags: nowait postinstall skipifsilent