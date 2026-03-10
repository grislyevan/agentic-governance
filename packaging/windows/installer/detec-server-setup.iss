; Detec Server - Inno Setup Installer Script
;
; Produces a single DetecServerSetup.exe that:
;   1. Extracts the pre-built detec-server bundle
;   2. Runs first-time setup (generates secrets + admin credentials)
;   3. Installs and starts the Windows Service
;   4. Configures the Windows Firewall
;   5. Creates a desktop shortcut
;
; Build (from repo root):
;   powershell -ExecutionPolicy Bypass -File packaging\windows\build-installer.ps1
;
; Or manually:
;   cd packaging\windows
;   pyinstaller --clean --noconfirm detec-server.spec
;   cd installer
;   python generate-assets.py
;   iscc detec-server-setup.iss

#define AppName      "Detec Server"
#define AppVersion   "0.1.0"
#define AppPublisher "Detec"
#define AppURL       "https://github.com/grislyevan/agentic-governance"
#define ServerPort   "8000"

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
SetupIconFile=..\..\..\branding\detec-icon.ico
UninstallDisplayIcon={app}\detec-server.exe
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

[Icons]
Name: "{commondesktop}\Detec Dashboard"; Filename: "http://localhost:{#ServerPort}"; IconFilename: "{app}\detec-server.exe"; Comment: "Open the Detec governance dashboard"

[UninstallRun]
Filename: "{app}\detec-server.exe"; Parameters: "stop"; Flags: runhidden waituntilterminated; RunOnceId: "StopService"
Filename: "{app}\detec-server.exe"; Parameters: "remove"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveService"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Detec Server"""; Flags: runhidden waituntilterminated; RunOnceId: "RemoveFirewall"

[UninstallDelete]
Type: files; Name: "{commondesktop}\Detec Dashboard.lnk"

[Code]
var
  AdminEmailPage: TInputQueryWizardPage;
  CredentialsPage: TWizardPage;
  CredsMemo: TNewMemo;
  LogMemo: TNewMemo;

