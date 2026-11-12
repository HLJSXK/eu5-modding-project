# Run from this Mod workspace; the uploader is a local CLI dependency.
[CmdletBinding()]
param(
    [Parameter(Position = 0)][string]$Target,
    [switch]$List,
    [switch]$Init,
    [UInt64]$ItemId,
    [switch]$Upload,
    [string]$Executable = $env:PDX_WORKSHOP_MANAGER
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Resolve-WorkspacePath([string]$Path) {
    if ([IO.Path]::IsPathRooted($Path)) { return [IO.Path]::GetFullPath($Path) }
    return [IO.Path]::GetFullPath((Join-Path $PSScriptRoot $Path))
}

try {
    $manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'workshop-targets.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($List) {
        $manifest.targets | Select-Object name, directory | Format-Table -AutoSize
        exit 0
    }
    if (-not $Target) { $Target = $manifest.default }
    $matches = @($manifest.targets | Where-Object { $_.name -eq $Target })
    if ($matches.Count -ne 1) { throw "Unknown target '$Target'. Run .\workshop.ps1 -List." }
    $entry = $matches[0]
    # Use the manifest's name, never an arbitrary user path, for state files.
    $Target = $entry.name
    if ($Target -notmatch '^[a-z0-9_-]+$') { throw 'Invalid target name in manifest.' }
    if ($Init -and $Upload) { throw 'Use -Init and -Upload separately.' }
    if ($PSBoundParameters.ContainsKey('ItemId') -and -not $Init) { throw '-ItemId requires -Init.' }
    $state = Join-Path $PSScriptRoot '.workshop'
    $profilePath = Join-Path $state "$Target.json"
    if ($Init) {
        if ($ItemId -eq 0) { throw 'Specify the existing Workshop item ID with -ItemId (must be greater than zero).' }
        if (Test-Path -LiteralPath $profilePath) { throw "Profile already exists. Edit it explicitly to change the item ID: $profilePath" }
        $profile = [ordered]@{
            game = 3450310
            mods = @([ordered]@{
                id = $ItemId
                directory = $entry.directory
                thumbnail = '.metadata/thumbnail.png'
            })
        }
        New-Item -ItemType Directory -Path $state -Force | Out-Null
        [IO.File]::WriteAllText($profilePath, ($profile | ConvertTo-Json -Depth 10), [Text.UTF8Encoding]::new($false))
        Write-Host "Created profile: $profilePath"
    }
    if (-not (Test-Path -LiteralPath $profilePath -PathType Leaf)) {
        throw "Initialize once: .\workshop.ps1 $Target -Init -ItemId <your-existing-workshop-id>"
    }
    $config = Get-Content -LiteralPath $profilePath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($config.game -ne 3450310 -or @($config.mods).Count -ne 1) { throw 'Profile must contain exactly one EU5 Mod.' }
    $mod = $config.mods[0]
    if ([UInt64]$mod.id -eq 0) { throw 'Item ID 0 creates a new item and is not supported by this update wrapper.' }
    $mod.directory = Resolve-WorkspacePath $mod.directory
    $expectedDirectory = Resolve-WorkspacePath $entry.directory
    if ($mod.directory -ne $expectedDirectory) { throw "Profile content path must match target '$Target': $expectedDirectory" }
    $metadataPath = Join-Path $mod.directory '.metadata/metadata.json'
    $metadata = Get-Content -LiteralPath $metadataPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($metadata.game_id -ne 'eu5' -or $metadata.id -ne $entry.mod_id) { throw 'Metadata identity does not match this target.' }
    if ([string]::IsNullOrWhiteSpace($metadata.name) -or [string]::IsNullOrWhiteSpace($metadata.version)) { throw 'Metadata name/version must not be empty.' }
    $thumbnailPath = Join-Path $mod.directory $mod.thumbnail
    if (-not (Test-Path -LiteralPath $thumbnailPath -PathType Leaf)) { throw "Thumbnail missing: $thumbnailPath" }
    foreach ($field in @('descriptions', 'change-note-directories')) {
        if ($mod.PSObject.Properties.Name -contains $field) {
            foreach ($property in $mod.$field.PSObject.Properties) {
                $property.Value = Resolve-WorkspacePath $property.Value
                if ($field -eq 'descriptions') {
                    if (-not (Test-Path -LiteralPath $property.Value -PathType Leaf)) { throw "Description missing: $($property.Value)" }
                } else {
                    $note = Join-Path $property.Value ($metadata.version + '.bbcode')
                    if (-not (Test-Path -LiteralPath $note -PathType Leaf)) { Write-Warning "No change note for this version: $note" }
                }
            }
        }
    }
    Write-Host "Target:    $Target"
    Write-Host "Title:     $($metadata.name)"
    Write-Host "Version:   $($metadata.version)"
    Write-Host "Item ID:   $($mod.id)"
    Write-Host "Content:   $($mod.directory)"
    Write-Host "Thumbnail: $thumbnailPath"
    Write-Host "Profile:   $profilePath"
    if (-not $Executable) { $Executable = '.workshop/bin/pdx-workshop-manager.exe' }
    $Executable = Resolve-WorkspacePath $Executable
    $binaryExists = Test-Path -LiteralPath $Executable -PathType Leaf
    if (-not $Upload) {
        if (-not $binaryExists) { Write-Warning "CLI not installed: $Executable (see README)." }
        Write-Host 'Local profile checks passed. No upload performed. Build first, then use -Upload.'
        exit 0
    }
    if (-not $binaryExists) { throw "CLI not installed: $Executable" }
    if (-not (Test-Path -LiteralPath (Join-Path (Split-Path $Executable) 'steam_api64.dll') -PathType Leaf)) {
        throw 'steam_api64.dll must be beside the CLI executable.'
    }
    # The upstream CLI writes its config and steam_appid.txt in its working directory.
    # Keep both local to this workspace and preserve portable paths in the user's profile.
    $runDirectory = Join-Path $state ('runs/' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $runDirectory -Force | Out-Null
    $runConfig = Join-Path $runDirectory 'manager-config.json'
    [IO.File]::WriteAllText($runConfig, ($config | ConvertTo-Json -Depth 20), [Text.UTF8Encoding]::new($false))
    Push-Location $runDirectory
    try {
        $logPath = Join-Path $runDirectory 'upload.log'
        # Windows PowerShell turns redirected native stderr into ErrorRecords.
        # Steam writes harmless breakpad diagnostics there during initialization.
        $previousErrorPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            $PSNativeCommandUseErrorActionPreference = $false
            & $Executable -config $runConfig -mod ([string]$mod.id) 2>&1 |
                ForEach-Object { $_.ToString() } |
                Tee-Object -FilePath $logPath -ErrorAction Stop
            $uploadExit = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $previousErrorPreference
        }
        $log = Get-Content -LiteralPath $logPath -Raw
        # Upstream main.go can return 0 after an error: require its success marker too.
        if ($uploadExit -ne 0 -or $log -notmatch 'Upload successful') {
            throw "Upload failed or completion was not confirmed. Log: $logPath"
        }
    } finally { Pop-Location }
    Write-Host "Upload completed. Log: $logPath"
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
