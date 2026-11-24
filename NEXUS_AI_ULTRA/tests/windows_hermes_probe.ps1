param([Parameter(Mandatory=$true)][string]$Python,
      [Parameter(Mandatory=$true)][string]$Helper,
      [Parameter(Mandatory=$true)][string]$Scratch)
$ErrorActionPreference='Stop'
if ($PSVersionTable.PSVersion.Major -ne 5) { throw 'This check requires native Windows PowerShell 5.1.' }
$utf8=New-Object System.Text.UTF8Encoding($false)
$root=Join-Path $Scratch 'helper paths with spaces'
$installation=Join-Path $root 'installed source with spaces'
$package=Join-Path $installation 'nexus'
New-Item -ItemType Directory -Path $package -Force | Out-Null
$copiedHelper=Join-Path $root 'installer helper with spaces.py'
Copy-Item -LiteralPath $Helper -Destination $copiedHelper
[IO.File]::WriteAllText((Join-Path $package '__init__.py'), '', $utf8)
$tools=@'
CATALOG = {'probe': ('A label with "quoted" text', False, {'value':'string'})}
'@
[IO.File]::WriteAllText((Join-Path $package 'tools.py'), $tools, $utf8)
$app=@'
import os
from pathlib import Path
class Agent:
    def config(self):
        return {'fixture': True}
hermes = Agent()
def state():
    data = Path(os.environ['NEXUS_DATA_DIR'])
    assert data.name == 'isolated data with spaces'
    data.mkdir(parents=True, exist_ok=True)
    (data / 'checked.txt').write_text('checked', encoding='utf-8')
    return {'fixture': True}
'@
[IO.File]::WriteAllText((Join-Path $package 'app.py'), $app, $utf8)

# A failing old-style control confirms this runner exercises the reported mode.
$saved=$ErrorActionPreference
try {
    $ErrorActionPreference='Continue'
    $ignored=& $Python -c 'import sys;print("%d.%d.%d" % sys.version_info[:3])' 2> (Join-Path $root 'old-probe.stderr')
    $oldExit=$LASTEXITCODE
} finally { $ErrorActionPreference=$saved }
if ($oldExit -eq 0) { throw 'Old inline quoting failure was not reproduced.' }

$version=& $Python -B $copiedHelper version
if ($LASTEXITCODE -ne 0 -or $version -notmatch '^\d+\.\d+\.\d+$') { throw 'File-based version check failed.' }
$output=Join-Path $root 'schema output with spaces.json'
& $Python -B $copiedHelper schemas --installation $installation --output $output
if ($LASTEXITCODE -ne 0) { throw 'File-based schema check failed.' }
$schemas=Get-Content -LiteralPath $output -Raw | ConvertFrom-Json
if ($schemas[0].function.description -ne 'A label with "quoted" text') { throw 'Schema quoted text was altered.' }
$data=Join-Path $root 'isolated data with spaces'
& $Python -B $copiedHelper check-app --installation $installation --data $data
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $data 'checked.txt'))) { throw 'File-based startup check failed.' }
Write-Output 'PASS: native Windows PowerShell 5.1 version/schema/startup helper checks; old quoting failure reproduced.'
