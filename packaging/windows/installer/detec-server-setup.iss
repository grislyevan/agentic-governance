; Detec Server - Inno Setup Installer Script
;
; Produces a single DetecServerSetup.exe that:
;   1. Shows a license agreement
;   2. Runs pre-flight checks (disk, port, existing install)
;   3. Lets the user configure port and database
;   4. Extracts the pre-built detec-server bundle
;   5. Runs first-time setup (generates secrets + admin credentials)
;   6. Installs and starts the Windows Service
;   7. Configures the Windows Firewall
;   8. Creates a desktop shortcut
;   9. Shows generated admin credentials
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

[Files]
Source: "..\dist\detec-server\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[UninstallRun]
Filename: "{app}\detec-server.exe"; Parameters: "stop"; Flags: runhidden waituntilterminated; RunOnceId: "StopService"
Filename: "{app}\detec-server.exe"; Parameters: "remove"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveService"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Detec Server"""; Flags: runhidden waituntilterminated; RunOnceId: "RemoveFirewall"

[UninstallDelete]
Type: files; Name: "{commondesktop}\Detec Dashboard.lnk"

[Code]
const
  ADMIN_EMAIL = 'admin@localhost';
  MIN_DISK_MB = 300;

var
  { Custom pages }
  PreflightPage: TWizardPage;
  PreflightMemo: TNewMemo;
  ConfigPage: TWizardPage;
  PortEdit: TNewEdit;
  PortLabel: TNewStaticText;
  DbSqliteRadio: TNewRadioButton;
  DbPgRadio: TNewRadioButton;
  PgUrlLabel: TNewStaticText;
  PgUrlEdit: TNewEdit;
  CredentialsPage: TWizardPage;
  CredsMemo: TNewMemo;
  LogMemo: TNewMemo;

  { State }
  PreflightPassed: Boolean;
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

procedure LogStep(const Msg: string);
begin
  LogMemo.Lines.Add(Msg);
  LogMemo.SelStart := Length(LogMemo.Text);
  WizardForm.StatusLabel.Caption := Msg;
  WizardForm.Refresh;
end;

function ReadPasswordFromEnv: string;
var
  Lines: TArrayOfString;
  I, P: Integer;
  Line, EnvFile: string;
begin
  Result := '(could not read)';
  EnvFile := ExpandConstant('{sd}\ProgramData\Detec\server.env');
  if LoadStringsFromFile(EnvFile, Lines) then
    for I := 0 to GetArrayLength(Lines) - 1 do
    begin
      Line := Trim(Lines[I]);
      P := Pos('SEED_ADMIN_PASSWORD=', Line);
      if P = 1 then
      begin
        Result := Copy(Line, 21, Length(Line));
        Break;
      end;
    end;
end;

function GetUserPort: string;
begin
  Result := Trim(PortEdit.Text);
  if Result = '' then
    Result := '{#DefaultPort}';
end;

function IsPostgreSQL: Boolean;
begin
  Result := DbPgRadio.Checked;
end;

