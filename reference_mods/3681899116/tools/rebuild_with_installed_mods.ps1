param(
    [switch]$GuiOnly,
    [switch]$SkipCleanup
)

$ErrorActionPreference = "Stop"

function Get-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @{
            Command = "py"
            Prefix = @("-3")
        }
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @{
            Command = "python"
            Prefix = @()
        }
    }

    throw "Python 3 was not found. Install Python 3 and run this script again."
}

function Get-SteamLibraries {
    $steamCandidates = New-Object System.Collections.Generic.List[string]
    $registryPaths = @(
        "HKCU:\Software\Valve\Steam",
        "HKLM:\SOFTWARE\WOW6432Node\Valve\Steam",
        "HKLM:\SOFTWARE\Valve\Steam"
    )

    foreach ($registryPath in $registryPaths) {
        if (Test-Path $registryPath) {
            $steamPath = (Get-ItemProperty $registryPath -ErrorAction SilentlyContinue).SteamPath
            if ($steamPath) {
                $steamCandidates.Add($steamPath)
            }
        }
    }

    if ($env:ProgramFiles) {
        $steamCandidates.Add((Join-Path $env:ProgramFiles "Steam"))
    }
    if (${env:ProgramFiles(x86)}) {
        $steamCandidates.Add((Join-Path ${env:ProgramFiles(x86)} "Steam"))
    }

    $libraries = New-Object System.Collections.Generic.List[string]
    foreach ($steamPath in ($steamCandidates | Select-Object -Unique)) {
        if (-not $steamPath) {
            continue
        }

        $libraries.Add($steamPath)
        $libraryFile = Join-Path $steamPath "steamapps\libraryfolders.vdf"
        if (-not (Test-Path $libraryFile)) {
            continue
        }

        $content = Get-Content $libraryFile -Raw -ErrorAction SilentlyContinue
        if (-not $content) {
            continue
        }

        foreach ($match in [regex]::Matches($content, '"path"\s*"([^"]+)"')) {
            $pathValue = $match.Groups[1].Value -replace "\\\\", "\"
            if ($pathValue) {
                $libraries.Add($pathValue)
            }
        }
    }

    return $libraries | Select-Object -Unique
}

function Find-GameRoot {
    foreach ($library in Get-SteamLibraries) {
        $candidate = Join-Path $library "steamapps\common\Europa Universalis V"
        if (Test-Path (Join-Path $candidate "game\in_game\events")) {
            return $candidate
        }
    }

    throw "Europa Universalis V could not be found automatically in your Steam libraries."
}

function Invoke-PythonScript {
    param(
        [hashtable]$PythonInfo,
        [string]$ScriptPath,
        [string[]]$Arguments = @()
    )

    Write-Host ""
    Write-Host "Running $([System.IO.Path]::GetFileName($ScriptPath))"
    & $PythonInfo.Command @($PythonInfo.Prefix + @($ScriptPath) + $Arguments)
    if ($LASTEXITCODE -ne 0) {
        throw "$([System.IO.Path]::GetFileName($ScriptPath)) failed with exit code $LASTEXITCODE."
    }
}

$toolsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$modRoot = Split-Path -Parent $toolsRoot
$python = Get-PythonCommand
$gameRoot = Find-GameRoot
$gameLocRoot = Join-Path $gameRoot "game\main_menu\localization"
$registryStatusPath = Join-Path $modRoot "data\registry_build_status.json"

Set-Location $modRoot

Write-Host "Unique Events Tab rebuild"
Write-Host "Mod folder: $modRoot"
Write-Host "Game root: $gameRoot"
Write-Host "Python: $($python.Command) $($python.Prefix -join ' ')"
if ($GuiOnly) {
    Write-Host "Mode: GUI only"
} elseif ($SkipCleanup) {
    Write-Host "Mode: full rebuild (skip cleanup)"
}

if (-not $GuiOnly) {
    Invoke-PythonScript $python (Join-Path $toolsRoot "generate_registry.py") @("--game-root", $gameRoot)
    $registryChanged = $true
    if (Test-Path $registryStatusPath) {
        try {
            $registryStatus = Get-Content $registryStatusPath -Raw | ConvertFrom-Json
            if ($null -ne $registryStatus.changed) {
                $registryChanged = [bool]$registryStatus.changed
            }
        } catch {
            $registryChanged = $true
        }
    }

    Invoke-PythonScript $python (Join-Path $toolsRoot "generate_fired_tracking_overrides.py") @("--game-root", $gameRoot)

    Invoke-PythonScript $python (Join-Path $toolsRoot "generate_country_events_gui.py") @("--game-root", $gameRoot)
    if ($registryChanged) {
        Invoke-PythonScript $python (Join-Path $toolsRoot "audit_country_transitions.py") @("--game-root", $gameRoot)
    }
    if ($registryChanged) {
        Invoke-PythonScript $python (Join-Path $toolsRoot "generate_country_events_loc.py")
    }
    if ($registryChanged -and -not $SkipCleanup) {
        Invoke-PythonScript $python (Join-Path $toolsRoot "cleanup_auto_loc.py") @("--game-loc", $gameLocRoot)
    } elseif (-not $registryChanged) {
        Write-Host ""
        Write-Host "Registry unchanged: kept fired-status script values and GUI in sync."
    }
} else {
    Invoke-PythonScript $python (Join-Path $toolsRoot "generate_country_events_gui.py") @("--game-root", $gameRoot)
}

Write-Host ""
Write-Host "Done. The mod was rebuilt with the events from the installed mods that were detected."
