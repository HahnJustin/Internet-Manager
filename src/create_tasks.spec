# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['create_tasks.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['win32com', 'win32com.client', 'pyuac'],
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
    name='create_tasks.exe',
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
    icon='assets/bell.ico'
)