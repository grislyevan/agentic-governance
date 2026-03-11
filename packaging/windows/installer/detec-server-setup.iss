; Detec Server - Inno Setup Installer Script
;
; UI: Full dark theme (Slate 900) with branded header and indigo accent.
; Wizard flow: Welcome > License > Pre-flight > Config > Admin >
; Summary > Installing (progress log) > Finish.
;
; Build (from repo root):
;   powershell -ExecutionPolicy Bypass -File packaging\windows\build-installer.ps1

#define AppName      "Detec Server"
#define AppVersion   "0.1.0"
#define AppPublisher "Detec"
#define AppURL       "https://github.com/grislyevan/agentic-governance"
#define DefaultPort  "8000"

[Setup]
AppId={{D3T3C-S3RV-3R01-0000-000000000001}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
DefaultDirName={autopf}\Detec\Server
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=DetecServerSetup-{#AppVersion}
UninstallDisplayIcon={app}\detec-server.exe
LicenseFile=license.txt
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
WizardImageFile=wizard-image.bmp
WizardSmallImageFile=wizard-small-image.bmp
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=yes
SetupWindowTitle=Detec Server

[Files]
Source: "..\dist\detec-server\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[UninstallRun]
Filename: "{app}\detec-server.exe"; Parameters: "stop"; Flags: runhidden waituntilterminated; RunOnceId: "StopService"
Filename: "{app}\detec-server.exe"; Parameters: "remove"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveService"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Detec Server"""; Flags: runhidden waituntilterminated; RunOnceId: "RemoveFirewall"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Detec Gateway"""; Flags: runhidden waituntilterminated; RunOnceId: "RemoveGatewayFirewall"

[UninstallDelete]
Type: files; Name: "{commondesktop}\Detec Dashboard.lnk"

[Code]
function SetEnvironmentVariable(lpName: string; lpValue: string): BOOL;
  external 'SetEnvironmentVariableW@kernel32.dll stdcall';

function GetKeyState(nVirtKey: Integer): SmallInt;
  external 'GetKeyState@user32.dll stdcall';

const
  MIN_DISK_MB = 300;
  VK_SHIFT = $10;

var
  PreflightPage: TWizardPage;
  PreflightMemo: TNewMemo;

  ConfigPage: TWizardPage;
  PortEdit: TNewEdit;
  PortLabel: TNewStaticText;
  DbSqliteRadio: TNewRadioButton;
  DbPgRadio: TNewRadioButton;
  PgUrlLabel: TNewStaticText;
  PgUrlEdit: TNewEdit;

  AdminPage: TWizardPage;
  AdminEmailLabel: TNewStaticText;
  AdminEmailEdit: TNewEdit;
  AdminPwLabel: TNewStaticText;
  AdminPwEdit: TPasswordEdit;
  AdminPwConfirmLabel: TNewStaticText;
  AdminPwConfirmEdit: TPasswordEdit;

  SummaryPage: TWizardPage;
  SummaryMemo: TNewMemo;

  LogMemo: TNewMemo;
  FinishLabel: TNewStaticText;

  PreflightPassed: Boolean;
  InstallHadErrors: Boolean;
  FinishPageCreated: Boolean;
  ChosenPort: string;

{ ── Helpers ────────────────────────────────────────────────────────── }

function RunCmd(const Filename, Params, WorkDir: string): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec(Filename, Params, WorkDir, SW_HIDE,
                 ewWaitUntilTerminated, ResultCode)
            and (ResultCode = 0);
end;

function RunCmdWithEnv(const Filename, Params, WorkDir, EnvName, EnvValue: string): Boolean;
var
  ResultCode: Integer;
begin
  SetEnvironmentVariable(EnvName, EnvValue);
  Result := Exec(Filename, Params, WorkDir, SW_HIDE,
                 ewWaitUntilTerminated, ResultCode)
            and (ResultCode = 0);
  SetEnvironmentVariable(EnvName, '');
end;

procedure LogStep(const Msg: string);
begin
  LogMemo.Lines.Add(Msg);
  LogMemo.SelStart := Length(LogMemo.Text);
  WizardForm.Refresh;
end;

function PadRight(const S: string; Len: Integer): string;
begin
  Result := S;
  while Length(Result) < Len do
    Result := Result + ' ';
end;

function GetUserPort: string;
begin
  Result := Trim(PortEdit.Text);
  if Result = '' then
    Result := '{#DefaultPort}';
end;

function GetAdminEmail: string;
begin
  Result := Trim(AdminEmailEdit.Text);
end;

function GetAdminPassword: string;
begin
  Result := AdminPwEdit.Text;
end;

function IsPostgreSQL: Boolean;
begin
  Result := DbPgRadio.Checked;
end;

procedure OnDbRadioClick(Sender: TObject);
begin
  PgUrlLabel.Visible := DbPgRadio.Checked;
  PgUrlEdit.Visible := DbPgRadio.Checked;
end;

{ ── Pre-flight checks ──────────────────────────────────────────────── }

procedure RunPreflightChecks;
var
  ResultCode: Integer;
  OutputFile, Line: string;
  Lines: TArrayOfString;
  I: Integer;
  Port: string;
  PortInUse, ServiceExists, InstallExists: Boolean;
  FreeMB, TotalMB: Cardinal;
begin
  PreflightMemo.Lines.Clear;
  PreflightPassed := True;
  Port := GetUserPort;

  PreflightMemo.Lines.Add('  Checking disk space...');
  WizardForm.Refresh;
  if GetSpaceOnDisk(ExpandConstant('{sd}'), True, FreeMB, TotalMB) then
  begin
    if FreeMB >= MIN_DISK_MB then
      PreflightMemo.Lines[PreflightMemo.Lines.Count - 1] :=
        '  [PASS]  Disk space: ' + IntToStr(FreeMB) + ' MB free'
    else
    begin
      PreflightMemo.Lines[PreflightMemo.Lines.Count - 1] :=
        '  [FAIL]  Disk space: only ' + IntToStr(FreeMB) +
        ' MB free (need ' + IntToStr(MIN_DISK_MB) + ' MB)';
      PreflightPassed := False;
    end;
  end else
    PreflightMemo.Lines[PreflightMemo.Lines.Count - 1] :=
      '  [PASS]  Disk space: could not determine (continuing)';

  PreflightMemo.Lines.Add('  Checking port ' + Port + '...');
  WizardForm.Refresh;
  PortInUse := False;
  OutputFile := ExpandConstant('{tmp}\netstat-check.txt');
  if Exec('powershell.exe',
          '-NoProfile -Command "if (Get-NetTCPConnection -LocalPort ' + Port +
          ' -State Listen -ErrorAction SilentlyContinue) { ''IN_USE'' | Out-File -Encoding ascii ''' +
          OutputFile + ''' } else { ''FREE'' | Out-File -Encoding ascii ''' + OutputFile + ''' }"',
          '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if LoadStringsFromFile(OutputFile, Lines) then
      for I := 0 to GetArrayLength(Lines) - 1 do
      begin
        Line := Lines[I];
        if Pos('IN_USE', Line) > 0 then
        begin
          PortInUse := True;
          Break;
        end;
      end;
  end;

  if PortInUse then
  begin
    PreflightMemo.Lines[PreflightMemo.Lines.Count - 1] :=
      '  [FAIL]  Port ' + Port + ' is already in use';
    PreflightPassed := False;
  end else
    PreflightMemo.Lines[PreflightMemo.Lines.Count - 1] :=
      '  [PASS]  Port ' + Port + ' is available';

  PreflightMemo.Lines.Add('  Checking for existing service...');
  WizardForm.Refresh;
  ServiceExists := False;
  if Exec(ExpandConstant('{sys}\sc.exe'), 'query DetecServer',
          '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    ServiceExists := (ResultCode = 0);

  if ServiceExists then
    PreflightMemo.Lines[PreflightMemo.Lines.Count - 1] :=
      '  [WARN]  Detec Server service exists (will be upgraded)'
  else
    PreflightMemo.Lines[PreflightMemo.Lines.Count - 1] :=
      '  [PASS]  No existing service found';

  PreflightMemo.Lines.Add('  Checking for previous installation...');
  WizardForm.Refresh;
  InstallExists := FileExists(ExpandConstant('{autopf}\Detec\Server\detec-server.exe'));

  if InstallExists then
    PreflightMemo.Lines[PreflightMemo.Lines.Count - 1] :=
      '  [WARN]  Previous installation found (will be overwritten)'
  else
    PreflightMemo.Lines[PreflightMemo.Lines.Count - 1] :=
      '  [PASS]  No previous installation found';

  PreflightMemo.Lines.Add('');
  if PreflightPassed then
    PreflightMemo.Lines.Add('  All clear. Ready when you are.')
  else
    PreflightMemo.Lines.Add('  A few things need attention before we continue.');

  WizardForm.Refresh;
end;

{ ── InitializeWizard ───────────────────────────────────────────────── }

procedure InitializeWizard;
var
  DbHeaderLabel: TNewStaticText;
  AccentBar: TPanel;
begin
  PreflightPassed := True;
  FinishPageCreated := False;
  ChosenPort := '{#DefaultPort}';

  { ── Dark theme: Slate 900 (#0f172a) everywhere ──────────────────── }
  WizardForm.Color := $002A170F;
  WizardForm.MainPanel.Color := $002A170F;
  WizardForm.InnerPage.Color := $002A170F;
  WizardForm.Bevel.Visible := False;
  WizardForm.Bevel1.Visible := False;

  { Header typography }
  WizardForm.PageNameLabel.Font.Name := 'Segoe UI';
  WizardForm.PageNameLabel.Font.Size := 12;
  WizardForm.PageNameLabel.Font.Color := $00F9F5F1;
  WizardForm.PageDescriptionLabel.Font.Name := 'Segoe UI';
  WizardForm.PageDescriptionLabel.Font.Color := $00B8A394;

  { License page }
  WizardForm.LicenseMemo.Color := $002A170F;
  WizardForm.LicenseMemo.Font.Color := $00B8A394;
  WizardForm.LicenseAcceptedRadio.Font.Color := $00F9F5F1;
  WizardForm.LicenseNotAcceptedRadio.Font.Color := $00F9F5F1;
  WizardForm.LicenseLabel1.Font.Color := $00F9F5F1;

  { Finish page labels (styled before controls are added in CurPageChanged) }
  WizardForm.FinishedHeadingLabel.Font.Color := $00F9F5F1;
  WizardForm.FinishedLabel.Font.Color := $00B8A394;

  { Indigo accent bar at the bottom of the header panel }
  AccentBar := TPanel.Create(WizardForm);
  AccentBar.Parent := WizardForm.MainPanel;
  AccentBar.SetBounds(
    0, WizardForm.MainPanel.ClientHeight - ScaleY(2),
    WizardForm.MainPanel.ClientWidth, ScaleY(2));
  AccentBar.Color := $00F16663;
  AccentBar.BevelOuter := bvNone;

  { ── Pre-flight Checks page (after License) ─────────────────────── }
  PreflightPage := CreateCustomPage(wpLicense,
    'Pre-flight Checks',
    'Checking that everything is in order.');

  PreflightMemo := TNewMemo.Create(PreflightPage);
  PreflightMemo.Parent := PreflightPage.Surface;
  PreflightMemo.SetBounds(0, 0,
    PreflightPage.SurfaceWidth,
    PreflightPage.SurfaceHeight - ScaleY(4));
  PreflightMemo.ReadOnly := True;
  PreflightMemo.ScrollBars := ssVertical;
  PreflightMemo.Font.Name := 'Consolas';
  PreflightMemo.Font.Size := 10;
  PreflightMemo.Color := $002A170F;
  PreflightMemo.Font.Color := $00F9F5F1;

  { ── Server Configuration page (after Preflight) ────────────────── }
  ConfigPage := CreateCustomPage(PreflightPage.ID,
    'Server Configuration',
    'Choose your port and database. Sensible defaults are pre-filled.');

  PortLabel := TNewStaticText.Create(ConfigPage);
  PortLabel.Parent := ConfigPage.Surface;
  PortLabel.Caption := 'Server port:';
  PortLabel.SetBounds(0, ScaleY(8), ScaleX(100), ScaleY(18));
  PortLabel.Font.Color := $00F9F5F1;

  PortEdit := TNewEdit.Create(ConfigPage);
  PortEdit.Parent := ConfigPage.Surface;
  PortEdit.Text := '{#DefaultPort}';
  PortEdit.SetBounds(ScaleX(110), ScaleY(5), ScaleX(80), ScaleY(22));
  PortEdit.Color := $003B291E;
  PortEdit.Font.Color := $00F9F5F1;

  DbHeaderLabel := TNewStaticText.Create(ConfigPage);
  DbHeaderLabel.Parent := ConfigPage.Surface;
  DbHeaderLabel.Caption := 'Database:';
  DbHeaderLabel.SetBounds(0, ScaleY(40), ScaleX(100), ScaleY(18));
  DbHeaderLabel.Font.Color := $00F9F5F1;

  DbSqliteRadio := TNewRadioButton.Create(ConfigPage);
  DbSqliteRadio.Parent := ConfigPage.Surface;
  DbSqliteRadio.Caption := 'SQLite (recommended for 1-10 endpoints, zero configuration)';
  DbSqliteRadio.Checked := True;
  DbSqliteRadio.SetBounds(ScaleX(12), ScaleY(60), ConfigPage.SurfaceWidth - ScaleX(12), ScaleY(20));
  DbSqliteRadio.OnClick := @OnDbRadioClick;
  DbSqliteRadio.Font.Color := $00F9F5F1;

  DbPgRadio := TNewRadioButton.Create(ConfigPage);
  DbPgRadio.Parent := ConfigPage.Surface;
  DbPgRadio.Caption := 'PostgreSQL (recommended for 10+ endpoints)';
  DbPgRadio.SetBounds(ScaleX(12), ScaleY(84), ConfigPage.SurfaceWidth - ScaleX(12), ScaleY(20));
  DbPgRadio.OnClick := @OnDbRadioClick;
  DbPgRadio.Font.Color := $00F9F5F1;

  PgUrlLabel := TNewStaticText.Create(ConfigPage);
  PgUrlLabel.Parent := ConfigPage.Surface;
  PgUrlLabel.Caption := 'Connection URL:';
  PgUrlLabel.SetBounds(ScaleX(28), ScaleY(112), ScaleX(110), ScaleY(18));
  PgUrlLabel.Visible := False;
  PgUrlLabel.Font.Color := $00F9F5F1;

  PgUrlEdit := TNewEdit.Create(ConfigPage);
  PgUrlEdit.Parent := ConfigPage.Surface;
  PgUrlEdit.Text := 'postgresql://user:pass@localhost:5432/detec';
  PgUrlEdit.SetBounds(ScaleX(140), ScaleY(109),
    ConfigPage.SurfaceWidth - ScaleX(144), ScaleY(22));
  PgUrlEdit.Visible := False;
  PgUrlEdit.Color := $003B291E;
  PgUrlEdit.Font.Color := $00F9F5F1;

  { ── Admin Account page (after Config) ──────────────────────────── }
  AdminPage := CreateCustomPage(ConfigPage.ID,
    'Administrator Account',
    'Set up your first admin account for the dashboard.');

  AdminEmailLabel := TNewStaticText.Create(AdminPage);
  AdminEmailLabel.Parent := AdminPage.Surface;
  AdminEmailLabel.Caption := 'Email address:';
  AdminEmailLabel.SetBounds(0, ScaleY(8), ScaleX(120), ScaleY(18));
  AdminEmailLabel.Font.Color := $00F9F5F1;

  AdminEmailEdit := TNewEdit.Create(AdminPage);
  AdminEmailEdit.Parent := AdminPage.Surface;
  AdminEmailEdit.Text := '';
  AdminEmailEdit.SetBounds(ScaleX(130), ScaleY(5),
    AdminPage.SurfaceWidth - ScaleX(134), ScaleY(22));
  AdminEmailEdit.Color := $003B291E;
  AdminEmailEdit.Font.Color := $00F9F5F1;

  AdminPwLabel := TNewStaticText.Create(AdminPage);
  AdminPwLabel.Parent := AdminPage.Surface;
  AdminPwLabel.Caption := 'Password:';
  AdminPwLabel.SetBounds(0, ScaleY(42), ScaleX(120), ScaleY(18));
  AdminPwLabel.Font.Color := $00F9F5F1;

  AdminPwEdit := TPasswordEdit.Create(AdminPage);
  AdminPwEdit.Parent := AdminPage.Surface;
  AdminPwEdit.Text := '';
  AdminPwEdit.SetBounds(ScaleX(130), ScaleY(39),
    AdminPage.SurfaceWidth - ScaleX(134), ScaleY(22));
  AdminPwEdit.Color := $003B291E;
  AdminPwEdit.Font.Color := $00F9F5F1;

  AdminPwConfirmLabel := TNewStaticText.Create(AdminPage);
  AdminPwConfirmLabel.Parent := AdminPage.Surface;
  AdminPwConfirmLabel.Caption := 'Confirm password:';
  AdminPwConfirmLabel.SetBounds(0, ScaleY(76), ScaleX(120), ScaleY(18));
  AdminPwConfirmLabel.Font.Color := $00F9F5F1;

  AdminPwConfirmEdit := TPasswordEdit.Create(AdminPage);
  AdminPwConfirmEdit.Parent := AdminPage.Surface;
  AdminPwConfirmEdit.Text := '';
  AdminPwConfirmEdit.SetBounds(ScaleX(130), ScaleY(73),
    AdminPage.SurfaceWidth - ScaleX(134), ScaleY(22));
  AdminPwConfirmEdit.Color := $003B291E;
  AdminPwConfirmEdit.Font.Color := $00F9F5F1;

  { ── Summary page (after Admin, before Ready) ───────────────────── }
  SummaryPage := CreateCustomPage(AdminPage.ID,
    'Installation Summary',
    'One last look before we get started.');

  SummaryMemo := TNewMemo.Create(SummaryPage);
  SummaryMemo.Parent := SummaryPage.Surface;
  SummaryMemo.SetBounds(0, 0,
    SummaryPage.SurfaceWidth,
    SummaryPage.SurfaceHeight - ScaleY(4));
  SummaryMemo.ReadOnly := True;
  SummaryMemo.ScrollBars := ssVertical;
  SummaryMemo.Font.Name := 'Consolas';
  SummaryMemo.Font.Size := 10;
  SummaryMemo.Color := $002A170F;
  SummaryMemo.Font.Color := $00F9F5F1;

  { ── Progress log (overlays the Installing page entirely) ────────── }
  LogMemo := TNewMemo.Create(WizardForm);
  LogMemo.Parent := WizardForm.InnerPage;
  LogMemo.SetBounds(
    WizardForm.StatusLabel.Left,
    WizardForm.StatusLabel.Top,
    WizardForm.StatusLabel.Width,
    WizardForm.InnerPage.ClientHeight - WizardForm.StatusLabel.Top - ScaleY(4)
  );
  LogMemo.ReadOnly := True;
  LogMemo.ScrollBars := ssVertical;
  LogMemo.Font.Name := 'Consolas';
  LogMemo.Font.Size := 10;
  LogMemo.Color := $002A170F;
  LogMemo.Font.Color := $00F9F5F1;
  LogMemo.Visible := False;
end;

{ ── Helpers: keyboard state ─────────────────────────────────────────── }

function IsShiftDown: Boolean;
begin
  Result := (GetKeyState(VK_SHIFT) < 0);
end;

{ ── Open dashboard helper (must precede CurPageChanged) ────────────── }

procedure OpenDashboard(Sender: TObject);
var
  ErrorCode: Integer;
begin
  if IsShiftDown then
    ShellExec('open', 'notepad.exe',
      ExpandConstant('{sd}\ProgramData\Detec\server.log'),
      '', SW_SHOW, ewNoWait, ErrorCode)
  else
    ShellExec('open', 'http://localhost:' + ChosenPort,
      '', '', SW_SHOW, ewNoWait, ErrorCode);
end;

{ ── Page navigation logic ──────────────────────────────────────────── }

procedure CurPageChanged(CurPageID: Integer);
var
  Btn: TNewButton;
  Port, DbDesc, PwMask: string;
begin
  if CurPageID = wpInstalling then
  begin
    WizardForm.PageNameLabel.Caption := 'Detec Server';
    WizardForm.PageDescriptionLabel.Caption := 'v{#AppVersion}';
    LogMemo.Visible := True;
    WizardForm.ProgressGauge.Visible := False;
    WizardForm.StatusLabel.Visible := False;
  end else
    LogMemo.Visible := False;

  if CurPageID = PreflightPage.ID then
    RunPreflightChecks;

  // Populate Summary page
  if CurPageID = SummaryPage.ID then
  begin
    Port := GetUserPort;
    if IsPostgreSQL then
      DbDesc := 'PostgreSQL'
    else
      DbDesc := 'SQLite (C:\ProgramData\Detec\detec.db)';
    PwMask := StringOfChar('*', Length(GetAdminPassword));

    SummaryMemo.Lines.Clear;
    SummaryMemo.Lines.Add('');
    SummaryMemo.Lines.Add('  Install directory:');
    SummaryMemo.Lines.Add('    ' + ExpandConstant('{autopf}\Detec\Server'));
    SummaryMemo.Lines.Add('');
    SummaryMemo.Lines.Add('  Server port:  ' + Port);
    SummaryMemo.Lines.Add('  Database:     ' + DbDesc);
    SummaryMemo.Lines.Add('');
    SummaryMemo.Lines.Add('  Admin email:  ' + GetAdminEmail);
    SummaryMemo.Lines.Add('  Admin pass:   ' + PwMask);
    SummaryMemo.Lines.Add('');
    SummaryMemo.Lines.Add('  After extraction the installer will:');
    SummaryMemo.Lines.Add('    - Generate configuration and admin account');
    SummaryMemo.Lines.Add('    - Install and start the Windows Service');
    SummaryMemo.Lines.Add('    - Configure Windows Firewall (TCP ' + Port + ')');
    SummaryMemo.Lines.Add('    - Create a desktop shortcut');
    SummaryMemo.Lines.Add('    - Verify the dashboard is responding');
  end;

  if (CurPageID = wpFinished) and (not FinishPageCreated) then
  begin
    FinishPageCreated := True;

    WizardForm.PageNameLabel.Caption := 'Detec Server';
    WizardForm.PageDescriptionLabel.Caption := 'Installation complete';

    FinishLabel := TNewStaticText.Create(WizardForm);
    FinishLabel.Parent := WizardForm.FinishedPage;
    FinishLabel.AutoSize := False;
    FinishLabel.WordWrap := True;
    FinishLabel.Font.Color := $00F9F5F1;
    FinishLabel.SetBounds(
      ScaleX(0),
      WizardForm.FinishedLabel.Top + WizardForm.FinishedLabel.Height + ScaleY(12),
      WizardForm.FinishedPage.Width, ScaleY(50)
    );

    if InstallHadErrors then
      FinishLabel.Caption :=
        'Installation completed with warnings. Check C:\ProgramData\Detec\server.log for details.'
    else
      FinishLabel.Caption :=
        'Detec Server is running on port ' + ChosenPort +
        '. Sign in with ' + GetAdminEmail + ' to get started.' + #13#10 +
        'Next step: deploy agents from Settings > Download Agent.';

    Btn := TNewButton.Create(WizardForm);
    Btn.Parent := WizardForm.FinishedPage;
    Btn.Caption := 'Open Detec Dashboard';
    Btn.SetBounds(
      ScaleX(0),
      FinishLabel.Top + FinishLabel.Height + ScaleY(8),
      ScaleX(180), ScaleY(30)
    );
    Btn.OnClick := @OpenDashboard;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;

  if CurPageID = PreflightPage.ID then
  begin
    if not PreflightPassed then
    begin
      MsgBox('Some pre-flight checks need attention first.', mbError, MB_OK);
      Result := False;
    end;
  end;

  if CurPageID = ConfigPage.ID then
  begin
    if (StrToIntDef(GetUserPort, 0) < 1) or (StrToIntDef(GetUserPort, 0) > 65535) then
    begin
      MsgBox('That port number doesn''t look right. Enter a value between 1 and 65535.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if IsPostgreSQL and (Trim(PgUrlEdit.Text) = '') then
    begin
      MsgBox('Please enter a PostgreSQL connection URL so we can connect.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    ChosenPort := GetUserPort;
  end;

  if CurPageID = AdminPage.ID then
  begin
    if GetAdminEmail = '' then
    begin
      MsgBox('We need an email address to create your admin account.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if Pos('@', GetAdminEmail) = 0 then
    begin
      MsgBox('That email looks incomplete. Make sure it includes an @.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if Length(GetAdminPassword) < 8 then
    begin
      MsgBox('Password needs at least 8 characters.', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if GetAdminPassword <> AdminPwConfirmEdit.Text then
    begin
      MsgBox('Those passwords don''t match. Try again?', mbError, MB_OK);
      Result := False;
      Exit;
    end;
  end;
end;

{ ── Skip the built-in Ready page (we use our own Summary page) ───── }

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID = wpReady);
end;

{ ── Pre-install: stop running service to avoid locked files ────────── }

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Result := '';
  if Exec(ExpandConstant('{sys}\sc.exe'), 'query DetecServer',
          '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if ResultCode = 0 then
    begin
      Exec(ExpandConstant('{sys}\sc.exe'), 'stop DetecServer',
           '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
      Sleep(2000);
    end;
  end;
end;

{ ── Post-install actions ───────────────────────────────────────────── }

procedure CurStepChanged(CurStep: TSetupStep);
var
  AppDir, Port, SetupArgs, DbLabel, ShortcutFile, AdminEmail: string;
  WshShell: Variant;
  Shortcut: Variant;
  HealthAttempt: Integer;
  HealthOK: Boolean;
  OutputFile, Line: string;
  Lines: TArrayOfString;
  I: Integer;
  LogPath: string;
begin
  if CurStep <> ssPostInstall then
    Exit;

  AppDir := ExpandConstant('{app}');
  Port := ChosenPort;
  AdminEmail := GetAdminEmail;
  InstallHadErrors := False;

  LogStep('  Detec Server v{#AppVersion}');
  LogStep('');

  LogStep('  ' + PadRight('Extracting files', 40) + 'done');

  LogStep('  Generating configuration...');
  SetupArgs := 'setup --force --admin-email "' + AdminEmail +
               '" --port ' + Port;
  if IsPostgreSQL then
    SetupArgs := SetupArgs + ' --database-url "' + Trim(PgUrlEdit.Text) + '"';
  if RunCmdWithEnv(AppDir + '\detec-server.exe', SetupArgs, AppDir,
                   'DETEC_ADMIN_PASSWORD', GetAdminPassword) then
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  ' + PadRight('Generating configuration', 40) + 'done'
  else begin
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  ' + PadRight('Generating configuration', 40) + 'FAIL';
    InstallHadErrors := True;
    LogStep('');
    LogStep('  Setup failed. Files extracted to ' + AppDir);
    LogStep('  Re-run: detec-server.exe setup --admin-email ' + AdminEmail);
    WizardForm.Refresh;
    Exit;
  end;
  WizardForm.Refresh;

  LogStep('  Installing Windows Service...');
  if RunCmd(AppDir + '\detec-server.exe', 'install', AppDir) then
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  ' + PadRight('Installing Windows Service', 40) + 'done'
  else begin
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  ' + PadRight('Installing Windows Service', 40) + 'FAIL';
    InstallHadErrors := True;
  end;
  WizardForm.Refresh;

  LogStep('  Starting server...');
  if RunCmd(AppDir + '\detec-server.exe', 'start', AppDir) then
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  ' + PadRight('Starting server', 40) + 'done'
  else begin
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  ' + PadRight('Starting server', 40) + 'FAIL';
    InstallHadErrors := True;
  end;
  WizardForm.Refresh;

  LogStep('  Configuring firewall...');
  if RunCmd(ExpandConstant('{sys}\netsh.exe'),
         'advfirewall firewall add rule name="Detec Server" ' +
         'dir=in action=allow protocol=TCP localport=' + Port, '') then
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  ' + PadRight('Configuring firewall', 40) + 'done'
  else
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  ' + PadRight('Configuring firewall', 40) + 'skipped';
  RunCmd(ExpandConstant('{sys}\netsh.exe'),
         'advfirewall firewall add rule name="Detec Gateway" ' +
         'dir=in action=allow protocol=TCP localport=8001', '');
  WizardForm.Refresh;

  try
    ShortcutFile := ExpandConstant('{commondesktop}\Detec Dashboard.lnk');
    WshShell := CreateOleObject('WScript.Shell');
    Shortcut := WshShell.CreateShortcut(ShortcutFile);
    Shortcut.TargetPath := 'http://localhost:' + Port;
    Shortcut.Description := 'Open the Detec governance dashboard';
    Shortcut.IconLocation := AppDir + '\detec-server.exe,0';
    Shortcut.Save;
  except
  end;

  LogStep('  Verifying dashboard...');
  HealthOK := False;
  OutputFile := ExpandConstant('{tmp}\health-check.txt');
  for HealthAttempt := 1 to 15 do
  begin
    if FileExists(OutputFile) then
      DeleteFile(OutputFile);
    Exec('powershell.exe',
      '-NoProfile -Command "try { $r = Invoke-WebRequest -Uri ''http://localhost:' +
      Port + '/docs'' -UseBasicParsing -TimeoutSec 2; ' +
      'if ($r.StatusCode -eq 200) { ''OK'' | Out-File -Encoding ascii ''' +
      OutputFile + ''' } } catch {}"',
      '', SW_HIDE, ewWaitUntilTerminated, I);
    if LoadStringsFromFile(OutputFile, Lines) then
      for I := 0 to GetArrayLength(Lines) - 1 do
      begin
        Line := Lines[I];
        if Pos('OK', Line) > 0 then
        begin
          HealthOK := True;
          Break;
        end;
      end;
    if HealthOK then
      Break;
    Sleep(1000);
  end;

  if HealthOK then
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  ' + PadRight('Verifying dashboard', 40) + 'done'
  else begin
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  ' + PadRight('Verifying dashboard', 40) + 'warning';
    LogStep('  Check C:\ProgramData\Detec\server.log');
    InstallHadErrors := True;
  end;
  WizardForm.Refresh;

  if IsPostgreSQL then
    DbLabel := 'PostgreSQL'
  else
    DbLabel := 'SQLite';

  LogStep('');
  if InstallHadErrors then
    LogStep('  Completed with warnings.')
  else
    LogStep('  Server is up. Dashboard: http://localhost:' + Port);

  LogStep('');
  LogStep('  ' + PadRight('Sign in', 12) + AdminEmail);
  LogStep('  ' + PadRight('Database', 12) + DbLabel);
  LogStep('  ' + PadRight('Config', 12) + 'C:\ProgramData\Detec\server.env');

  LogPath := ExpandConstant('{sd}\ProgramData\Detec\install.log');
  ForceDirectories(ExtractFilePath(LogPath));
  SetArrayLength(Lines, LogMemo.Lines.Count);
  for I := 0 to LogMemo.Lines.Count - 1 do
    Lines[I] := LogMemo.Lines[I];
  SaveStringsToFile(LogPath, Lines, False);
  LogStep('');
  LogStep('  ' + PadRight('Log', 12) + LogPath);
end;

{ ── Uninstall: offer to remove data directory ──────────────────────── }

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: string;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{sd}\ProgramData\Detec');
    if DirExists(DataDir) then
    begin
      if MsgBox(
        'Do you also want to remove the Detec data directory?' + #13#10 + #13#10 +
        'This will permanently delete:' + #13#10 +
        '  - Database (detec.db)' + #13#10 +
        '  - Configuration (server.env)' + #13#10 +
        '  - Server logs (server.log)' + #13#10 + #13#10 +
        'Location: ' + DataDir,
        mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      begin
        DelTree(DataDir, True, True, True);
      end;
    end;
  end;
end;
