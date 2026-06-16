"""TodoApp デスクトップ起動用ランチャー（非フリーズ/開発用）

デスクトップのアイコン(TodoApp.lnk)から pythonw.exe で呼び出される。
実体の起動ロジックは launcher.py に集約してある。
"""
from launcher import main

if __name__ == "__main__":
    main()
