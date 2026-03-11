; Detec Agent - Inno Setup Installer Script
;
; Wizard flow:
;   Welcome > License > Installing (progress) > Finish
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
OutputDir=..\dist
OutputBaseFilename=DetecAgentSetup-{#AppVersion}
UninstallDisplayIcon={app}\detec-agent.exe
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
  FinishLabel: TNewStaticText;
  InstallHadErrors: Boolean;
  ConfigExtracted: Boolean;
  FinishPageCreated: Boolean;

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

{ ── InitializeWizard ───────────────────────────────────────────────── }

procedure InitializeWizard;
begin
  FinishPageCreated := False;
  InstallHadErrors := False;
  ConfigExtracted := False;

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
  LogMemo.Font.Size := 9;
  LogMemo.Color := $003B291E;
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
    LogMemo.Visible := True;
    WizardForm.ProgressGauge.Visible := False;
    WizardForm.StatusLabel.Visible := False;
  end else
    LogMemo.Visible := False;

  if (CurPageID = wpFinished) and (not FinishPageCreated) then
  begin
    FinishPageCreated := True;

    FinishLabel := TNewStaticText.Create(WizardForm);
    FinishLabel.Parent := WizardForm.FinishedPage;
    FinishLabel.AutoSize := False;
    FinishLabel.WordWrap := True;
    FinishLabel.SetBounds(
      ScaleX(0),
      WizardForm.FinishedLabel.Top + WizardForm.FinishedLabel.Height + ScaleY(12),
      WizardForm.FinishedPage.Width, ScaleY(60)
    );

    if InstallHadErrors then
      FinishLabel.Caption :=
        'Installation completed with warnings.' + #13#10 +
        'Check C:\ProgramData\Detec\Agent\install.log for details.'
    else if ConfigExtracted then
      FinishLabel.Caption :=
        'Detec Agent is running and connected to your server.' + #13#10 +
        'The agent icon should now be visible in the system tray.'
    else
      FinishLabel.Caption :=
        'Detec Agent is installed but no server configuration was found.' + #13#10 +
        'Run: detec-agent setup --api-url <URL> --api-key <KEY>';
  end;
end;

{ ── Skip the built-in Ready page (nothing to configure) ───────────── }

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID = wpReady);
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

  LogMemo.Lines.Add('  Installing Detec Agent');
  LogMemo.Lines.Add('');

  // Step 1: files already extracted by Inno Setup
  LogStep('  [1/4]  Extracting files...               done');

  // Step 2: extract embedded config from the installer EXE
  LogStep('  [2/4]  Extracting server configuration...');
  ExtractEmbeddedConfig;
  if ConfigExtracted then
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  [2/4]  Server configuration applied.      done'
  else
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  [2/4]  No embedded configuration found.   skipped';
  WizardForm.Refresh;

  // Step 3: register the Windows Service
  LogStep('  [3/4]  Installing Windows Service...');
  if RunCmd(AppDir + '\detec-agent.exe', 'install', AppDir) then
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  [3/4]  Installing Windows Service...      done'
  else begin
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  [3/4]  Installing Windows Service...      ERROR';
    InstallHadErrors := True;
  end;
  WizardForm.Refresh;

  // Step 4: start the service
  LogStep('  [4/4]  Starting Detec Agent...');
  if RunCmd(AppDir + '\detec-agent.exe', 'start', AppDir) then
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  [4/4]  Starting Detec Agent...            done'
  else begin
    LogMemo.Lines[LogMemo.Lines.Count - 1] :=
      '  [4/4]  Starting Detec Agent...            ERROR';
    InstallHadErrors := True;
  end;
  WizardForm.Refresh;

  // Summary
  LogMemo.Lines.Add('');
  if InstallHadErrors then begin
    LogStep('  Installation completed with warnings.');
    LogMemo.Lines.Add('  Some steps need attention.');
  end else if ConfigExtracted then
    LogStep('  Detec Agent is installed and connected.')
  else begin
    LogStep('  Detec Agent is installed.');
    LogMemo.Lines.Add('  Configure: detec-agent setup --api-url <URL> --api-key <KEY>');
  end;

  LogMemo.Lines.Add('');
  LogMemo.Lines.Add('  Install directory:  ' + AppDir);
  LogMemo.Lines.Add('  Data directory:     ' + DataDir);

  // Persist install log
  LogPath := DataDir + '\install.log';
  ForceDirectories(DataDir);
  SetArrayLength(Lines, LogMemo.Lines.Count);
  for I := 0 to LogMemo.Lines.Count - 1 do
    Lines[I] := LogMemo.Lines[I];
  SaveStringsToFile(LogPath, Lines, False);
  LogStep('');
  LogStep('  Install log saved to ' + LogPath);
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
