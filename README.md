サイトURL:https://tealands.github.io/SortTodo/

# SortTodo

前に作ったSortTodoをレポジトリにします

<img width="1447" height="948" alt="image" src="https://github.com/user-attachments/assets/7589312a-9c58-49e6-bc6f-9d583372643c" />

## ローカルで動かす方法

### 必要な開発環境

- windows環境
- Python 3.8以上
- Flask
- その他、`requirements.txt`に記載されているライブラリ

### 手順

1. このレポジトリをクローンする

```bash
git clone https://github.com/Tealands/TodoApp
```

2. クローンしたディレクトリに移動する
3. 必要なライブラリをインストールして、アプリを起動する

```bash
pip install -r requirements.txt
python app.py
```

4. ブラウザで `http://localhost:5000` にアクセスする

## 今後の追加要素

- 万人が使えるように、データを保存するAccessDatabseのパスを指定して、そこにDatabaseファイルがなければ作成する。そして、そのパスはブラウザのローカルストレージに保存するようにする。このパスをonedriveの中などにすることで複数の端末から同じDBにアクセスできる。
- デスクトップにアイコン付き実行ファイルを作成する
