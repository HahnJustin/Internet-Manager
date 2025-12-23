# -*- mode: python ; coding: utf-8 -*-
import os

HERE = os.path.abspath(SPECPATH)   # folder containing this spec (your /src)
pathex = [HERE]

a = Analysis(
    ['gui.py'],                    # <-- NOT src/gui.py
    pathex=pathex,
    binaries=[],
    datas=[
        (os.path.join(HERE, 'assets'), 'assets'),
        (os.path.join(HERE, 'fonts'), 'fonts'),
    ],
    hiddenimports=[],
    hookspath=[],
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
    name='internet_manager',
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
    icon=os.path.join(HERE, 'assets', 'globe.ico'),
)
