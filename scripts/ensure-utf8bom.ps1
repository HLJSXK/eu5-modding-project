# ensure-utf8bom.ps1
# Scans all .yml and .txt files under the given path and rewrites any that are
# missing the UTF-8 BOM signature (EF BB BF).  EU5 / Jomini requires BOM on
# both file types; files without it silently produce broken in-game text.
#
# Usage:
#   .\scripts\ensure-utf8bom.ps1                  # fix all .yml under repo root
#   .\scripts\ensure-utf8bom.ps1 -Path src\stable  # fix a specific subtree
#   .\scripts\ensure-utf8bom.ps1 -DryRun           # report only, no writes

param(
    [string]$Path = (Split-Path $PSScriptRoot -Parent),
    [switch]$DryRun
)

$bomBytes   = [byte[]]@(0xEF, 0xBB, 0xBF)
$enc_no_bom = [System.Text.UTF8Encoding]::new($false)
$enc_bom    = [System.Text.UTF8Encoding]::new($true)

$fixed  = 0
$ok     = 0
$errors = 0

Get-ChildItem -Path $Path -Recurse -File | Where-Object { $_.Extension -in '.yml', '.txt' } | ForEach-Object {
    $file = $_
    try {
        $raw = [System.IO.File]::ReadAllBytes($file.FullName)
        $hasBOM = ($raw.Length -ge 3 -and
                   $raw[0] -eq 0xEF -and
                   $raw[1] -eq 0xBB -and
                   $raw[2] -eq 0xBF)

        if ($hasBOM) {
            $ok++
        } else {
            if ($DryRun) {
                Write-Host "[NEEDS BOM] $($file.FullName)"
            } else {
                $text = [System.IO.File]::ReadAllText($file.FullName, $enc_no_bom)
                [System.IO.File]::WriteAllText($file.FullName, $text, $enc_bom)
                Write-Host "[FIXED]     $($file.Name)"
            }
            $fixed++
        }
    } catch {
        Write-Host "[ERROR]     $($file.FullName): $_"
        $errors++
    }
}

Write-Host ""
if ($DryRun) {
    Write-Host "[DONE] Dry-run complete. $fixed file(s) need BOM, $ok already correct, $errors error(s)."
} else {
    Write-Host "[DONE] $fixed file(s) fixed, $ok already correct, $errors error(s)."
}

if ($errors -gt 0) { exit 1 }
exit 0