procedure InitializeWizard;
begin
  { --- Admin email page (after Welcome) --- }
  AdminEmailPage := CreateInputQueryPage(wpWelcome,
    'Administrator Account',
    'Set the email address for the initial admin account.',
    'This email will be used to sign in to the Detec dashboard. ' +
    'A strong password will be generated automatically.');
  AdminEmailPage.Add('Admin email:', False);
  AdminEmailPage.Values[0] := 'admin@yourorg.com';

  { --- Progress log on the installing page --- }
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
  LogMemo.Color := $003B291E;   { BGR for slate-800 #1e293b }
  LogMemo.Font.Color := $00F9F5F1; { BGR for slate-100 #f1f5f9 }
  LogMemo.Visible := False;

  { --- Credentials page (after installing, before Finish) --- }
  CredentialsPage := CreateCustomPage(wpInstalling,
    'Administrator Credentials',
    'Save these credentials now. The password cannot be recovered later.');

  CredsMemo := TNewMemo.Create(CredentialsPage);
  CredsMemo.Parent := CredentialsPage.Surface;
  CredsMemo.SetBounds(
    0, 0,
    CredentialsPage.SurfaceWidth,
    CredentialsPage.SurfaceHeight - ScaleY(4)
  );
  CredsMemo.ReadOnly := True;
  CredsMemo.ScrollBars := ssVertical;
  CredsMemo.Font.Name := 'Consolas';
  CredsMemo.Font.Size := 11;
  CredsMemo.Color := $003B291E;
  CredsMemo.Font.Color := $00F9F5F1;
end;

{ Append a line to the install log and update the status label. }
procedure LogStep(const Msg: string);
begin
  LogMemo.Lines.Add(Msg);
  { Auto-scroll to bottom }
  SendMessage(LogMemo.Handle, $00B7 {EM_LINESCROLL}, 0, LogMemo.Lines.Count);
  WizardForm.StatusLabel.Caption := Msg;
  WizardForm.Refresh;
end;

{ Read the generated admin password from server.env after setup runs. }
function ReadPasswordFromEnv: string;
var
  Lines: TArrayOfString;
  I, P: Integer;
  Line: string;
  EnvFile: string;
begin
  Result := '(could not read -- check C:\ProgramData\Detec\server.env)';
  EnvFile := ExpandConstant('{sd}\ProgramData\Detec\server.env');
  if LoadStringsFromFile(EnvFile, Lines) then
  begin
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
end;

{ Run a command and return success. }
function RunCmd(const Filename, Params, WorkDir: string): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec(Filename, Params, WorkDir, SW_HIDE,
                 ewWaitUntilTerminated, ResultCode)
            and (ResultCode = 0);
end;

{ Post-install: configure the server, install the service, open the firewall. }
procedure CurStepChanged(CurStep: TSetupStep);
var
  AppDir, AdminEmail, Password: string;
begin
  if CurStep <> ssPostInstall then
    Exit;

  LogMemo.Visible := True;
  AppDir := ExpandConstant('{app}');
  AdminEmail := AdminEmailPage.Values[0];

  { Step 1: First-time setup }
  LogStep('Generating server configuration...');
  if RunCmd(AppDir + '\detec-server.exe',
            'setup --force --admin-email ' + AdminEmail, AppDir) then
    LogStep('  [OK] Configuration written to C:\ProgramData\Detec\')
  else
    LogStep('  [!]  Setup exited with an error (check server.env)');

  { Step 2: Install Windows Service }
  LogStep('Installing Windows Service...');
  if RunCmd(AppDir + '\detec-server.exe', 'install', AppDir) then
    LogStep('  [OK] Service "Detec Server" registered')
  else
    LogStep('  [!]  Service install returned an error');

  { Step 3: Start the service }
  LogStep('Starting Detec Server...');
  if RunCmd(AppDir + '\detec-server.exe', 'start', AppDir) then
    LogStep('  [OK] Service started')
  else
    LogStep('  [!]  Service start returned an error');

  { Step 4: Firewall rule }
  LogStep('Configuring firewall...');
  RunCmd(ExpandConstant('{sys}\netsh.exe'),
         'advfirewall firewall add rule name="Detec Server" ' +
         'dir=in action=allow protocol=TCP localport={#ServerPort}', '');
  LogStep('  [OK] Firewall rule added (TCP {#ServerPort} inbound)');

  LogStep('');
  LogStep('Detec Server is running at http://localhost:{#ServerPort}');

  { Read the generated password and populate the credentials page }
  Password := ReadPasswordFromEnv;
  CredsMemo.Lines.Add('');
  CredsMemo.Lines.Add('  Detec Server is running!');
  CredsMemo.Lines.Add('');
  CredsMemo.Lines.Add('  Dashboard:       http://localhost:{#ServerPort}');
  CredsMemo.Lines.Add('  API docs:        http://localhost:{#ServerPort}/docs');
  CredsMemo.Lines.Add('');
  CredsMemo.Lines.Add('  Admin email:     ' + AdminEmail);
  CredsMemo.Lines.Add('  Admin password:  ' + Password);
  CredsMemo.Lines.Add('');
  CredsMemo.Lines.Add('  SAVE THIS PASSWORD. It will not be shown again.');
  CredsMemo.Lines.Add('');
  CredsMemo.Lines.Add('  -----------------------------------------------');
  CredsMemo.Lines.Add('  Config:    C:\ProgramData\Detec\server.env');
  CredsMemo.Lines.Add('  Database:  C:\ProgramData\Detec\detec.db');
  CredsMemo.Lines.Add('  Logs:      C:\ProgramData\Detec\server.log');
end;

{ Summary shown on the Ready page. }
function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo,
  MemoTypeInfo, MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: string): string;
begin
  Result :=
    'Detec Server will be installed with these settings:' + NewLine +
    NewLine +
    Space + 'Install directory:' + NewLine +
    Space + Space + ExpandConstant('{app}') + NewLine +
    NewLine +
    Space + 'Admin email:' + NewLine +
    Space + Space + AdminEmailPage.Values[0] + NewLine +
    NewLine +
    Space + 'After file extraction, the installer will:' + NewLine +
    Space + Space + 'Generate server configuration and secrets' + NewLine +
    Space + Space + 'Install and start the Detec Server Windows Service' + NewLine +
    Space + Space + 'Configure Windows Firewall (TCP {#ServerPort} inbound)' + NewLine +
    Space + Space + 'Create a "Detec Dashboard" desktop shortcut';
end;

{ Open dashboard in browser from the Finish page. }
procedure OpenDashboard(Sender: TObject);
var
  ErrorCode: Integer;
begin
  ShellExec('open', 'http://localhost:{#ServerPort}', '', '', SW_SHOW, ewNoWait, ErrorCode);
end;

{ Add an "Open Dashboard" button to the Finish page. }
procedure CurPageChanged(CurPageID: Integer);
var
  Btn: TNewButton;
begin
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

{ After uninstall, offer to remove the data directory (database, config, logs). }
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
        'Do you also want to remove the Detec data directory?' + #13#10 +
        #13#10 +
        'This will permanently delete:' + #13#10 +
        '  - Database (detec.db)' + #13#10 +
        '  - Configuration (server.env)' + #13#10 +
        '  - Server logs (server.log)' + #13#10 +
        #13#10 +
        'Location: ' + DataDir,
        mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      begin
        DelTree(DataDir, True, True, True);
      end;
    end;
  end;
end;
