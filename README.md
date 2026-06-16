# TodoApp

前に作ったSortTodoをレポジトリにします

詳しい利用手順はForUser.mdを確認してください。

## 省略語

- Microsoft Access Database->MAD
- Database->DB
- OneDrive->OD
- ShellScriptファイル->SHファイル

## ローカルで動かす方法

### 必要な開発環境

- windows環境
- Python 3.8以上
- Flask
- その他、`requirements.txt`に記載されているライブラリ

### 手順

1. このレポジトリをクローンする

```powershell
git clone https://github.com/Tealands/TodoApp
```

2. クローンしたディレクトリに移動する
3. 必要なライブラリをインストールして、アプリを起動する

```powershell
pip install -r requirements.txt
python app.py
```

4. ブラウザで `http://localhost:5000` にアクセスする

## 環境構築不要の配布（インストーラー）

Python を入れていない人にも配れるよう、**インストーラー1つで必要環境ごと導入**できる。
仕組みは2段構え:

1. **PyInstaller** で Python・Flask・pyodbc・pywin32・OpenCV を `TodoApp.exe` に同梱
   （配布先に Python のインストールは不要）
2. **Inno Setup** のインストーラーが、Access ドライバ未導入の PC には
   Microsoft Access Database Engine をまとめて自動インストール

### ビルド手順（開発者向け）

前提ツール:

- PyInstaller … `pip install pyinstaller`
- Inno Setup 6 … `winget install JRSoftware.InnoSetup`
- （任意）`redist\AccessDatabaseEngine_X64.exe`
  … Microsoft 公式「Access Database Engine 2016 再頒布可能」から取得して配置

ビルドは1コマンド:

```powershell
.\build.ps1
```

- `dist\TodoApp\TodoApp.exe` … Python 同梱の実行ファイル
- `Output\TodoApp_Setup.exe` … 配布用インストーラー（Inno Setup がある場合）

### 配布される側がやること

`TodoApp_Setup.exe` をダブルクリック → 完了 → デスクトップアイコンから起動するだけ。

> ⚠️ 注意: `TodoApp.exe` は 64bit のため 64bit 版 Access ドライバが必要。
> 32bit 版 Office が入った PC では 64bit ドライバと競合し得るため、
> インストーラーが検出して警告する（その場合は手動対応が必要）。

### 構成ファイル

| ファイル | 役割 |
|---|---|
| `entry.py` | フリーズ時のエントリ。引数なしでランチャー、`--backend` でサーバー |
| `launcher.py` | 起動ロジック（アニメ表示→バックエンド起動→ブラウザ表示）|
| `launch_todo.pyw` | 非フリーズ（開発）用のデスクトップ起動シム |
| `TodoApp.spec` | PyInstaller ビルド定義 |
| `installer.iss` | Inno Setup インストーラー定義 |
| `build.ps1` | 上記をまとめて実行するビルドスクリプト |

## 今後の追加要素

- ~~dockerを用いて環境構築を行わなくてよくする~~
  → Access DB / Windows 固有機能を残す方針のため、Docker(Linux) ではなく
    **PyInstaller + Inno Setup によるインストーラー配布**に変更（上記参照）
- 32bit / 64bit 両対応のインストーラー（32bit Office 環境への対応）
- 初期設定画面の景観を変える
- アニメーションが終わってから画面を表示するまでの時間を短縮する(アニメーションは最前に持ってくる)
