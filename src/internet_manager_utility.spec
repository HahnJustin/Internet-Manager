# -*- mode: python ; coding: utf-8 -*-
import os

# SPECPATH is already the directory that contains this .spec file
SPEC_DIR = os.path.abspath(SPECPATH)              # ...\InternetManager\src
ROOT     = os.path.dirname(SPEC_DIR)              # ...\InternetManager
SRC      = os.path.join(ROOT, "src")              # ...\InternetManager\src
UTIL     = os.path.join(SRC, "utilities")         # ...\InternetManager\src\utilities

a = Analysis(
    [os.path.join(UTIL, "utility_cli.py")],
    pathex=[SRC, UTIL],  # make sure both package + same-folder imports work
    binaries=[],
    datas=[],
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
    a.zipfiles,
    a.datas,
    [],
    name="internet_manager_utility",
    debug=False,
    strip=False,
    upx=False,  # your log says UPX not available anyway
    console=True,
    icon=os.path.join(SRC, "assets", "globe_server.ico"),
)
