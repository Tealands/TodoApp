# -*- mode: python ; coding: utf-8 -*-
"""TodoApp の PyInstaller ビルド定義。

  build: pyinstaller --noconfirm TodoApp.spec
  出力 : dist/TodoApp/TodoApp.exe （onedir 形式）

エントリは entry.py。同じ exe が引数なしでランチャー、--backend でサーバーになる。
index.html / style.css / KeepOut(アイコン・動画) を同梱する。
"""

block_cipher = None

datas = [
    ('index.html', '.'),
    ('style.css', '.'),
    ('KeepOut', 'KeepOut'),
]

hiddenimports = [
    'pyodbc',
    'win32com',
    'win32com.client',
    'win32timezone',
    'cv2',
]

a = Analysis(
    ['entry.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TodoApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,            # ウインドウアプリ（コンソール非表示）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='KeepOut/desktop.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TodoApp',
)
