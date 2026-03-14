; Detec Agent - Inno Setup Installer Script
;
; UI: Full dark theme (Slate 900) with branded header and indigo accent.
; Shows a clean progress log during install, then auto-closes with a
; brief countdown. No wizard pages. Supports /VERYSILENT for headless.
;
; Tamper controls (see docs/tamper-controls.md):
;   - PrivilegesRequired=admin: install and uninstall require elevation (UAC).
;   - Service stop/delete: Windows SCM restricts sc stop / sc delete to admins.
;   - Optional uninstall token: ProgramData\Detec\Agent\allow_uninstall.token
;     for scripted/MDM uninstall (documented in tamper-controls.md).
;
; Config embedding (zero-touch):
;   When downloaded from the Detec Server dashboard, this installer has
;   tenant configuration (API URL, key, interval) appended after the PE
;   data. The post-install step extracts it automatically via PowerShell.
;
;   Binary layout:
;     [original EXE] [DETEC_CFG_V1\0] [JSON bytes] [4-byte LE length] [DETEC_CFG_V1\0]
;
;   If no embedded config is found, the agent installs but requires
;   manual setup: detec-agent setup --api-url ... --api-key ...
;
; Build (from repo root):
;   powershell -ExecutionPolicy Bypass -File packaging\windows\build-installer.ps1

#define AppName      "Detec Agent"
#define AppVersion   "0.3.0"
#define AppPublisher "Detec"
#define AppURL       "https://github.com/grislyevan/agentic-governance"

