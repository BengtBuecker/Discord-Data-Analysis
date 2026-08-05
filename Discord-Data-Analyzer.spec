# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[SPECPATH],
    binaries=[],
    datas=[('ui/index.html', 'ui'), ('ui/style.css', 'ui'), ('ui/app.js', 'ui'), ('ui/Logo.png', 'ui')],
    hiddenimports=['api', 'analyzers', 'analyzers.messages', 'analyzers.voice', 'utils', 'utils.parser', 'utils.formatting', 'webview', 'tkinter'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Discord-Data-Analyzer',
    icon='ui/Logo.ico',
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
