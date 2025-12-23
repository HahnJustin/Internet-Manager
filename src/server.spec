# -*- mode: python ; coding: utf-8 -*-
import os
# from PyInstaller.utils.hooks import collect_submodules

HERE = os.path.abspath(SPECPATH)   # folder containing this spec
SRC  = HERE                        # if server.spec is inside src/

a = Analysis(
    ['server.py'],
    pathex=[SRC],
    binaries=[],
    datas=[
        ('assets/*', 'assets'),
    ],
    hiddenimports=[
        # 'libserver',  # usually not needed if pathex is right, but harmless
        # *collect_submodules('libserver'),
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='internet_manager_server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # <-- turn on console for debugging server
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/globe_server.ico'
)
