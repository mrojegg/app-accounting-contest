# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_root = Path.cwd()
datas = [
    (str(project_root / "Internal_DO_NOT_DELETE"), "Internal_DO_NOT_DELETE"),
]

hiddenimports = [
    "run_sorting_pipeline",
    "sort_documents",
    "build_salary_tables",
    "build_tax_distribution",
    "build_tax_distribution_demo_b",
    "build_tax_distribution_generic",
    "build_insurance_distribution",
    "build_insurance_distribution_demo_b",
    "build_insurance_distribution_generic",
    "build_commission_table",
]

a = Analysis(
    ["src/windows_app/launcher.py"],
    pathex=[
        str(project_root),
        str(project_root / "Internal_DO_NOT_DELETE" / "scripts"),
    ],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SortingFilesWindows",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