[Setup]
AppId={{D3T3C-AG3N-T001-0000-000000000001}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
DefaultDirName={autopf}\Detec\Agent
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableWelcomePage=yes
OutputDir=..\dist
OutputBaseFilename=DetecAgentSetup-{#AppVersion}
UninstallDisplayIcon={app}\detec-agent.exe
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
Source: "..\dist\detec-agent\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\detec-agent-gui\*"; DestDir: "{app}\Agent-GUI"; Flags: ignoreversion recursesubdirs createallsubdirs

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "DetecAgentGUI"; ValueData: """{app}\Agent-GUI\detec-agent-gui.exe"""; Flags: uninsdeletevalue

[Run]
Filename: "{app}\Agent-GUI\detec-agent-gui.exe"; Flags: nowait runasoriginaluser skipifsilent

[UninstallRun]
Filename: "{app}\detec-agent.exe"; Parameters: "stop"; Flags: runhidden waituntilterminated; RunOnceId: "StopAgentService"
Filename: "{app}\detec-agent.exe"; Parameters: "remove"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveAgentService"

[Code]
var
  LogMemo: TNewMemo;
  InstallHadErrors: Boolean;
  ConfigExtracted: Boolean;

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
  WizardForm.Refresh;
end;

function PadRight(const S: string; Len: Integer): string;
begin
  Result := S;
  while Length(Result) < Len do
    Result := Result + ' ';
end;

{ ── InitializeWizard ───────────────────────────────────────────────── }

procedure InitializeWizard;
var
  AccentBar: TPanel;
begin
  InstallHadErrors := False;
  ConfigExtracted := False;

  { Dark theme: Slate 900 (#0f172a) everywhere }
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

  { Indigo accent bar at the bottom of the header panel }
  AccentBar := TPanel.Create(WizardForm);
  AccentBar.Parent := WizardForm.MainPanel;
  AccentBar.SetBounds(
    0, WizardForm.MainPanel.ClientHeight - ScaleY(2),
    WizardForm.MainPanel.ClientWidth, ScaleY(2));
  AccentBar.Color := $00F16663;
  AccentBar.BevelOuter := bvNone;

  { Progress log }
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

{ ── Embedded config extraction ─────────────────────────────────────── }

procedure ExtractEmbeddedConfig;
var
  ScriptPath, ResultFile, DataDir, SetupExe: string;
  Lines: TArrayOfString;
  ResultLines: TArrayOfString;
  ResultCode: Integer;
begin
  SetupExe := ExpandConstant('{srcexe}');
  DataDir := ExpandConstant('{sd}\ProgramData\Detec\Agent');
  ScriptPath := ExpandConstant('{tmp}\extract-config.ps1');
  ResultFile := ExpandConstant('{tmp}\config-result.txt');

  SetArrayLength(Lines, 28);
  Lines[0]  := '$ErrorActionPreference = "Stop"';
  Lines[1]  := 'try {';
  Lines[2]  := '  $exe = [IO.File]::ReadAllBytes("' + SetupExe + '")';
  Lines[3]  := '  $magic = [Text.Encoding]::ASCII.GetBytes("DETEC_CFG_V1") + [byte]0';
  Lines[4]  := '  $mLen = $magic.Length';
  Lines[5]  := '  if ($exe.Length -lt ($mLen * 2 + 4)) { "NO_CONFIG" | Out-File "' + ResultFile + '"; exit }';
  Lines[6]  := '  $tail = New-Object byte[] $mLen';
  Lines[7]  := '  [Array]::Copy($exe, $exe.Length - $mLen, $tail, 0, $mLen)';
  Lines[8]  := '  $match = $true';
  Lines[9]  := '  for ($i = 0; $i -lt $mLen; $i++) { if ($tail[$i] -ne $magic[$i]) { $match = $false; break } }';
  Lines[10] := '  if (-not $match) { "NO_CONFIG" | Out-File "' + ResultFile + '"; exit }';
  Lines[11] := '  $lenOff = $exe.Length - $mLen - 4';
  Lines[12] := '  $cfgLen = [BitConverter]::ToUInt32($exe, $lenOff)';
  Lines[13] := '  $cfgOff = $lenOff - $cfgLen';
  Lines[14] := '  $jsonBytes = New-Object byte[] $cfgLen';
  Lines[15] := '  [Array]::Copy($exe, $cfgOff, $jsonBytes, 0, $cfgLen)';
  Lines[16] := '  $json = [Text.Encoding]::UTF8.GetString($jsonBytes)';
  Lines[17] := '  $cfg = $json | ConvertFrom-Json';
  Lines[18] := '  New-Item -ItemType Directory -Force -Path "' + DataDir + '" | Out-Null';
  Lines[19] := '  $env = @("AGENTIC_GOV_API_URL=$($cfg.api_url)","AGENTIC_GOV_API_KEY=$($cfg.api_key)","AGENTIC_GOV_INTERVAL=$($cfg.interval)","AGENTIC_GOV_PROTOCOL=$($cfg.protocol)")';
  Lines[20] := '  if ($cfg.PSObject.Properties["gateway_host"]) { $env += "AGENTIC_GOV_GATEWAY_HOST=$($cfg.gateway_host)" }';
  Lines[21] := '  if ($cfg.PSObject.Properties["gateway_port"]) { $env += "AGENTIC_GOV_GATEWAY_PORT=$($cfg.gateway_port)" }';
  Lines[22] := '  [IO.File]::WriteAllText("' + DataDir + '\agent.env", ($env -join "`n") + "`n")';
  Lines[23] := '  [IO.File]::WriteAllText("' + DataDir + '\collector.json", $json)';
  Lines[24] := '  "OK" | Out-File "' + ResultFile + '"';
  Lines[25] := '} catch {';
  Lines[26] := '  "ERROR: $($_.Exception.Message)" | Out-File "' + ResultFile + '"';
  Lines[27] := '}';
  SaveStringsToFile(ScriptPath, Lines, False);

  Exec('powershell.exe',
    '-NoProfile -ExecutionPolicy Bypass -File "' + ScriptPath + '"',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  if LoadStringsFromFile(ResultFile, ResultLines) then
  begin
    if (GetArrayLength(ResultLines) > 0) and (Pos('OK', ResultLines[0]) > 0) then
      ConfigExtracted := True;
  end;
end;

{ ── Page navigation logic ──────────────────────────────────────────── }

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpInstalling then
  begin
    WizardForm.PageNameLabel.Caption := 'Detec Agent';
    WizardForm.PageDescriptionLabel.Caption := 'v{#AppVersion}';
    LogMemo.Visible := True;
    WizardForm.ProgressGauge.Visible := False;
    WizardForm.StatusLabel.Visible := False;
    WizardForm.BackButton.Visible := False;
    WizardForm.NextButton.Visible := False;
    WizardForm.CancelButton.Visible := False;
  end else
    LogMemo.Visible := False;
end;

{ ── Skip everything except the Installing page ────────────────────── }

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID = wpReady) or (PageID = wpFinished);
end;

{ ── Pre-install: stop running service/GUI to avoid locked files ────── }

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Result := '';
  if Exec(ExpandConstant('{sys}\sc.exe'), 'query DetecAgent',
          '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if ResultCode = 0 then
    begin
      Exec(ExpandConstant('{sys}\sc.exe'), 'stop DetecAgent',
           '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
      Sleep(2000);
    end;
  end;
  Exec('taskkill.exe', '/F /IM detec-agent-gui.exe',
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

{ ── Post-install actions ───────────────────────────────────────────── }

procedure CurStepChanged(CurStep: TSetupStep);
var
  AppDir, DataDir, LogPath: string;
  Lines: TArrayOfString;
  I: Integer;
begin
  if CurStep <> ssPostInstall then
    Exit;

  AppDir := ExpandConstant('{app}');
  DataDir := ExpandConstant('{sd}\ProgramData\Detec\Agent');
  InstallHadErrors := False;

  LogStep('  Detec Agent v{#AppVersion}');
  LogStep('');

  LogStep('  ' + PadRight('Extracting files', 40) + 'done');

  LogStep('  Applying server configuration...');
  ExtractEmbeddedConfig;
  if ConfigExtracted then
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  ' + PadRight('Applying server configuration', 40) + 'done'
  else
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  ' + PadRight('Server configuration', 40) + 'skipped';
  WizardForm.Refresh;

  LogStep('  Installing Windows Service...');
  if RunCmd(AppDir + '\detec-agent.exe', 'install', AppDir) then
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  ' + PadRight('Installing Windows Service', 40) + 'done'
  else begin
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  ' + PadRight('Installing Windows Service', 40) + 'FAIL';
    InstallHadErrors := True;
  end;
  WizardForm.Refresh;

  LogStep('  Starting agent...');
  if RunCmd(AppDir + '\detec-agent.exe', 'start', AppDir) then
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  ' + PadRight('Starting agent', 40) + 'done'
  else begin
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  ' + PadRight('Starting agent', 40) + 'FAIL';
    InstallHadErrors := True;
  end;
  WizardForm.Refresh;

  LogStep('  Configuring failure recovery...');
  if RunCmd(AppDir + '\detec-agent.exe', 'set-recovery', AppDir) then
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  ' + PadRight('Configuring failure recovery', 40) + 'done'
  else
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  ' + PadRight('Configuring failure recovery', 40) + 'skipped';
  WizardForm.Refresh;

  LogStep('');
  if InstallHadErrors then
    LogStep('  Completed with warnings.')
  else if ConfigExtracted then
    LogStep('  Agent is running and connected.')
  else begin
    LogStep('  Agent is installed.');
    LogStep('  Run: detec-agent setup --api-url <URL> --api-key <KEY>');
  end;

  LogStep('');
  LogStep('  ' + PadRight('Install', 10) + AppDir);
  LogStep('  ' + PadRight('Data', 10) + DataDir);

  LogPath := DataDir + '\install.log';
  ForceDirectories(DataDir);
  SetArrayLength(Lines, LogMemo.Lines.Count);
  for I := 0 to LogMemo.Lines.Count - 1 do
    Lines[I] := LogMemo.Lines[I];
  SaveStringsToFile(LogPath, Lines, False);
  LogStep('');
  LogStep('  ' + PadRight('Log', 10) + LogPath);

  LogStep('');
  for I := 3 downto 1 do
  begin
    if I = 3 then
      LogStep('  Closing in ' + IntToStr(I) + '...')
    else begin
      LogMemo.Lines[LogMemo.Lines.Count - 1] :=
        '  Closing in ' + IntToStr(I) + '...';
      WizardForm.Refresh;
    end;
    Sleep(1000);
  end;
end;

{ ── Uninstall: kill GUI, offer to remove data directory ──────────── }

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: string;
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    Exec('taskkill.exe', '/F /IM detec-agent-gui.exe',
         '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;

  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{sd}\ProgramData\Detec\Agent');
    if DirExists(DataDir) then
    begin
      if MsgBox(
        'Do you also want to remove the Detec Agent data directory?' + #13#10 + #13#10 +
        'This will permanently delete:' + #13#10 +
        '  - Configuration (agent.env, collector.json)' + #13#10 +
        '  - Agent logs' + #13#10 + #13#10 +
        'Location: ' + DataDir,
        mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      begin
        DelTree(DataDir, True, True, True);
      end;
    end;
  end;
end;
