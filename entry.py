"""PyInstaller 用エントリポイント（TodoApp.exe）

同じ実行ファイルが2つの役割を持つ:
  TodoApp.exe            → ランチャー（アニメ表示 → バックエンド起動 → ブラウザ表示）
  TodoApp.exe --backend  → Flask バックエンドサーバー本体

ランチャーは start_backend() で自分自身を --backend 付きで再起動するため、
1つの exe だけで完結する。
"""
import sys

if __name__ == "__main__":
    if "--backend" in sys.argv:
        import app
        app.run_server()
    else:
        import launcher
        launcher.main()
