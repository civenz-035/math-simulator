<#
.SYNOPSIS
    dice — run the simulator without typing the full path.

.DESCRIPTION
    Wrapper so you can call:
        .\dice.ps1 -m 2 -r 1000
        .\dice.ps1 calc --balance 10000 --mul 2.0 --chance 4.95
        .\dice.ps1 -server

    This script declares NO param() block on purpose. With a param() block,
    PowerShell's own binder consumes "-balance" as "-b" + "alance" (and "-m" as
    a named parameter) before the script runs, which corrupts roll.py's long
    options. Keeping the parameter list empty means every token lands in $args
    untouched and can be forwarded verbatim.

    Set DICE_PYTHON to override the interpreter.

.EXAMPLE
    .\dice.ps1 -m 2 -r 1000
.EXAMPLE
    .\dice.ps1 calc --balance 10000 --mul 2.0 --chance 4.95
.EXAMPLE
    .\dice.ps1 -server
#>
$ErrorActionPreference = 'Continue'
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PyExe = if ($env:DICE_PYTHON) { $env:DICE_PYTHON } else { 'python' }

# `-server` is the only shortcut; everything else forwards to roll.py as-is.
if ($args.Count -eq 1 -and $args[0] -eq '-server') {
    & $PyExe (Join-Path $RepoRoot 'server\dice-server.py')
    exit $LASTEXITCODE
}

if ($args.Count -eq 0) { $args = @('-h') }

& $PyExe (Join-Path $RepoRoot 'bin\roll.py') @args
exit $LASTEXITCODE