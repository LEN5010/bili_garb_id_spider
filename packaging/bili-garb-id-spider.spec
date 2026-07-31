from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata


project_root = Path(SPECPATH).parent
bili_datas, bili_binaries, bili_hiddenimports = collect_all("bilibili_api")
bili_datas += copy_metadata("bilibili-api-python", recursive=True)

analysis = Analysis(
    [str(project_root / "run.py")],
    pathex=[str(project_root)],
    binaries=bili_binaries,
    datas=bili_datas,
    hiddenimports=bili_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "pytest_asyncio"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="bili-garb-id-spider",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

bundle = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="bili-garb-id-spider",
)
