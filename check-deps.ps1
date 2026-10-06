<#
.SYNOPSIS
    Reports whether dice-simulator's prerequisites are satisfied.

.DESCRIPTION
    Inspects and reports only. It never installs anything, never calls winget,
    and never needs elevated privileges. If something is missing it tells you
    what to do — you run the install yourself.

.EXAMPLE
    .\check-deps.ps1
#>
[CmdletBinding()]
param()

function Write-Ok   { param($m) Write-Host "  [ok]   $m" -ForegroundColor Green }
function Write-Need { param($m) Write-Host "  [need] $m" -ForegroundColor Yellow }

Write-Host ''
Write-Host 'dice-simulator - prerequisite check' -ForegroundColor Cyan
Write-Host ''

$Missing = $false

# ── PowerShell ──
Write-Ok "PowerShell $($PSVersionTable.PSVersion)"

# ── python >= 3.9 (PEP 585 annotations in roll.py) ──
$PyExe = $null
foreach ($cand in @('python', 'python3', 'py')) {
    $cmd = Get-Command $cand -ErrorAction SilentlyContinue
    if (-not $cmd) { continue }
    try {
        $ver = & $cmd.Source -c "import sys; print('.'.join(map(str,sys.version_info[:3])))" 2>$null
        $p = $ver.Trim().Split('.')
        if (([int]$p[0] -gt 3) -or ([int]$p[0] -eq 3 -and [int]$p[1] -ge 9)) {
            $PyExe = $cmd.Source
            Write-Ok "python $ver ($([System.IO.Path]::GetFileName($cmd.Source)))"
        } else {
            Write-Need "python $ver is older than 3.9 - the Python engine needs >= 3.9"
            $Missing = $true
        }
    } catch { }
}
if (-not $PyExe -and -not $Missing) {
    Write-Need 'python not found - the Python engine needs Python >= 3.9'
    $Missing = $true
}

Write-Host ''

if ($Missing) {
    Write-Host 'Some prerequisites are missing.' -ForegroundColor Yellow
    Write-Host ''
    Write-Host '  Suggested next steps (run these yourself if needed):'
    Write-Host '    winget install Python.Python.3.12'
    Write-Host '    winget install Git.Git'
    Write-Host ''
    Write-Host '  Verify with:  python --version'
} else {
    Write-Host 'All prerequisites are satisfied.' -ForegroundColor Green
}

Write-Host ''
Write-Host 'Usage once ready:'
Write-Host '  python bin\roll.py -m 2 -r 1000'
Write-Host '  .\dice.ps1 -server'
Write-Host ''

if ($Missing) { exit 1 }