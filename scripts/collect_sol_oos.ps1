# Windows PowerShell 5.1+; read-only collection of game data. Does not upload anything.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateSet('host','client')][string]$Role,
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9_-]+$')][string]$Session,
    [Parameter(Mandatory=$true)][string]$ModPath,
    [string]$UserDataPath = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Paradox Interactive\Europa Universalis V'),
    [string]$OutputRoot = (Join-Path $PSScriptRoot 'reports'),
    [string]$GameVersion = '',
    [string]$GameChecksum = '',
    [string]$Language = '',
    [string[]]$SaveFile = @(),
    [string[]]$ExtraFile = @(),
    [string]$Notes = ''
)
$ErrorActionPreference = 'Stop'
$warnings = [System.Collections.Generic.List[string]]::new()
$utf8 = [System.Text.UTF8Encoding]::new($false)
function Get-Sha256([string]$FilePath) {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($FilePath)
    try { return ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
    finally { $stream.Dispose(); $algorithm.Dispose() }
}
$gameRoot = (Resolve-Path -LiteralPath $UserDataPath).Path
$modRoot = (Resolve-Path -LiteralPath $ModPath).Path
$outputFull = [IO.Path]::GetFullPath($OutputRoot)
foreach ($sourceRoot in @($gameRoot, $modRoot)) {
    if ($outputFull.TrimEnd('\') -eq $sourceRoot.TrimEnd('\') -or $outputFull.StartsWith($sourceRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'OutputRoot must be outside the game-data and mod directories.'
    }
}
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$reportPath = Join-Path $outputFull ($Session + '-' + $Role + '-' + $stamp)
if (Test-Path -LiteralPath $reportPath) { throw 'Report directory already exists.' }
New-Item -ItemType Directory -Path $reportPath -Force | Out-Null

function Copy-EvidenceTree([string]$SourcePath, [string]$DestinationPath) {
    New-Item -ItemType Directory -Path $DestinationPath -Force | Out-Null
    foreach ($item in Get-ChildItem -LiteralPath $SourcePath -Force) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            $warnings.Add('Skipped linked evidence: ' + $item.FullName)
        } elseif ($item.PSIsContainer) {
            Copy-EvidenceTree $item.FullName (Join-Path $DestinationPath $item.Name)
        } else {
            try { Copy-Item -LiteralPath $item.FullName -Destination (Join-Path $DestinationPath $item.Name) }
            catch { $warnings.Add('Could not copy ' + $item.FullName + ': ' + $_.Exception.Message) }
        }
    }
}

foreach ($folderName in @('logs','oos')) {
    $sourcePath = Join-Path $gameRoot $folderName
    if (Test-Path -LiteralPath $sourcePath -PathType Container) {
        Copy-EvidenceTree $sourcePath (Join-Path $reportPath $folderName)
    } else { $warnings.Add('Missing evidence folder: ' + $sourcePath) }
}
$modFiles = [System.Collections.Generic.List[object]]::new()
function Hash-ModTree([string]$FolderPath) {
    foreach ($item in Get-ChildItem -LiteralPath $FolderPath -Force | Sort-Object Name) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            $warnings.Add('Skipped linked mod path: ' + $item.FullName)
        } elseif ($item.PSIsContainer) { Hash-ModTree $item.FullName }
        elseif ($item.Name -ne 'sol_oos_build.json') {
            $relative = $item.FullName.Substring($modRoot.TrimEnd('\').Length + 1).Replace('\','/')
            $modFiles.Add([ordered]@{path=$relative; sha256=(Get-Sha256 $item.FullName); size=$item.Length})
        }
    }
}
Hash-ModTree $modRoot
$buildVerified = $false
$buildPath = Join-Path $modRoot 'sol_oos_build.json'
if (Test-Path -LiteralPath $buildPath) {
    Copy-Item -LiteralPath $buildPath -Destination (Join-Path $reportPath 'sol_oos_build.json')
    $build = Get-Content -LiteralPath $buildPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $expected = @{}
    foreach ($entry in $build.files) { $expected[$entry.path] = $entry.sha256 }
    $buildVerified = ($expected.Count -eq $modFiles.Count)
    foreach ($entry in $modFiles) {
        if ($expected[$entry.path] -ne $entry.sha256) { $buildVerified = $false }
    }
    if (-not $buildVerified) { $warnings.Add('Observed mod files do not match the build manifest.') }
} else { $warnings.Add('No diagnostic build manifest at ModPath.') }
$extraManifest = @()
$index = 0
foreach ($inputFile in @($SaveFile) + @($ExtraFile)) {
    $resolvedFile = Get-Item -LiteralPath $inputFile
    if ($resolvedFile.PSIsContainer -or ($resolvedFile.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'SaveFile/ExtraFile must be regular files.' }
    $relative = 'attachments/' + $index + '-' + $resolvedFile.Name
    $attachmentRoot = Join-Path $reportPath 'attachments'
    New-Item -ItemType Directory -Path $attachmentRoot -Force | Out-Null
    Copy-Item -LiteralPath $resolvedFile.FullName -Destination (Join-Path $reportPath $relative)
    $extraManifest += [ordered]@{path=$relative; sha256=(Get-Sha256 (Join-Path $reportPath $relative))}
    $index++
}
$manifest = [ordered]@{
    schema=1; role=$Role; session=$Session; collected_utc=[DateTime]::UtcNow.ToString('o');
    game_version=$GameVersion; game_checksum=$GameChecksum; language=$Language; notes=$Notes;
    game_data_path=$gameRoot; mod_path=$modRoot; build_verified=$buildVerified;
    mod_files=@($modFiles.ToArray()); attachments=@($extraManifest); warnings=@($warnings.ToArray());
    limitations='ModPath hashes only the supplied SOL folder; it does not prove the game loaded it or verify other mods. Logs copied during play may be incomplete. OOS folder includes all available incidents.'
}
[IO.File]::WriteAllText((Join-Path $reportPath 'collection.json'), ($manifest | ConvertTo-Json -Depth 8), $utf8)
# ZipFile includes hidden evidence files; Compress-Archive can omit them.
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zipPath = $reportPath + '.zip'
[IO.Compression.ZipFile]::CreateFromDirectory($reportPath, $zipPath)
Write-Output ('Report: ' + $zipPath)
foreach ($warning in $warnings) { Write-Warning $warning }