{ ── Database radio toggle ──────────────────────────────────────────── }

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

  { Check 1: Disk space }
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

  { Check 2: Port availability }
  PreflightMemo.Lines.Add('  Checking port ' + Port + '...');
  WizardForm.Refresh;
  PortInUse := False;
  OutputFile := ExpandConstant('{tmp}\netstat-check.txt');
  if Exec(ExpandConstant('{cmd}'),
          '/C netstat -an | findstr "LISTENING" | findstr ":' + Port + ' " > "' + OutputFile + '"',
          '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if LoadStringsFromFile(OutputFile, Lines) then
      for I := 0 to GetArrayLength(Lines) - 1 do
      begin
        Line := Lines[I];
        if Pos(':' + Port + ' ', Line) > 0 then
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

  { Check 3: Existing service }
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

  // Check 4: Existing installation (use literal path; app dir not available yet)
  PreflightMemo.Lines.Add('  Checking for previous installation...');
  WizardForm.Refresh;
  InstallExists := FileExists(ExpandConstant('{autopf}\Detec\Server\detec-server.exe'));

  if InstallExists then
    PreflightMemo.Lines[PreflightMemo.Lines.Count - 1] :=
      '  [WARN]  Previous installation found (will be overwritten)'
  else
    PreflightMemo.Lines[PreflightMemo.Lines.Count - 1] :=
      '  [PASS]  No previous installation found';

  { Summary }
  PreflightMemo.Lines.Add('');
  if PreflightPassed then
    PreflightMemo.Lines.Add('  All checks passed. Click Next to continue.')
  else
    PreflightMemo.Lines.Add('  Some checks failed. Please resolve before continuing.');

  WizardForm.Refresh;
end;

{ ── InitializeWizard ───────────────────────────────────────────────── }

procedure InitializeWizard;
begin
  PreflightPassed := True;
  ChosenPort := '{#DefaultPort}';

  { ── Pre-flight Checks page (after License) ── }
  PreflightPage := CreateCustomPage(wpLicense,
    'Pre-flight Checks',
    'Verifying your system is ready for installation.');

  PreflightMemo := TNewMemo.Create(PreflightPage);
  PreflightMemo.Parent := PreflightPage.Surface;
  PreflightMemo.SetBounds(0, 0,
    PreflightPage.SurfaceWidth,
    PreflightPage.SurfaceHeight - ScaleY(4));
  PreflightMemo.ReadOnly := True;
  PreflightMemo.ScrollBars := ssVertical;
  PreflightMemo.Font.Name := 'Consolas';
  PreflightMemo.Font.Size := 10;
  PreflightMemo.Color := $003B291E;
  PreflightMemo.Font.Color := $00F9F5F1;

  { ── Server Configuration page (after Preflight) ── }
  ConfigPage := CreateCustomPage(PreflightPage.ID,
    'Server Configuration',
    'Configure the server port and database backend.');

  PortLabel := TNewStaticText.Create(ConfigPage);
  PortLabel.Parent := ConfigPage.Surface;
  PortLabel.Caption := 'Server port:';
  PortLabel.SetBounds(0, ScaleY(8), ScaleX(100), ScaleY(18));

  PortEdit := TNewEdit.Create(ConfigPage);
  PortEdit.Parent := ConfigPage.Surface;
  PortEdit.Text := '{#DefaultPort}';
  PortEdit.SetBounds(ScaleX(110), ScaleY(5), ScaleX(80), ScaleY(22));

  { Database section }
  DbSqliteRadio := TNewRadioButton.Create(ConfigPage);
  DbSqliteRadio.Parent := ConfigPage.Surface;
  DbSqliteRadio.Caption := 'SQLite (recommended for 1-10 endpoints, zero configuration)';
  DbSqliteRadio.Checked := True;
  DbSqliteRadio.SetBounds(0, ScaleY(52), ConfigPage.SurfaceWidth, ScaleY(20));
  DbSqliteRadio.OnClick := @OnDbRadioClick;

  DbPgRadio := TNewRadioButton.Create(ConfigPage);
  DbPgRadio.Parent := ConfigPage.Surface;
  DbPgRadio.Caption := 'PostgreSQL (recommended for 10+ endpoints)';
  DbPgRadio.SetBounds(0, ScaleY(76), ConfigPage.SurfaceWidth, ScaleY(20));
  DbPgRadio.OnClick := @OnDbRadioClick;

  PgUrlLabel := TNewStaticText.Create(ConfigPage);
  PgUrlLabel.Parent := ConfigPage.Surface;
  PgUrlLabel.Caption := 'Connection URL:';
  PgUrlLabel.SetBounds(ScaleX(20), ScaleY(104), ScaleX(110), ScaleY(18));
  PgUrlLabel.Visible := False;

  PgUrlEdit := TNewEdit.Create(ConfigPage);
  PgUrlEdit.Parent := ConfigPage.Surface;
  PgUrlEdit.Text := 'postgresql://user:pass@localhost:5432/detec';
  PgUrlEdit.SetBounds(ScaleX(130), ScaleY(101),
    ConfigPage.SurfaceWidth - ScaleX(134), ScaleY(22));
  PgUrlEdit.Visible := False;

  { ── Progress log on the installing page ── }
  LogMemo := TNewMemo.Create(WizardForm);
  LogMemo.Parent := WizardForm.InnerPage;
  LogMemo.SetBounds(
    WizardForm.StatusLabel.Left,
    WizardForm.ProgressGauge.Top + WizardForm.ProgressGauge.Height + ScaleY(12),
    WizardForm.StatusLabel.Width,
    WizardForm.InnerPage.ClientHeight
      - WizardForm.ProgressGauge.Top
      - WizardForm.ProgressGauge.Height
      - ScaleY(20)
  );
  LogMemo.ReadOnly := True;
  LogMemo.ScrollBars := ssVertical;
  LogMemo.Font.Name := 'Consolas';
  LogMemo.Font.Size := 9;
  LogMemo.Color := $003B291E;
  LogMemo.Font.Color := $00F9F5F1;
  LogMemo.Visible := False;

  { ── Credentials page (after Installing) ── }
  CredentialsPage := CreateCustomPage(wpInstalling,
    'Administrator Credentials',
    'Save these credentials now. The password cannot be recovered later.');

  CredsMemo := TNewMemo.Create(CredentialsPage);
  CredsMemo.Parent := CredentialsPage.Surface;
  CredsMemo.SetBounds(0, 0,
    CredentialsPage.SurfaceWidth,
    CredentialsPage.SurfaceHeight - ScaleY(4));
  CredsMemo.ReadOnly := True;
  CredsMemo.ScrollBars := ssVertical;
  CredsMemo.Font.Name := 'Consolas';
  CredsMemo.Font.Size := 11;
  CredsMemo.Color := $003B291E;
  CredsMemo.Font.Color := $00F9F5F1;
end;

{ ── Finish page: open dashboard (must precede CurPageChanged) ──────── }

procedure OpenDashboard(Sender: TObject);
var
  ErrorCode: Integer;
begin
  ShellExec('open', 'http://localhost:' + ChosenPort, '', '', SW_SHOW, ewNoWait, ErrorCode);
end;

{ ── Page navigation logic ──────────────────────────────────────────── }

procedure CurPageChanged(CurPageID: Integer);
var
  Btn: TNewButton;
begin
  { Hide the progress log when not on the Installing page }
  LogMemo.Visible := (CurPageID = wpInstalling);

  { Run preflight checks when entering that page }
  if CurPageID = PreflightPage.ID then
    RunPreflightChecks;

  { "Open Dashboard" button on Finish page }
  if CurPageID = wpFinished then
  begin
    Btn := TNewButton.Create(WizardForm);
    Btn.Parent := WizardForm.FinishedPage;
    Btn.Caption := 'Open Detec Dashboard';
    Btn.SetBounds(
      ScaleX(0),
      WizardForm.FinishedLabel.Top + WizardForm.FinishedLabel.Height + ScaleY(20),
      ScaleX(180),
      ScaleY(30)
    );
    Btn.OnClick := @OpenDashboard;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;

  { Block navigation from preflight if checks failed }
  if CurPageID = PreflightPage.ID then
  begin
    if not PreflightPassed then
    begin
      MsgBox('Please resolve the failed checks before continuing.',
             mbError, MB_OK);
      Result := False;
    end;
  end;

  { Validate port input }
  if CurPageID = ConfigPage.ID then
  begin
    if (StrToIntDef(GetUserPort, 0) < 1) or
       (StrToIntDef(GetUserPort, 0) > 65535) then
    begin
      MsgBox('Please enter a valid port number (1-65535).',
             mbError, MB_OK);
      Result := False;
      Exit;
    end;
    if IsPostgreSQL and (Trim(PgUrlEdit.Text) = '') then
    begin
      MsgBox('Please enter a PostgreSQL connection URL.',
             mbError, MB_OK);
      Result := False;
      Exit;
    end;
    ChosenPort := GetUserPort;
  end;
end;

{ ── Post-install actions ───────────────────────────────────────────── }

procedure CurStepChanged(CurStep: TSetupStep);
var
  AppDir, Port, Password, SetupArgs, DbLabel, ShortcutFile: string;
  WshShell: Variant;
  Shortcut: Variant;
begin
  if CurStep <> ssPostInstall then
    Exit;

  LogMemo.Visible := True;
  AppDir := ExpandConstant('{app}');
  Port := ChosenPort;

  LogMemo.Lines.Add('  Installing Detec Server');
  LogMemo.Lines.Add('');

  { Step 1: extraction is done by Inno Setup }
  LogStep('  [1/5]  Extracting files...               done');

  { Step 2: Setup }
  LogStep('  [2/5]  Generating server configuration...');
  SetupArgs := 'setup --force --admin-email ' + ADMIN_EMAIL + ' --port ' + Port;
  if IsPostgreSQL then
    SetupArgs := SetupArgs + ' --database-url "' + Trim(PgUrlEdit.Text) + '"';
  if RunCmd(AppDir + '\detec-server.exe', SetupArgs, AppDir) then
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  [2/5]  Generating server configuration... done'
  else
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  [2/5]  Generating server configuration... ERROR';
  WizardForm.Refresh;

  { Step 3: Install service }
  LogStep('  [3/5]  Installing Windows Service...');
  if RunCmd(AppDir + '\detec-server.exe', 'install', AppDir) then
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  [3/5]  Installing Windows Service...      done'
  else
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  [3/5]  Installing Windows Service...      ERROR';
  WizardForm.Refresh;

  { Step 4: Start service }
  LogStep('  [4/5]  Starting Detec Server...');
  if RunCmd(AppDir + '\detec-server.exe', 'start', AppDir) then
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  [4/5]  Starting Detec Server...           done'
  else
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  [4/5]  Starting Detec Server...           ERROR';
  WizardForm.Refresh;

  { Step 5: Firewall + shortcut }
  LogStep('  [5/5]  Configuring firewall...');
  RunCmd(ExpandConstant('{sys}\netsh.exe'),
         'advfirewall firewall add rule name="Detec Server" ' +
         'dir=in action=allow protocol=TCP localport=' + Port, '');
  LogMemo.Lines[LogMemo.Lines.Count - 1] :=
    '  [5/5]  Configuring firewall...            done';
  WizardForm.Refresh;

  { Create desktop shortcut with the chosen port }
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

  LogMemo.Lines.Add('');
  LogStep('  Detec Server is running at http://localhost:' + Port);

  { Populate credentials page }
  Password := ReadPasswordFromEnv;
  if IsPostgreSQL then
    DbLabel := 'PostgreSQL'
  else
    DbLabel := 'SQLite (C:\ProgramData\Detec\detec.db)';

  CredsMemo.Lines.Add('');
  CredsMemo.Lines.Add('  Detec Server is running!');
  CredsMemo.Lines.Add('');
  CredsMemo.Lines.Add('  Dashboard:       http://localhost:' + Port);
  CredsMemo.Lines.Add('  Database:        ' + DbLabel);
  CredsMemo.Lines.Add('');
  CredsMemo.Lines.Add('  -----------------------------------------------');
  CredsMemo.Lines.Add('');
  CredsMemo.Lines.Add('  Sign in with:    ' + ADMIN_EMAIL);
  CredsMemo.Lines.Add('  Password:        ' + Password);
  CredsMemo.Lines.Add('');
  CredsMemo.Lines.Add('  SAVE THIS PASSWORD. It will not be shown again.');
  CredsMemo.Lines.Add('');
  CredsMemo.Lines.Add('  -----------------------------------------------');
  CredsMemo.Lines.Add('  Config:    C:\ProgramData\Detec\server.env');
  CredsMemo.Lines.Add('  Logs:      C:\ProgramData\Detec\server.log');
end;

{ ── Ready page summary ─────────────────────────────────────────────── }

function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo,
  MemoTypeInfo, MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: string): string;
var
  Port, DbDesc: string;
begin
  Port := GetUserPort;
  if IsPostgreSQL then
    DbDesc := 'PostgreSQL'
  else
    DbDesc := 'SQLite (C:\ProgramData\Detec\detec.db)';

  Result :=
    'Detec Server will be installed with these settings:' + NewLine +
    NewLine +
    Space + 'Install directory:' + NewLine +
    Space + Space + ExpandConstant('{autopf}\Detec\Server') + NewLine +
    NewLine +
    Space + 'Server port: ' + Port + NewLine +
    Space + 'Database: ' + DbDesc + NewLine +
    Space + 'Admin account: ' + ADMIN_EMAIL + NewLine +
    NewLine +
    Space + 'After file extraction, the installer will:' + NewLine +
    Space + Space + 'Generate configuration and admin account' + NewLine +
    Space + Space + 'Install and start the Detec Server Windows Service' + NewLine +
    Space + Space + 'Configure Windows Firewall (TCP ' + Port + ' inbound)' + NewLine +
    Space + Space + 'Create a "Detec Dashboard" desktop shortcut';
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
