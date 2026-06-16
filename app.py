import os
import sys
import json
import time
import threading
import pyodbc
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)

# ── 実行環境のパス解決 ────────────────────────────────────
# PyInstaller で .exe 化（フリーズ）された場合と、通常の python 実行の両方に対応する。
#   FROZEN    : .exe として実行中か
#   RES_DIR   : index.html / style.css / KeepOut など同梱リソースの場所
#               （フリーズ時は展開先 _MEIPASS、通常時はこのファイルのフォルダ）
#   DATA_DIR  : db_config.json など「書き込み・永続化したい」ファイルの場所
#               （フリーズ時は exe の隣。一時展開先に書くと再起動で消えるため）
FROZEN = getattr(sys, 'frozen', False)
RES_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))

# ── 自動終了(ハートビート監視) ────────────────────────────
# フロントエンドが定期的に /api/ping を送る。画面(タブ/ウインドウ)が
# 閉じられて ping が一定時間途絶えたら、バックエンドを自分で終了する。
SHUTDOWN_AFTER = 8.0     # 最後のpingからこの秒数pingが無ければ終了
STARTUP_GRACE = 90.0     # 起動後、最初のpingをこの秒数まで待つ(ブラウザ起動猶予)
_heartbeat = {'last': None, 'started': time.monotonic()}


def _watchdog():
    """pingの途絶を監視し、画面が閉じられたらプロセスを終了する。"""
    while True:
        time.sleep(2.0)
        now = time.monotonic()
        last = _heartbeat['last']
        if last is None:
            # まだ一度も接続が無い。起動猶予を超えたらブラウザ未起動とみなして終了
            if now - _heartbeat['started'] > STARTUP_GRACE:
                os._exit(0)
        elif now - last > SHUTDOWN_AFTER:
            os._exit(0)

# ── 設定ファイル ──────────────────────────────────────────
# 接続するMAD(Microsoft Access Database)のパスをここに保存する。
# フリーズ時は exe の隣（永続）に置く。
CONFIG_PATH = os.path.join(DATA_DIR, 'db_config.json')


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(cfg):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get_db_path():
    return load_config().get('db_path')


def conn_str(db_path):
    return (
        r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};'
        f'DBQ={db_path};'
    )


def get_conn():
    db_path = get_db_path()
    if not db_path:
        raise RuntimeError('データベースが設定されていません。初回登録画面で設定してください。')
    if not os.path.exists(db_path):
        raise RuntimeError(f'設定されたデータベースが見つかりません: {db_path}')
    return pyodbc.connect(conn_str(db_path))


def get_desktop_folder():
    if os.name != 'nt':
        raise RuntimeError('この機能はWindows環境でのみ利用できます。')

    try:
        import ctypes
        from ctypes import create_unicode_buffer
        CSIDL_DESKTOPDIRECTORY = 0x0010
        buf = create_unicode_buffer(260)
        res = ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_DESKTOPDIRECTORY, None, 0, buf)
        if res != 0:
            raise RuntimeError('デスクトップフォルダーの取得に失敗しました。')
        desktop = buf.value
        if os.path.isdir(desktop):
            return desktop
    except Exception:
        pass

    desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
    if os.path.isdir(desktop):
        return desktop

    raise RuntimeError('デスクトップフォルダーが見つかりませんでした。')


def create_desktop_shortcut():
    # フリーズ時は exe 自身を、通常時は launch_todo.pyw をショートカット先にする。
    if FROZEN:
        target = sys.executable
    else:
        target = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'launch_todo.pyw')
        if not os.path.exists(target):
            raise RuntimeError(f'起動用ファイルが見つかりません: {target}')

    desktop = get_desktop_folder()
    shortcut_path = os.path.join(desktop, 'TodoApp.lnk')
    try:
        import win32com.client
        shell = win32com.client.Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(shortcut_path)
        icon_path = os.path.join(RES_DIR, 'KeepOut', 'desktop.ico')
        if os.path.exists(icon_path):
            shortcut.IconLocation = icon_path
        shortcut.Targetpath = target
        shortcut.WorkingDirectory = os.path.dirname(target)
        shortcut.Description = 'TodoApp を起動します'
        shortcut.save()
        return shortcut_path
    except Exception as e:
        raise RuntimeError(f'ショートカットの作成に失敗しました: {e}')


