param(
    [string]$Python = "py -3"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$specPath = Join-Path $repoRoot "src\windows_app\launcher.spec"
$distDir = Join-Path $repoRoot "Dist\windows-exe"
$buildDir = Join-Path $repoRoot "build-pyinstaller"

Push-Location $repoRoot
try {
    & cmd /c "$Python -m pip install --upgrade pip"
    & cmd /c "$Python -m pip install -r requirements-windows-build.txt"

    $args = @(
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--distpath", $distDir,
        "--workpath", $buildDir
    )

    $args += $specPath
    & cmd /c "$Python $($args -join ' ')"
    Write-Output (Join-Path $distDir "SortingFilesWindows")
}
finally {
    Pop-Location
}
