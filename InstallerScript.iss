; -- Example Inno Setup script snippet --

#define MyAppName "Internet Manager"
#define MyAppNameNoSpace "Internet-Manager"
#define MyAppVersion "1.3.0"
#define MyAppPublisher "Dalichrome"
#define MyAppURL "https://dalichro.me/project/internet-manager/"
#define MyAppExeName "internet_manager.exe"
#define MyAppServerExeName "internet_manager_server.exe"
#define MyAppUtilityExe "internet_manager_utility.exe"

[Setup]
AppId={{830FD9CF-9FF5-429D-A381-6E48510D3202}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
OutputBaseFilename={#MyAppNameNoSpace}-{#MyAppVersion}-Installer
UninstallDisplayName=Uninstaller
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
CloseApplications=force
LicenseFile=EULA
SetupIconFile=src\assets\globe_server.ico
WizardImageFile=src\assets\internet_manager_frame.bmp
WizardSmallImageFile=src\assets\globex147.bmp
WizardImageStretch=yes
WizardImageAlphaFormat=premultiplied
WizardResizable=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; \
  GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Dirs]
Name: "{commonappdata}\InternetManager"; Permissions: users-modify

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\{#MyAppServerExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\{#MyAppUtilityExe}"; DestDir: "{app}"; Flags: ignoreversion

Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "EULA"; DestDir: "{app}"; Flags: ignoreversion
Source: "attribution.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Ask the running server to shut down (best-effort)
Filename: "{app}\{#MyAppUtilityExe}"; Parameters: "close-server"; Flags: runhidden;

; Create/update the scheduled tasks (requires admin; installer already runs admin)
Filename: "{app}\{#MyAppUtilityExe}"; Parameters: "install-tasks"; Flags: runhidden waituntilterminated

[UninstallRun]
; Ask the running server to shut down (best-effort)
Filename: "{app}\{#MyAppUtilityExe}"; Parameters: "close-server"; Flags: runhidden; RunOnceId: "KillServerTask"

; Remove scheduled tasks
Filename: "{app}\{#MyAppUtilityExe}"; Parameters: "remove-tasks"; Flags: runhidden; RunOnceId: "RemoveTasks"




[Registry]
Root: HKLM; Subkey: "Software\Dalitech\Internet Manager"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey

[Code]

var
  StartManagerCheckbox: TCheckBox;

// -----------------------------------------------------------------------------
// NAIVE JSON HELPER FUNCTIONS
// (Caution: Will break if JSON is formatted differently or includes escaping.)
// -----------------------------------------------------------------------------
function ReadJsonString(const JSON, Key: String; DefaultValue: String): String;
var
  KeyPos, StartPos, EndPos: Integer;
  KeySearch: String;
begin
  Result := DefaultValue;
  KeySearch := '"' + Key + '":';
  KeyPos := Pos(KeySearch, JSON);
  if KeyPos = 0 then
    Exit;

  StartPos := KeyPos + Length(KeySearch);
  while (StartPos <= Length(JSON)) and (JSON[StartPos] <> '"') do
    Inc(StartPos);
  if StartPos > Length(JSON) then
    Exit;
  Inc(StartPos); // skip quote
  EndPos := StartPos;
  while (EndPos <= Length(JSON)) and (JSON[EndPos] <> '"') do
    Inc(EndPos);
  if EndPos > Length(JSON) then
    Exit;
  Result := Copy(JSON, StartPos, EndPos - StartPos);
end;

function ReadJsonBoolean(const JSON, Key: String; DefaultValue: Boolean): Boolean;
var
  KeyPos, StartPos, EndPos: Integer;
  KeySearch, Value: String;
begin
  Result := DefaultValue;
  KeySearch := '"' + Key + '":';
  KeyPos := Pos(KeySearch, JSON);
  if KeyPos = 0 then
    Exit;

  StartPos := KeyPos + Length(KeySearch);

  // Skip whitespace after the colon
  while (StartPos <= Length(JSON)) and (JSON[StartPos] <= ' ') do
    Inc(StartPos);

  if StartPos > Length(JSON) then
    Exit;

  EndPos := StartPos;
  // Read until comma/brace/whitespace/newline/tab
  while (EndPos <= Length(JSON)) and not (JSON[EndPos] in [',', '}', ' ', #9, #10, #13]) do
    Inc(EndPos);

  Value := Lowercase(Trim(Copy(JSON, StartPos, EndPos - StartPos)));

  if Value = 'true' then
    Result := True
  else if Value = 'false' then
    Result := False;
end;

function ReadJsonInteger(const JSON, Key: String; DefaultValue: Integer): Integer;
var
  KeyPos, StartPos, EndPos: Integer;
  KeySearch, Value: String;
begin
  Result := DefaultValue; // Initialize result with default value
  KeySearch := '"' + Key + '":'; // Construct the search pattern for the key
  KeyPos := Pos(KeySearch, JSON); // Find the position of the key in the JSON string
  if KeyPos = 0 then
    Exit; // If key is not found, return the default value

  StartPos := KeyPos + Length(KeySearch); // Position right after the key and colon

  // Skip any whitespace characters (space, tab, newline, etc.)
  while (StartPos <= Length(JSON)) and (JSON[StartPos] <= ' ') do
    Inc(StartPos);

  if StartPos > Length(JSON) then
    Exit; // If we've reached the end of the string, exit with default value

  EndPos := StartPos; // Initialize end position to start position

  // Continue until we find a delimiter that signifies the end of the integer value
  while (EndPos <= Length(JSON)) and not (JSON[EndPos] in [',', '}', ' ', #10, #13, #9]) do
    Inc(EndPos);

  // Extract the substring that represents the integer value
  Value := Trim(Copy(JSON, StartPos, EndPos - StartPos));

  try
    Result := StrToInt(Value); // Attempt to convert the extracted string to an integer
  except
    // If conversion fails, keep the default value
  end;
end;

function ReadJsonArrayAsString(const JSON, Key: String; DefaultValue: String): String;
var
  KeyPos, StartPos, EndPos, Count: Integer;
  KeySearch, ArrayContent: String;
begin
  Result := DefaultValue;
  KeySearch := '"' + Key + '":';
  KeyPos := Pos(KeySearch, JSON);
  if KeyPos = 0 then
    Exit;

  StartPos := KeyPos + Length(KeySearch);
  // find '['
  while (StartPos <= Length(JSON)) and (JSON[StartPos] <> '[') do
    Inc(StartPos);
  if StartPos > Length(JSON) then
    Exit;
  Inc(StartPos); // skip '['

  // find ']'
  EndPos := StartPos;
  while (EndPos <= Length(JSON)) and (JSON[EndPos] <> ']') do
    Inc(EndPos);
  if EndPos > Length(JSON) then
    Exit;

  ArrayContent := Copy(JSON, StartPos, EndPos - StartPos);

  Count := StringChangeEx(ArrayContent, '"', '', True);
  ArrayContent := Trim(ArrayContent);

  Result := ArrayContent;
end;

// -----------------------------------------------------------------------------
// SPLIT AND JOIN HELPERS
// -----------------------------------------------------------------------------
function SplitString(Text: String; Separator: String): TArrayOfString;
var
  i, p: Integer;
  Dest: TArrayOfString;
begin
  i := 0;
  repeat
    SetArrayLength(Dest, i+1);
    p := Pos(Separator, Text);
    if p > 0 then
    begin
      Dest[i] := Copy(Text, 1, p-1);
      Text := Copy(Text, p + Length(Separator), Length(Text));
      i := i + 1;
    end
    else
    begin
      Dest[i] := Text;
      Text := '';
    end;
  until Length(Text)=0;
  Result := Dest;
end;

function StringListFromComma(const S: String): String;
var
  Temp: String;
  i: Integer;
  Items: TArrayOfString;
begin
  Items := SplitString(S, ',');
  Result := '';
  for i := 0 to GetArrayLength(Items)-1 do
  begin
    Temp := Trim(Items[i]);
    if Temp <> '' then
    begin
      if Result <> '' then
        Result := Result + ',';
      Result := Result + '"' + Temp + '"';
    end;
  end;
  if Result <> '' then
    Result := '[' + Result + ']'
  else
    Result := '[]';
end;

function BoolToStr(Value: Boolean): String;
begin
  if Value then
    Result := 'True'
  else
    Result := 'False';
end;

// -----------------------------------------------------------------------------
// HELPER: Create a label + TEdit on a custom page
// -----------------------------------------------------------------------------
function CreateLabeledEdit(const AParent: TWinControl; const Caption: String;
  var TheEdit: TEdit; ALeft, ATop, AWidth: Integer): Integer;
var
  Lbl: TLabel;
begin
  Lbl := TLabel.Create(WizardForm);
  Lbl.Parent := AParent;
  Lbl.Top := ATop;
  Lbl.Left := ALeft;
  Lbl.Caption := Caption;

  TheEdit := TEdit.Create(WizardForm);
  TheEdit.Parent := AParent;
  TheEdit.Top := Lbl.Top + Lbl.Height + 4;
  TheEdit.Left := ALeft;
  TheEdit.Width := AWidth;

  Result := TheEdit.Top + TheEdit.Height;
end;

// -----------------------------------------------------------------------------
// GLOBALS: Two pages + all config controls
// -----------------------------------------------------------------------------
var
  BasicPage, AdvancedPage: TWizardPage;

// Basic fields
var
  EditShutdownTimes: TEdit;
  EditEnforcedShutdownTimes: TEdit;
  EditUpTimes: TEdit;
  EditNetworks: TEdit;
  EditWarningMinutes: TEdit;
  CheckMilitaryTime: TCheckBox;
  CheckSoundOn: TCheckBox;
  CheckUseRetroVoucher: TCheckBox;

// Advanced fields
var
  EditHost: TEdit;
  EditPort: TEdit;
  EditKey: TEdit;
  EditStreakShift: TEdit;

// -----------------------------------------------------------------------------
// Load existing config from file using LoadStringFromFile with a temporary variable
// -----------------------------------------------------------------------------
function LoadExistingConfig(const ConfigFile: String): String;
var
  FileContent: AnsiString;
begin
  // Default to empty
  Result := '';

  // Only attempt to load if file exists
  if FileExists(ConfigFile) then
  begin
    // LoadStringFromFile returns True on success, False otherwise
    if LoadStringFromFile(ConfigFile, FileContent) then
      Result := FileContent
    else
      Result := ''; 
  end;
end;

// -----------------------------------------------------------------------------
// Fill TEdits / Checkboxes from JSON or fallback default
// -----------------------------------------------------------------------------
procedure FillWizardFieldsFromJson(const JSON: String);
begin
  // BASIC FIELDS
  EditShutdownTimes.Text := ReadJsonArrayAsString(JSON, 'shutdown_times',
      '23:00:00,23:30:00,23:45:00,23:52:30,0:00:00');
  EditEnforcedShutdownTimes.Text := ReadJsonArrayAsString(JSON, 'enforced_shutdown_times',
      '0:05:00');
  EditUpTimes.Text := ReadJsonArrayAsString(JSON, 'up_times', '4:30:00');
  EditNetworks.Text := ReadJsonArrayAsString(JSON, 'networks', 'Ethernet,Wi-Fi');
  EditWarningMinutes.Text := IntToStr(ReadJsonInteger(JSON, 'warning_minutes', 15));
  CheckMilitaryTime.Checked := ReadJsonBoolean(JSON, 'military_time', False);
  CheckSoundOn.Checked := ReadJsonBoolean(JSON, 'sound_on', True);
  CheckUseRetroVoucher.Checked := ReadJsonBoolean(JSON, 'use_retrovoucher', False);
  
  // ADVANCED FIELDS
  EditHost.Text := ReadJsonString(JSON, 'host', '127.0.0.1');
  EditPort.Text := IntToStr(ReadJsonInteger(JSON, 'port', 65432));
  EditKey.Text := ReadJsonString(JSON, 'key', 'sWXO8LvX0FaQgNAbDckjy32kfBQDPtvODAVLhcc7GgM=');
  EditStreakShift.Text := ReadJsonString(JSON, 'streak_shift', '4:00');
end;

// -----------------------------------------------------------------------------
// Generate JSON from all fields
// -----------------------------------------------------------------------------
function GenerateJsonFromWizardFields(): String;
var
  shutdownTimes, enforcedShutdownTimes, upTimes, ethernet: String;
  warningMinutes: Integer;
  mt, so, urv: Boolean;
  host, key, streakShift: String;
  port: Integer;
begin
  // BASIC FIELDS
  shutdownTimes := StringListFromComma(EditShutdownTimes.Text);
  enforcedShutdownTimes := StringListFromComma(EditEnforcedShutdownTimes.Text);
  upTimes := StringListFromComma(EditUpTimes.Text);
  ethernet := StringListFromComma(EditNetworks.Text);
  warningMinutes := StrToIntDef(EditWarningMinutes.Text, 15);
  mt := CheckMilitaryTime.Checked;
  so := CheckSoundOn.Checked;
  urv := CheckUseRetroVoucher.Checked;

  // ADVANCED FIELDS
  host := EditHost.Text;
  port := StrToIntDef(EditPort.Text, 65432);
  key := EditKey.Text;
  streakShift := EditStreakShift.Text;

  Result :=
    '{'#13#10 +
    '  "host": "' + host + '",'#13#10 +
    '  "port": ' + IntToStr(port) + ','#13#10 +
    '  "key": "' + key + '",'#13#10 +
    '  "shutdown_times": ' + shutdownTimes + ','#13#10 +
    '  "enforced_shutdown_times": ' + enforcedShutdownTimes + ','#13#10 +
    '  "up_times": ' + upTimes + ','#13#10 +
    '  "networks": ' + ethernet + ','#13#10 +
    '  "streak_shift": "' + streakShift + '",'#13#10 +
    '  "military_time": ' + Lowercase(BoolToStr(mt)) + ','#13#10 +
    '  "sound_on": ' + Lowercase(BoolToStr(so)) + ','#13#10 +
    '  "warning_minutes": ' + IntToStr(warningMinutes) + ','#13#10 +  
    '  "use_retrovoucher": ' + Lowercase(BoolToStr(urv)) + #13#10 +  
    '}';
end;

// -----------------------------------------------------------------------------
// Save JSON
// -----------------------------------------------------------------------------
procedure SaveJson(const FilePath, JSONData: String);
begin
  SaveStringToFile(FilePath, JSONData, False);
end;

// -----------------------------------------------------------------------------
// CREATE WIZARD PAGES
// 1) BasicPage
// 2) AdvancedPage
// -----------------------------------------------------------------------------
procedure InitializeWizard();
var
  NextTop: Integer;
begin

  // -------------------- Universal Styling --------------------
  WizardForm.Caption := '{#MyAppName}' + ' ' + '{#MyAppVersion}' + ' Installer';

  // Change the main wizard background color to light blue (RGB(230, 240, 255))
  WizardForm.Color := $00342022;


  // -------------------- Basic Settings Page --------------------
  BasicPage := CreateCustomPage(wpSelectDir,
    'Basic Settings',
    'Configure the basic Internet Manager settings.');

  NextTop := 0;

  // Shutdown Times
  NextTop := CreateLabeledEdit(BasicPage.Surface,
    'Skippable Internet Shutdown Times (comma-separated):', EditShutdownTimes, 10, NextTop, 300) + 12;
  // Enforced Shutdown Times
  NextTop := CreateLabeledEdit(BasicPage.Surface,
    'Unskippable Internet Shutdown Times (comma-separated):', EditEnforcedShutdownTimes, 10, NextTop, 300) + 12;
  // Up Times
  NextTop := CreateLabeledEdit(BasicPage.Surface,
    'Internet Turn On Times (comma-separated):', EditUpTimes, 10, NextTop, 300) + 12;
  // Ethernet
  NextTop := CreateLabeledEdit(BasicPage.Surface,
    'Networks (comma-separated) [Use "View Network Connections" to find network names]:', EditNetworks, 10, NextTop, 300) + 12;
  // Warning Minutes
  NextTop := CreateLabeledEdit(BasicPage.Surface,
    'Warning Minutes (How many minutes prior to a shutdown you hear a noise):', EditWarningMinutes, 10, NextTop, 100) + 12;

  // ---- Checkbox row (horizontal) ----
  // Military Time
  CheckMilitaryTime := TCheckBox.Create(WizardForm);
  CheckMilitaryTime.Parent := BasicPage.Surface;
  CheckMilitaryTime.Top := NextTop + 4;
  CheckMilitaryTime.Left := 10;
  CheckMilitaryTime.Width := 140;
  CheckMilitaryTime.Caption := 'Military Time';
  CheckMilitaryTime.Checked := False;

  // Sound On
  CheckSoundOn := TCheckBox.Create(WizardForm);
  CheckSoundOn.Parent := BasicPage.Surface;
  CheckSoundOn.Top := CheckMilitaryTime.Top;         // same row
  CheckSoundOn.Left := CheckMilitaryTime.Left + CheckMilitaryTime.Width + 16;
  CheckSoundOn.Width := 110;
  CheckSoundOn.Caption := 'Sound On';
  CheckSoundOn.Checked := True;

  // Use RetroVoucher
  CheckUseRetroVoucher := TCheckBox.Create(WizardForm);
  CheckUseRetroVoucher.Parent := BasicPage.Surface;
  CheckUseRetroVoucher.Top := CheckMilitaryTime.Top; // same row
  CheckUseRetroVoucher.Left := CheckSoundOn.Left + CheckSoundOn.Width + 16;
  CheckUseRetroVoucher.Width := 160;
  CheckUseRetroVoucher.Caption := 'RetroVoucher';
  CheckUseRetroVoucher.Checked := False; // default OFF

  // advance layout AFTER the row
  NextTop := 0;
  
  // -------------------- Advanced Settings Page --------------------
  AdvancedPage := CreateCustomPage(BasicPage.ID,
    'Advanced Settings',
    'Configure advanced settings like Host, Port, etc. [DO NOT CHANGE THESE UNLESS YOU KNOW WHAT YOURE DOING]');

  // Host
  NextTop := CreateLabeledEdit(AdvancedPage.Surface,
    'Host:', EditHost, 10, NextTop, 250) + 12;

  // Port
  NextTop := CreateLabeledEdit(AdvancedPage.Surface,
    'Port:', EditPort, 10, NextTop, 100) + 12;

  // Key
  NextTop := CreateLabeledEdit(AdvancedPage.Surface,
    'Key:', EditKey, 10, NextTop, 300) + 12;

  // Streak Shift
  NextTop := CreateLabeledEdit(AdvancedPage.Surface,
    'Streak Shift (HH:MM):', EditStreakShift, 10, NextTop, 100) + 12;
end;

// -----------------------------------------------------------------------------
// When wizard page changes, if we land on BasicPage, we load existing config
// so that by the time we go to AdvancedPage, all fields are already set.
// -----------------------------------------------------------------------------
procedure CurPageChanged(CurPageID: Integer);
var
  ExistingJson: String;
begin
  // MsgBox('CurPageChanged ' + IntToStr(CurPageID), mbInformation, MB_OK);
  // Load existing config when on BasicPage
  if CurPageID = BasicPage.ID then
  begin
    ExistingJson := LoadExistingConfig(ExpandConstant('{commonappdata}\InternetManager\config.json'));
    if ExistingJson <> '' then
      FillWizardFieldsFromJson(ExistingJson)
    else
      FillWizardFieldsFromJson('');
  end;

  // Initialize the Finished page checkbox
  if CurPageID = wpFinished then
  begin
    if not Assigned(StartManagerCheckbox) then
    begin
      StartManagerCheckbox := TCheckBox.Create(WizardForm.FinishedPage);
      StartManagerCheckbox.Parent := WizardForm.FinishedPage;
      StartManagerCheckbox.Left := ScaleX(220);
      StartManagerCheckbox.Top := ScaleY(140);
      StartManagerCheckbox.Width := 200;
      StartManagerCheckbox.Caption := 'Start Internet Manager now';
      StartManagerCheckbox.Checked := True; // Default to checked
    end;
  end;
end;


// -----------------------------------------------------------------------------
// Detect if it's an upgrade
// -----------------------------------------------------------------------------
function IsUpgradeInstall(): Boolean;
var
  InstallDir: string;
begin
  Result := False;
  if RegQueryStringValue(HKLM, 'Software\MyCompany\Internet Manager',
    'InstallPath', InstallDir) then
  begin
    if DirExists(InstallDir) then
      Result := True;
  end;
end;

// -----------------------------------------------------------------------------
// On ssInstall, generate config.json from fields, save, kill server if needed
// -----------------------------------------------------------------------------
procedure CurStepChanged(CurStep: TSetupStep);
var
  NewJson: String;
  ResultCode: Integer;
begin
  if CurStep = ssInstall then
  begin
    // If upgrading, kill existing server
    if IsUpgradeInstall() then
    begin
      Exec(ExpandConstant('{app}\{#MyAppUtilityExe}'), 'kill-server', '', SW_HIDE,
        ewWaitUntilTerminated, ResultCode);
    end;

    // Build new JSON from wizard fields
    NewJson := GenerateJsonFromWizardFields();

    // Save to {app}\config.json
    SaveJson(ExpandConstant('{commonappdata}\InternetManager\config.json'), NewJson);
  end
  else if CurStep = ssDone then
  begin
    // After installation is complete, handle the checkbox action
    if Assigned(StartManagerCheckbox) and StartManagerCheckbox.Checked then
    begin
      // Execute the server executable
      if Exec(ExpandConstant('{app}\{#MyAppServerExeName}'), '', '', SW_HIDE,
        ewNoWait, ResultCode) then
      begin
        // Optional: Inform the user that the server has started
        // MsgBox('Starting the server...', mbInformation, MB_OK);

        // Wait for 5 seconds before starting the main application
        Sleep(5000);

        // Execute the main application executable
        if Exec(ExpandConstant('{app}\{#MyAppExeName}'), '', '', SW_SHOW,
          ewNoWait, ResultCode) then
        begin
          // Optional: Inform the user that the application has started
          // MsgBox('Internet Manager has started.', mbInformation, MB_OK);
        end
        else
        begin
          // Handle execution failure if necessary
          MsgBox('Failed to start the Internet Manager application.', mbError, MB_OK);
        end;
      end
      else
      begin
        // Handle execution failure if necessary
        MsgBox('Failed to start the Internet Manager server.', mbError, MB_OK);
      end;
    end;
  end;
end;