# ── DB / テーブル作成 ─────────────────────────────────────
def create_access_db(db_path):
    """指定パスにMADファイルが無ければ新規作成する"""
    if os.path.exists(db_path):
        return
    try:
        import win32com.client
        catalog = win32com.client.Dispatch('ADOX.Catalog')
        catalog.Create(
            f'Provider=Microsoft.ACE.OLEDB.12.0;Data Source={db_path};'
        )
        del catalog
        print(f'データベースを作成しました: {db_path}')
    except Exception as e:
        raise RuntimeError(
            'データベースの作成に失敗しました。\n'
            'pywin32 と Microsoft ACE OLEDB ドライバーがインストールされているか確認してください。\n'
            f'エラー: {e}'
        )


def ensure_table(db_path):
    """Tasksテーブルが存在しない場合に作成する"""
    conn = pyodbc.connect(conn_str(db_path))
    cursor = conn.cursor()
    existing = [t.table_name for t in cursor.tables(tableType='TABLE')]
    if 'Tasks' not in existing:
        cursor.execute("""
            CREATE TABLE Tasks (
                ID        AUTOINCREMENT PRIMARY KEY,
                TaskText  MEMO,
                Done      YESNO,
                CreatedAt TEXT(50),
                Deadline  TEXT(50),
                ListType  TEXT(10),
                Lesson    TEXT(100)
            )
        """)
        conn.commit()
        print('Tasksテーブルを作成しました。')
    else:
        # 既存テーブルに Lesson カラムが無ければ追加する
        cols = [c.column_name for c in cursor.columns(table='Tasks')]
        if 'Lesson' not in cols:
            try:
                cursor.execute("ALTER TABLE Tasks ADD COLUMN Lesson TEXT(100)")
                conn.commit()
                print('Tasksテーブルに Lesson カラムを追加しました。')
            except Exception:
                # AccessのバージョンやドライバによってはALTERが通らない場合がある。
                # その場合はユーザーに手動で対応してもらう。
                print('警告: Lesson カラムの追加に失敗しました。手動で追加してください。')
    cursor.close()
    conn.close()


def row_to_dict(row):
    return {
        'id':        row[0],
        'text':      row[1],
        'done':      bool(row[2]),
        'createdAt': row[3] or '',
        'date':      row[4],
        'listType':  row[5],
        'lesson':    row[6] if len(row) > 6 else ''
    }


# ── HTMLを配信 ────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory(RES_DIR, 'index.html')


@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(RES_DIR, filename)


# ── ハートビートAPI ──────────────────────────────────────
@app.route('/api/ping', methods=['POST'])
def ping():
    """フロントエンドからの生存通知。画面が開いている間、定期的に呼ばれる。"""
    _heartbeat['last'] = time.monotonic()
    return ('', 204)


# ── 設定API ──────────────────────────────────────────────
@app.route('/api/config', methods=['GET'])
def get_config():
    """現在のDB設定状況を返す"""
    db_path = get_db_path()
    return jsonify({
        'configured': bool(db_path) and os.path.exists(db_path),
        'path': db_path,
    })


@app.route('/api/config', methods=['POST'])
def set_config():
    """
    DBパスを設定する。
    mode = 'existing' : 既存のMADファイルを参照する
    mode = 'new'      : 任意のフォルダーにMADファイルを新規作成する
    """
    data = request.get_json() or {}
    mode = data.get('mode')
    path = (data.get('path') or '').strip().strip('"')

    if not path:
        return jsonify({'error': 'パスを指定してください。'}), 400

    try:
        if mode == 'existing':
            if not os.path.exists(path):
                return jsonify({'error': f'ファイルが見つかりません: {path}'}), 400
            if not path.lower().endswith(('.accdb', '.mdb')):
                return jsonify({'error': 'MADファイル(.accdb / .mdb)を指定してください。'}), 400

        elif mode == 'new':
            # 拡張子が無ければ .accdb を付与
            if not path.lower().endswith(('.accdb', '.mdb')):
                path = path + '.accdb'
            folder = os.path.dirname(path)
            if folder and not os.path.isdir(folder):
                return jsonify({'error': f'フォルダーが見つかりません: {folder}'}), 400
            create_access_db(path)

        else:
            return jsonify({'error': '不明なモードです。'}), 400

        ensure_table(path)
        save_config({'db_path': path})
        return jsonify({'success': True, 'path': path})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/config', methods=['DELETE'])
