; ============================================================
;  TodoApp インストーラー定義 (Inno Setup)
; ------------------------------------------------------------
;  これ1つを配布すれば、配布先 PC に:
;    - TodoApp 本体（Python 同梱済み / dist\TodoApp）
;    - 必要なら Microsoft Access Database Engine（Access ドライバ）
;  をまとめて導入できる。
;
;  ビルド手順:
;    1. 先に PyInstaller でビルドして dist\TodoApp\TodoApp.exe を作る
;    2. redist\AccessDatabaseEngine_X64.exe を配置（下記「準備」参照）
;    3. Inno Setup で本ファイルをコンパイル（iscc installer.iss）
;    4. 出力: Output\TodoApp_Setup.exe
;
;  準備（Access Engine 再配布パッケージ）:
;    Microsoft 公式の「Microsoft Access Database Engine 2016 再頒布可能」
;    から AccessDatabaseEngine_X64.exe を入手し、redist\ に置く。
;    （TodoApp.exe は 64bit のため 64bit 版ドライバが必要）
; ============================================================

#define MyAppName "TodoApp"
#define MyAppExeName "TodoApp.exe"
#define MyAppPublisher "TodoApp"

[Setup]
AppId={{B7E4B0F2-1C2D-4E8A-9F3B-TODOAPP000001}
AppName={#MyAppName}
AppVersion=1.0.0
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputBaseFilename=TodoApp_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; TodoApp.exe は 64bit のため、インストーラーも 64bit モードで動かす
; （レジストリも 64bit ビューで読む）
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
SetupIconFile=KeepOut\desktop.ico
PrivilegesRequired=admin

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "デスクトップにショートカットを作成する"; GroupDescription: "追加アイコン:"

[Files]
; PyInstaller の出力一式（onedir）をまるごと配置
Source: "dist\TodoApp\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Access Database Engine 再配布パッケージ（任意・存在すれば同梱）
Source: "redist\AccessDatabaseEngine_X64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Access ドライバが未導入のときだけ、サイレントで Access Engine を入れる
Filename: "{tmp}\AccessDatabaseEngine_X64.exe"; Parameters: "/quiet"; \
  StatusMsg: "Access データベースエンジンをインストールしています..."; \
  Check: NeedsAccessEngine; Flags: waituntilterminated
; インストール完了後にアプリを起動するか選べる
Filename: "{app}\{#MyAppExeName}"; Description: "TodoApp を起動する"; \
  Flags: nowait postinstall skipifsilent

[Code]
{ 64bit ビューで Access ODBC ドライバが登録済みかを調べる }
function AccessDriverInstalled(): Boolean;
begin
  Result :=
    RegKeyExists(HKLM64, 'SOFTWARE\ODBC\ODBCINST.INI\Microsoft Access Driver (*.mdb, *.accdb)') or
    RegKeyExists(HKLM64, 'SOFTWARE\Microsoft\Office\ClickToRun\REGISTRY\MACHINE\Software\Microsoft\Office\16.0\Access Connectivity Engine');
end;

{ [Run] の Check: ドライバが無いときだけ Access Engine を実行する }
function NeedsAccessEngine(): Boolean;
begin
  Result := not AccessDriverInstalled();
end;

{ 32bit 版 Office が入っていると 64bit Access Engine が入らないため事前に警告する }
function OfficeIs32Bit(): Boolean;
var
  platform: String;
begin
  Result := False;
  { ClickToRun(Office 2013以降)の Platform を確認 }
  if RegQueryStringValue(HKLM64, 'SOFTWARE\Microsoft\Office\ClickToRun\Configuration', 'Platform', platform) then
  begin
    if CompareText(platform, 'x86') = 0 then
      Result := True;
  end;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if (not AccessDriverInstalled()) and OfficeIs32Bit() then
  begin
    if MsgBox(
      'この PC には 32bit 版の Microsoft Office が検出されました。' + #13#10 +
      'TodoApp は 64bit のため 64bit 版 Access ドライバが必要ですが、' + #13#10 +
      '32bit Office と同時には導入できない場合があります。' + #13#10#13#10 +
      'このまま続行しますか？（Access ドライバの導入は手動が必要になる可能性があります）',
      mbConfirmation, MB_YESNO) = IDNO then
      Result := False;
  end;
end;
