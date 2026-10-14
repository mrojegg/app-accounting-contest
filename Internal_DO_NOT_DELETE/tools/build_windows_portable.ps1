param(
    [string]$OutputRoot = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$distRoot = Join-Path $repoRoot "Dist\windows-portable"
$bundleRoot = if ($OutputRoot) { $OutputRoot } else { Join-Path $distRoot "SortingFilesWindowsCLI" }

if (Test-Path $bundleRoot) {
    Remove-Item -Recurse -Force $bundleRoot
}

New-Item -ItemType Directory -Force -Path $bundleRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $bundleRoot "Internal_DO_NOT_DELETE") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $bundleRoot "src") | Out-Null

Copy-Item -Recurse -Force (Join-Path $repoRoot "Internal_DO_NOT_DELETE\scripts") (Join-Path $bundleRoot "Internal_DO_NOT_DELETE")
Copy-Item -Recurse -Force (Join-Path $repoRoot "Internal_DO_NOT_DELETE\project_rules") (Join-Path $bundleRoot "Internal_DO_NOT_DELETE")
Copy-Item -Recurse -Force (Join-Path $repoRoot "src\windows_app") (Join-Path $bundleRoot "src")
Copy-Item -Force (Join-Path $repoRoot "README.md") $bundleRoot
Copy-Item -Force (Join-Path $repoRoot "requirements-windows.txt") $bundleRoot
Copy-Item -Force (Join-Path $repoRoot "requirements-windows-build.txt") $bundleRoot

$docsDir = Join-Path $bundleRoot "docs"
New-Item -ItemType Directory -Force -Path $docsDir | Out-Null
Copy-Item -Force (Join-Path $repoRoot "docs\windows-development.md") $docsDir

$runPipelineCmd = @'
@echo off
setlocal
set "ROOT=%~dp0"
py -3 "%ROOT%Internal_DO_NOT_DELETE\scripts\run_sorting_pipeline.py" %*
'@
Set-Content -Path (Join-Path $bundleRoot "run_sorting_pipeline.cmd") -Value $runPipelineCmd -Encoding ASCII

$validateCmd = @'
@echo off
setlocal
set "ROOT=%~dp0"
py -3 "%ROOT%Internal_DO_NOT_DELETE\scripts\validate_windows_export.py" %*
'@
Set-Content -Path (Join-Path $bundleRoot "validate_windows_export.cmd") -Value $validateCmd -Encoding ASCII

$installCmd = @'
@echo off
setlocal
set "ROOT=%~dp0"
py -3 -m pip install -r "%ROOT%requirements-windows.txt"
'@
Set-Content -Path (Join-Path $bundleRoot "install_python_deps.cmd") -Value $installCmd -Encoding ASCII

$runLauncherCmd = @'
@echo off
setlocal
set "ROOT=%~dp0"
py -3 "%ROOT%src\windows_app\launcher.py"
'@
Set-Content -Path (Join-Path $bundleRoot "run_windows_launcher.cmd") -Value $runLauncherCmd -Encoding ASCII

Write-Output $bundleRoot
