[CmdletBinding()]
param(
    [string]$Destination = (Join-Path $env:USERPROFILE 'NEXUS_AI_ULTRA'),
    [string]$HermesRoot = (Join-Path $env:LOCALAPPDATA 'hermes\hermes-agent'),
    [string]$HermesHome,
    [string]$HermesPython
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Assert-ClosedNexus {
    if ($env:OS -eq 'Windows_NT') {
        $listeners = @(Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue)
        if ($listeners.Count) { throw 'Close NEXUS dashboard, floating AI and its server before installing. No process was stopped.' }
    }
}

function Get-SafePath([string]$Root, [string]$Relative) {
    if ([IO.Path]::IsPathRooted($Relative) -or $Relative.Contains('\') -or $Relative.Split('/') -contains '..') {
        throw 'Unsafe package path.'
    }
    $rootFull = [IO.Path]::GetFullPath($Root).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    $path = [IO.Path]::GetFullPath((Join-Path $Root $Relative))
    if (-not $path.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase)) { throw 'Package path escapes installation.' }
    $inspect = $path
    while ($inspect -and $inspect.Length -ge $rootFull.Length - 1) {
        if (Test-Path -LiteralPath $inspect) {
            if ((Get-Item -LiteralPath $inspect -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw 'Symlink/reparse installation paths are unsupported.'
            }
        }
        $inspect = Split-Path -Parent $inspect
    }
    return $path
}

function Get-HashOrNull([string]$Path) {
    if (Test-Path -LiteralPath $Path -PathType Leaf) { return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
    return $null
}

$Destination = [IO.Path]::GetFullPath($Destination)
$HermesRoot = [IO.Path]::GetFullPath($HermesRoot)
if (-not $HermesHome) { $HermesHome = Split-Path -Parent $HermesRoot }
$HermesHome = [IO.Path]::GetFullPath($HermesHome)
if (-not (Test-Path -LiteralPath (Join-Path $Destination 'nexus/app.py') -PathType Leaf)) { throw 'Choose your existing NEXUS installation.' }
if (-not (Test-Path -LiteralPath (Join-Path $HermesRoot 'run_agent.py') -PathType Leaf)) { throw 'Existing native Hermes installation not found. Nothing was installed.' }
Assert-ClosedNexus
$manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') -Raw | ConvertFrom-Json
if ($manifest.format -ne 2 -or $manifest.hermes_build -ne 'caafe5389ae585ef77387a962aee05b1bcf17029') { throw 'Unsupported integration package.' }
$candidates = @($manifest.files)
if (-not $candidates.Count) { throw 'Empty integration package.' }
$entries = @()
$seen = @{}
foreach ($entry in $candidates) {
    if ($seen.ContainsKey($entry.path)) { throw 'Duplicate package path.' }
    $seen[$entry.path] = $true
    $target = Get-SafePath $Destination $entry.path
    $actual = Get-HashOrNull $target
    $matches = @(@($entry) + @($entry.variants) | Where-Object { $_.previous_sha256 -eq $actual })
    if ($matches.Count -eq 0) {
        throw ('Existing file differs from the tested baseline: ' + $entry.path + '. Installation left unchanged.')
    }
    if ($matches.Count -ne 1) { throw 'Ambiguous package baseline.' }
    $selected = $matches[0]
    if ($selected.operation -notin @('replace','append')) { throw 'Unsupported package operation.' }
    if ($selected.operation -eq 'append' -and $entry.path -ne 'PROJECT_STATE.md') { throw 'Append is limited to project notes.' }
    $source = Get-SafePath (Join-Path $PSScriptRoot 'payload') $selected.source_path
    if ((Get-HashOrNull $source) -ne $selected.sha256) { throw ('Package hash mismatch: ' + $entry.path) }
    $entries += [pscustomobject]@{ path=$entry.path; previous_sha256=$selected.previous_sha256; sha256=$selected.sha256; source_path=$selected.source_path; operation=$selected.operation }
}
$nexusCandidates = @((Join-Path $Destination '.venv/Scripts/python.exe'), (Join-Path $Destination '.venv/bin/python'))
$nexusPython = @($nexusCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1)
if (-not $nexusPython.Count) { throw 'Existing NEXUS virtual environment not found.' }
$nexusPython = $nexusPython[0]
if (-not $HermesPython) {
    $candidates = @((Join-Path $HermesRoot 'venv/Scripts/python.exe'), (Join-Path $HermesRoot '.venv/Scripts/python.exe'))
    $toolsRoot = Join-Path $HermesHome 'tools'
    if (Test-Path -LiteralPath $toolsRoot -PathType Container) {
        $candidates += @(Get-ChildItem -LiteralPath $toolsRoot -Directory -Filter 'python-*' | ForEach-Object {
            Join-Path $_.FullName 'python.exe'
            Join-Path $_.FullName 'bin/python.exe'
        })
    }
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            $version = & $candidate -c 'import sys;print("%d.%d.%d" % sys.version_info[:3])'
            if ($LASTEXITCODE -eq 0 -and $version -eq '3.14.9') { $HermesPython = $candidate; break }
        }
    }
}
if (-not $HermesPython -or -not (Test-Path -LiteralPath $HermesPython -PathType Leaf)) {
    throw 'Existing Hermes Python 3.14.9 was not located. Retry with -HermesPython pointing to its installed interpreter. No packages were downloaded.'
}
$HermesPython = [IO.Path]::GetFullPath($HermesPython)
$stage = Join-Path ([IO.Path]::GetTempPath()) ('nexus-hermes-probe-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    $probeError = Join-Path $stage 'probe.stderr'
    $schemas = & $nexusPython -B -c 'import sys,json;sys.path.insert(0,sys.argv[1]);from nexus.tools import CATALOG;print(json.dumps([dict(type="function",function=dict(name=n,description=d,parameters=dict(type="object",properties={k:dict(type=v) for k,v in a.items()},required=list(a),additionalProperties=False))) for n,(d,_,a) in CATALOG.items()]))' $Destination
    if ($LASTEXITCODE -ne 0) { throw 'Existing NEXUS tool catalog could not be loaded. No files changed.' }
    $schemasPath = Join-Path $stage 'schemas.json'
    [IO.File]::WriteAllText($schemasPath, ($schemas -join "`n"), (New-Object System.Text.UTF8Encoding($false)))
    $schemaCount = @((($schemas -join "`n") | ConvertFrom-Json)).Count
    $savedPreference = $ErrorActionPreference
    try {
        # Windows PowerShell 5 treats native stderr as error records. Keep diagnostic
        # output private and judge this probe by its actual process exit status.
        $ErrorActionPreference = 'Continue'
        $probe = & $HermesPython -I -u (Join-Path $PSScriptRoot 'payload/nexus/hermes_worker.py') --root $HermesRoot --runtime-home $HermesHome --profile (Join-Path $stage 'profile') --schemas $schemasPath --probe 2> $probeError
        $probeExit = $LASTEXITCODE
    } finally { $ErrorActionPreference = $savedPreference }
    if ($probeExit -ne 0) { throw 'Hermes compatibility probe failed. NEXUS installation left unchanged.' }
    $ready = ($probe -join "`n") | ConvertFrom-Json
    if ($ready.type -ne 'ready' -or $ready.build -ne $manifest.hermes_build -or $ready.tools -ne $schemaCount) { throw 'Unexpected Hermes probe result.' }
    Assert-ClosedNexus
    $backup = $Destination + '.hermes-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,6)
    New-Item -ItemType Directory -Path $backup | Out-Null
    $prepared = Join-Path $stage 'prepared'
    New-Item -ItemType Directory -Path $prepared | Out-Null
    $records = @()
    foreach ($entry in $entries) {
        $target = Get-SafePath $Destination $entry.path
        if ((Get-HashOrNull $target) -ne $entry.previous_sha256) { throw 'Source changed during preflight. Nothing applied.' }
        if ($null -ne $entry.previous_sha256) {
            $saved = Get-SafePath $backup $entry.path
            New-Item -ItemType Directory -Path (Split-Path -Parent $saved) -Force | Out-Null
            Copy-Item -LiteralPath $target -Destination $saved
            if ((Get-HashOrNull $saved) -ne $entry.previous_sha256) { throw 'Source changed while saving backup. Nothing applied.' }
        }
        $source = Get-SafePath (Join-Path $PSScriptRoot 'payload') $entry.source_path
        $staged = Get-SafePath $prepared $entry.path
        New-Item -ItemType Directory -Path (Split-Path -Parent $staged) -Force | Out-Null
        if ($entry.operation -eq 'append') {
            $oldBytes = [IO.File]::ReadAllBytes($saved)
            $strictUtf8 = New-Object System.Text.UTF8Encoding($false,$true)
            [void]$strictUtf8.GetString($oldBytes)
            $addition = [IO.File]::ReadAllBytes($source)
            [IO.File]::WriteAllBytes($staged, [byte[]]($oldBytes + $addition))
        } else {
            Copy-Item -LiteralPath $source -Destination $staged
            if ((Get-HashOrNull $staged) -ne $entry.sha256) { throw 'Staged package hash mismatch.' }
        }
        $records += [pscustomobject]@{ path=$entry.path; previous_sha256=$entry.previous_sha256; sha256=(Get-HashOrNull $staged) }
    }
    $runtimePath = Get-SafePath $Destination 'hermes_runtime.json'
    $oldRuntimeHash = Get-HashOrNull $runtimePath
    if ($oldRuntimeHash) { Copy-Item -LiteralPath $runtimePath -Destination (Join-Path $backup 'hermes_runtime.json') }
    $runtimeText = @{ build=$manifest.hermes_build; python=$HermesPython; root=$HermesRoot; runtime_home=$HermesHome } | ConvertTo-Json
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllText((Join-Path $prepared 'hermes_runtime.json'), $runtimeText, $utf8)
    $records += [pscustomobject]@{ path='hermes_runtime.json'; previous_sha256=$oldRuntimeHash; sha256=(Get-HashOrNull (Join-Path $prepared 'hermes_runtime.json')) }
    $records | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $backup 'restore-manifest.json') -Encoding UTF8
    $applied = @()
    try {
        foreach ($record in $records) {
            $target = Get-SafePath $Destination $record.path
            if ((Get-HashOrNull $target) -ne $record.previous_sha256) { throw ('Concurrent edit retained: ' + $record.path) }
            $source = Get-SafePath $prepared $record.path
            New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
            $newPath = $target + '.nexus-hermes-' + [Guid]::NewGuid().ToString('N') + '.new'
            try {
                Copy-Item -LiteralPath $source -Destination $newPath
                Move-Item -LiteralPath $newPath -Destination $target -Force
            } finally {
                if (Test-Path -LiteralPath $newPath) { Remove-Item -LiteralPath $newPath }
            }
            $applied += $record
        }
        & $nexusPython -B -c 'import sys,os;sys.path.insert(0,sys.argv[1]);os.environ["NEXUS_DATA_DIR"]=sys.argv[2];import nexus.app as app;app.hermes.config();app.state();print("NEXUS Hermes configuration verified; app startup checked with isolated temporary data")' $Destination (Join-Path $stage 'postflight-data')
        if ($LASTEXITCODE -ne 0) { throw 'NEXUS post-install import/configuration check failed.' }
    } catch {
        $installFailure = $_
        foreach ($record in $applied) {
            $target = Get-SafePath $Destination $record.path
            if ((Get-HashOrNull $target) -ne $record.sha256) { Write-Warning ('Concurrent file change retained: ' + $record.path); continue }
            if ($null -ne $record.previous_sha256) { Copy-Item -LiteralPath (Get-SafePath $backup $record.path) -Destination $target -Force }
            else { Remove-Item -LiteralPath $target }
        }
        throw $installFailure
    }
    Write-Host 'Integrated: Hermes is the NEXUS main agent. Open your existing NEXUS desktop shortcut.' -ForegroundColor Green
    Write-Host ('Source backup: ' + $backup)
    Write-Host 'GUI, voice selection, database, credentials and provider settings were retained. No API request was made by this installer.'
} finally {
    # Only remove this installer's private temporary probe directory.
    if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
}
