import os
import pyodbc
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)

DB_PATH = r'C:\Users\hachi\OneDrive\SortTodoDatabase.accdb'

CONN_STR = (
    r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};'
    f'DBQ={DB_PATH};'
)


def get_conn():
    return pyodbc.connect(CONN_STR)


def create_db_if_not_exists():
    """Accessデータベースファイルが存在しない場合に作成する"""
    if not os.path.exists(DB_PATH):
        try:
            import win32com.client
            catalog = win32com.client.Dispatch('ADOX.Catalog')
            catalog.Create(
                f'Provider=Microsoft.ACE.OLEDB.12.0;Data Source={DB_PATH};'
            )
            del catalog
            print(f'データベースを作成しました: {DB_PATH}')
        except Exception as e:
            raise RuntimeError(
                f'データベースの作成に失敗しました。\n'
                f'pywin32 と Microsoft ACE OLEDB ドライバーがインストールされているか確認してください。\n'
                f'エラー: {e}'
            )


def create_table_if_not_exists():
    """Tasksテーブルが存在しない場合に作成する"""
    conn = get_conn()
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
                ListType  TEXT(10)
            )
        """)
        conn.commit()
        print('Tasksテーブルを作成しました。')
    cursor.close()
    conn.close()


def init_db():
    create_db_if_not_exists()
    create_table_if_not_exists()


def row_to_dict(row):
    return {
        'id':        row[0],
        'text':      row[1],
        'done':      bool(row[2]),
        'createdAt': row[3] or '',
        'date':      row[4],
        'listType':  row[5],
    }


# ── HTMLを配信 ────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)


# ── API ──────────────────────────────────────────────────
@app.route('/api/tasks', methods=['GET'])
def get_tasks():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT ID, TaskText, Done, CreatedAt, Deadline, ListType FROM Tasks'
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
        'INSERT INTO Tasks (TaskText, Done, CreatedAt, Deadline, ListType) VALUES (?, ?, ?, ?, ?)',
        (data['text'], False, data.get('createdAt'), data.get('date'), data['listType'])
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
    }), 201


@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    data = request.get_json()
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE Tasks SET TaskText=?, Done=?, Deadline=? WHERE ID=?',
        (data['text'], data['done'], data.get('date'), task_id)
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


if __name__ == '__main__':
    init_db()
    print('サーバー起動中 → http://localhost:5000')
    app.run(debug=True, port=5000)