def reset_config():
    """DB設定をリセットする（初回登録画面に戻す）"""
    save_config({})
    return jsonify({'success': True})


@app.route('/api/create-shortcut', methods=['POST'])
def create_shortcut_api():
    try:
        path = create_desktop_shortcut()
        return jsonify({'success': True, 'path': path})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/browse', methods=['GET'])
def browse():
    """
    ネイティブのファイル/フォルダー選択ダイアログを開き、選ばれたパスを返す。
    type = 'file'   : 既存ファイルを選択
    type = 'folder' : フォルダーを選択
    tkinterが使えない環境では supported:false を返し、手入力にフォールバックする。
    """
    kind = request.args.get('type', 'file')
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)

        if kind == 'folder':
            selected = filedialog.askdirectory(title='フォルダーを選択')
        else:
            selected = filedialog.askopenfilename(
                title='Accessデータベースファイルを選択',
                filetypes=[('Access Database', '*.accdb;*.mdb'), ('すべてのファイル', '*.*')],
            )

        root.destroy()
        return jsonify({'path': selected or '', 'supported': True})

    except Exception as e:
        return jsonify({'path': '', 'supported': False, 'error': str(e)})


# ── タスクAPI ────────────────────────────────────────────
@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT ID, TaskText, Done, CreatedAt, Deadline, ListType, Lesson FROM Tasks'
    )
    tasks = [row_to_dict(r) for r in cursor.fetchall()]
    cursor.close()
    conn.close()
    return jsonify(tasks)


@app.route('/api/tasks', methods=['POST'])
def add_task():
    data = request.get_json()
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO Tasks (TaskText, Done, CreatedAt, Deadline, ListType, Lesson) VALUES (?, ?, ?, ?, ?, ?)',
        (data['text'], False, data.get('createdAt'), data.get('date'), data['listType'], data.get('lesson'))
    )
    conn.commit()
    cursor.execute('SELECT @@IDENTITY')
    new_id = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return jsonify({
        'id':        new_id,
        'text':      data['text'],
        'done':      False,
        'createdAt': data.get('createdAt'),
        'date':      data.get('date'),
        'listType':  data['listType'],
        'lesson':    data.get('lesson') or '',
    }), 201


@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    data = request.get_json()
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE Tasks SET TaskText=?, Done=?, Deadline=?, Lesson=? WHERE ID=?',
        (data['text'], data['done'], data.get('date'), data.get('lesson'), task_id)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM Tasks WHERE ID=?', (task_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True})


def run_server():
    """Flask バックエンドを起動する。通常実行・フリーズ実行の両方から呼ばれる。"""
    # 起動時に既に設定済みならテーブルの存在だけ確認しておく
    db_path = get_db_path()
    if db_path and os.path.exists(db_path):
        try:
            ensure_table(db_path)
            print(f'接続先データベース: {db_path}')
        except Exception as e:
            print(f'警告: データベースの初期化に失敗しました: {e}')
    else:
        print('データベース未設定です。ブラウザの初回登録画面で設定してください。')

    # 画面が閉じられたら自動終了するための監視スレッドを開始
    threading.Thread(target=_watchdog, daemon=True).start()

    print('サーバー起動中 → http://localhost:5000')
    # debug=False: フリーズ時はデバッガ不要。use_reloader=False で単一プロセスにし、
    # 監視スレッドからの自動終了を確実にする。
    app.run(debug=not FROZEN, port=5000, use_reloader=False)


if __name__ == '__main__':
    run_server()
