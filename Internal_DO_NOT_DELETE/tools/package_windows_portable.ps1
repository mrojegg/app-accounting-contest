param(
    [string]$BundleRoot = "",
    [string]$ZipPath = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$buildScript = Join-Path $PSScriptRoot "build_windows_portable.ps1"
$defaultBundleRoot = Join-Path $repoRoot "Dist\windows-portable\SortingFilesWindowsCLI"
$resolvedBundleRoot = if ($BundleRoot) { $BundleRoot } else { $defaultBundleRoot }
$resolvedZipPath = if ($ZipPath) { $ZipPath } else { Join-Path $repoRoot "Dist\SortingFilesWindowsCLI.zip" }

if (-not (Test-Path $resolvedBundleRoot)) {
    & $buildScript -OutputRoot $resolvedBundleRoot | Out-Null
}

if (Test-Path $resolvedZipPath) {
    Remove-Item -Force $resolvedZipPath
}

Compress-Archive -Path (Join-Path $resolvedBundleRoot "*") -DestinationPath $resolvedZipPath
Write-Output $resolvedZipPath
