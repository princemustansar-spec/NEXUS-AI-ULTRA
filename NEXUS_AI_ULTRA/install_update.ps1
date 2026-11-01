[CmdletBinding()]
param(
    [string]$Destination,
    [string]$Revision = 'main',
    [string]$ArchivePath,
    [switch]$Rollback,
    [string]$BackupPath
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
if (-not $Destination) {
    $candidates = @((Get-Location).Path, 'C:\NEXUS_AI_ULTRA', (Join-Path $env:USERPROFILE 'NEXUS_AI_ULTRA')) |
        Where-Object { (Test-Path (Join-Path $_ 'run.py')) -and (Test-Path (Join-Path $_ 'nexus\app.py')) } |
        ForEach-Object { [IO.Path]::GetFullPath($_) } | Select-Object -Unique
    $candidates = @($candidates)
    if ($candidates.Count -gt 1) { throw 'Multiple NEXUS installations found. Rerun with -Destination pointing to the installation you want to update.' }
    $Destination = if ($candidates.Count -eq 1) { $candidates[0] } else { Join-Path $env:USERPROFILE 'NEXUS_AI_ULTRA' }
}
$Destination = [IO.Path]::GetFullPath($Destination)
$parent = Split-Path -Parent $Destination
if ($Destination -eq [IO.Path]::GetPathRoot($Destination)) { throw 'Choose a project directory, not a drive root.' }
if (Test-Path -LiteralPath $Destination) {
    if ((Get-Item -LiteralPath $Destination).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Symlink/reparse destinations are unsupported.' }
}
function Assert-NoRunningNexus {
    # Refuse instead of terminating processes or copying open user databases.
    $running = Get-CimInstance Win32_Process | Where-Object {
        ($_.Name -match '^(pythonw?|NEXUS_AI_ULTRA)\.exe$') -and
        (($_.ExecutablePath -and $_.ExecutablePath.StartsWith($Destination + '\',[StringComparison]::OrdinalIgnoreCase)) -or
         ($_.CommandLine -and $_.CommandLine.Contains($Destination)))
    }
    if ($running) { throw 'Close NEXUS and its console before updating or rolling back.' }
}
function Preserve-CurrentData([string]$From, [string]$To, $Managed) {
    $known = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    foreach ($name in $Managed) { [void]$known.Add([string]$name) }
    $directories = New-Object 'System.Collections.Generic.Stack[string]'
    $directories.Push($From)
    while ($directories.Count -gt 0) {
        foreach ($file in Get-ChildItem -LiteralPath $directories.Pop() -Force) {
            if ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
            $relative = $file.FullName.Substring($From.Length + 1).Replace('\','/')
            if ($relative -match '^(\.venv|\.git|dist|build)(/|$)' -or $relative -eq '.nexus-update-backup.json') { continue }
            if ($file.PSIsContainer) { $directories.Push($file.FullName); continue }
            if (-not $known.Contains($relative)) {
                $target = Join-Path $To $relative
                New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
                Copy-Item -LiteralPath $file.FullName -Destination $target -Force
            }
        }
    }
}
Assert-NoRunningNexus
if ($Rollback) {
    if (-not $BackupPath) { throw 'Supply -BackupPath from the successful update receipt.' }
    $BackupPath = [IO.Path]::GetFullPath($BackupPath)
    if ((Split-Path -Parent $BackupPath) -ne $parent -or -not (Test-Path (Join-Path $BackupPath '.nexus-update-backup.json'))) { throw 'Not a recognized sibling NEXUS backup.' }
    $receipt = Get-Content (Join-Path $BackupPath '.nexus-update-backup.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($receipt.destination -ne $Destination) { throw 'Backup belongs to a different installation.' }
    $saved = $Destination + '.before-rollback-' + [Guid]::NewGuid().ToString('N')
    if (Test-Path $Destination) { Move-Item -LiteralPath $Destination -Destination $saved }
    try {
        Move-Item -LiteralPath $BackupPath -Destination $Destination
        if (Test-Path $saved) { Preserve-CurrentData $saved $Destination $receipt.managed }
    }
    catch {
        if (Test-Path $Destination) { Move-Item -LiteralPath $Destination -Destination ($Destination + '.rollback-incomplete-' + [Guid]::NewGuid().ToString('N')) }
        if (Test-Path $saved) { Move-Item -LiteralPath $saved -Destination $Destination }
        throw
    }
    Write-Host "Rollback complete. Previous updated folder retained at $saved. User data outside the project was untouched."
    exit 0
}
$temp = Join-Path ([IO.Path]::GetTempPath()) ('nexus-update-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temp | Out-Null
$backup = $null
$applied = $false
$hadDestination = Test-Path -LiteralPath $Destination
try {
    if (-not $ArchivePath) {
        if ($Revision -notmatch '^[A-Za-z0-9_./-]+$' -or $Revision.Contains('..')) { throw 'Invalid revision.' }
        $ArchivePath = Join-Path $temp 'source.zip'
        $url = 'https://github.com/princemustansar-spec/jarvis/archive/' + $Revision + '.zip'
        Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $ArchivePath
    }
    $unpack = Join-Path $temp 'unpack'
    # Check archive entries before extracting to prevent path traversal.
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead([IO.Path]::GetFullPath($ArchivePath))
    try {
        foreach ($entry in $zip.Entries) {
            $parts = $entry.FullName.Replace('\','/').Split('/')
            if ($entry.FullName.Contains(':') -or $parts -contains '..' -or $entry.FullName -match '^[\\/]|^[A-Za-z]:') { throw 'Unsafe archive path.' }
        }
    } finally { $zip.Dispose() }
    Expand-Archive -LiteralPath $ArchivePath -DestinationPath $unpack
    $roots = @(Get-ChildItem $unpack -Directory)
    if ($roots.Count -ne 1) { throw 'Unexpected source archive layout.' }
    $source = Join-Path $roots[0].FullName 'NEXUS_AI_ULTRA'
    foreach ($required in @('run.py','requirements.txt','requirements-voice.txt','static\index.html','nexus\voice.py')) {
        if (-not (Test-Path (Join-Path $source $required))) { throw "Archive missing $required" }
    }
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    if ($hadDestination) {
        # Copy the complete old folder, including .venv, before making any change.
        $backup = $Destination + '.backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8)
        New-Item -ItemType Directory -Path $backup | Out-Null
        $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
        & icacls $backup /inheritance:r /grant:r "*${sid}:(OI)(CI)F" | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Could not secure backup permissions; update aborted.' }
        & robocopy $Destination $backup /E /COPY:DAT /DCOPY:DAT /XJ /R:1 /W:1 /NFL /NDL /NP | Out-Null
        if ($LASTEXITCODE -ge 8) { throw 'Backup failed; update aborted before modifying the installation.' }
        $managed = @(Get-ChildItem -LiteralPath $source -File -Recurse | ForEach-Object { $_.FullName.Substring($source.Length + 1).Replace('\','/') })
        @{ destination=$Destination; revision=$Revision; created=(Get-Date).ToString('o'); managed=$managed } | ConvertTo-Json | Set-Content (Join-Path $backup '.nexus-update-backup.json') -Encoding UTF8
    }
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    $applied = $true
    # Overlay source only; never mirror/delete unknown user files or replace env/data.
    & robocopy $source $Destination /E /COPY:DAT /XJ /R:1 /W:1 /XD .git .venv __pycache__ .pytest_cache dist build voice-models /XF .env .env.* *.sqlite3* *.db *.log *.wav *.mp3 *.key *.pem /NFL /NDL /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw 'Source copy failed.' }
    $python = Join-Path $Destination '.venv\Scripts\python.exe'
    if (-not (Test-Path $python)) {
        & py -3.12 -m venv (Join-Path $Destination '.venv')
        if ($LASTEXITCODE -ne 0) { & py -3.11 -m venv (Join-Path $Destination '.venv') }
        if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.11 or 3.12 x64, then retry.' }
    }
    & $python -c 'import sys,struct; sys.exit(0 if sys.version_info[:2] in ((3,11),(3,12)) and struct.calcsize(chr(80))==8 else 1)'
    if ($LASTEXITCODE -ne 0) { throw 'The existing venv needs Python 3.11/3.12 x64; it was not deleted.' }
    & $python -m pip install -r (Join-Path $Destination 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    & $python -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Dependency check failed.' }
    & $python -m compileall -q (Join-Path $Destination 'nexus') (Join-Path $Destination 'run.py')
    if ($LASTEXITCODE -ne 0) { throw 'Source syntax check failed.' }
    # Avoid launching a stale portable build after updating Python source.
    $launcher = Join-Path $Destination 'START_UPDATED_NEXUS.bat'
    @('@echo off','cd /d "%~dp0"','start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0run.py"') | Set-Content $launcher -Encoding ASCII
    try {
        $linkPath = Join-Path ([Environment]::GetFolderPath('Desktop')) 'NEXUS AI ULTRA.lnk'
        if ((Test-Path $linkPath) -and $backup) { Copy-Item -LiteralPath $linkPath -Destination (Join-Path $backup 'previous-desktop-shortcut.lnk') }
        $shell = New-Object -ComObject WScript.Shell
        $link = $shell.CreateShortcut($linkPath)
        $link.TargetPath = Join-Path $Destination '.venv\Scripts\pythonw.exe'
        $link.Arguments = '"' + (Join-Path $Destination 'run.py') + '"'
        $link.WorkingDirectory = $Destination
        $link.Save()
    } catch { Write-Warning 'Desktop shortcut update failed; use START_UPDATED_NEXUS.bat.' }
    Write-Host "Updated. Desktop shortcut points to this updated source. Its start mode follows Floating AI settings. Launch $launcher if needed."
    if ($backup) { Write-Host "Backup: $backup"; Write-Host "Rollback: powershell -NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Destination `"$Destination`" -Rollback -BackupPath `"$backup`"" }
    Write-Host 'SQLite, models, user files and OS credential storage were not deleted or uploaded.'
} catch {
    if ($applied -and $backup -and (Test-Path $backup)) {
        $failed = $Destination + '.failed-' + [Guid]::NewGuid().ToString('N')
        Move-Item -LiteralPath $Destination -Destination $failed
        & robocopy $backup $Destination /E /COPY:DAT /DCOPY:DAT /XJ /R:1 /W:1 /NFL /NDL /NP | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "Update failed and automatic restore failed. Complete backup is at $backup; changed folder at $failed." }
        $receipt = Get-Content (Join-Path $backup '.nexus-update-backup.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        Preserve-CurrentData $failed $Destination $receipt.managed
        Write-Warning "Original installation restored. Failed update retained at $failed."
    }
    throw
} finally { if (Test-Path $temp) { Remove-Item -LiteralPath $temp -Recurse -Force } }
