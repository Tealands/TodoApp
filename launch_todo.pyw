"""TodoApp ランチャー

デスクトップのアイコンから呼び出される。
1. バックエンド(app.py)がまだ起動していなければ、コンソール無しで起動する。
2. 起動を待つ間、mini_animation.mov を小さなウインドウでループ再生する。
   （動画が無い／再生できない場合は、ただ待つだけにフォールバックする）
3. サーバーが応答したら小ウインドウを閉じ、既定のブラウザで画面を開く。

pythonw.exe で実行することでコンソールウィンドウを表示しない。
"""
import os
import sys
import time
import socket
import subprocess
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
HOST = "127.0.0.1"
PORT = 5000
URL = f"http://{HOST}:{PORT}"
MOVIE = os.path.join(HERE, "KeepOut", "mini_animaiton.mov")

WAIT_TIMEOUT = 60.0   # アニメ再生後にサーバー起動を待つ最大秒数
WIN_MAX_W = 480       # 小ウインドウの最大幅(px)
WIN_TITLE = "TodoApp"


def is_up():
    """サーバーがポートで応答していれば True。loopback なので即座に返る。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex((HOST, PORT)) == 0


def start_backend():
    """コンソールウインドウを出さずに app.py を起動する。"""
    CREATE_NO_WINDOW = 0x08000000
    subprocess.Popen(
        [sys.executable, os.path.join(HERE, "app.py")],
        cwd=HERE,
        creationflags=CREATE_NO_WINDOW,
    )


def _arrange_window(title, w, h):
    """cv2 ウインドウを枠なし・最前面・画面中央に整える（Windows 限定・任意）。"""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        # 64bit環境でHWND(ポインタ)が切り詰められないよう型を明示する
        user32.FindWindowW.restype = wintypes.HWND
        user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        user32.SetWindowPos.argtypes = [
            wintypes.HWND, wintypes.HWND,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint,
        ]
        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongW.restype = ctypes.c_long
        user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]

        hwnd = user32.FindWindowW(None, title)
        if not hwnd:
            return

        GWL_STYLE = -16
        WS_CAPTION = 0x00C00000
        WS_THICKFRAME = 0x00040000
        WS_POPUP = -0x80000000          # 0x80000000 を符号付きLONGで表現
        SWP_FRAMECHANGED = 0x0020
        SWP_SHOWWINDOW = 0x0040
        HWND_TOPMOST = wintypes.HWND(-1)

        # 枠（タイトルバー・リサイズ枠）を外す
        style = user32.GetWindowLongW(hwnd, GWL_STYLE)
        style = (style & ~WS_CAPTION & ~WS_THICKFRAME) | WS_POPUP
        user32.SetWindowLongW(hwnd, GWL_STYLE, style)

        # 画面中央に配置し、サイズを確定し、最前面化する
        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        user32.SetWindowPos(
            hwnd, HWND_TOPMOST, x, y, w, h,
            SWP_FRAMECHANGED | SWP_SHOWWINDOW,
        )
    except Exception:
        pass


def play_until_ready():
    """動画を1回通し再生しながらサーバー起動を待つ。動画が使えなければ単純待機。"""
    try:
        import cv2
    except Exception:
        cv2 = None

    deadline = time.monotonic() + WAIT_TIMEOUT

    if cv2 is None or not os.path.exists(MOVIE):
        # フォールバック: 動画なしで待つだけ
        while time.monotonic() < deadline and not is_up():
            time.sleep(0.3)
        return

    cap = cv2.VideoCapture(MOVIE)
    if not cap.isOpened():
        cap.release()
        while time.monotonic() < deadline and not is_up():
            time.sleep(0.3)
        return

    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    delay = int(1000 / fps) if fps and fps > 0 else 33
    delay = max(1, delay)

    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or WIN_MAX_W)
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or WIN_MAX_W)
    scale = min(1.0, WIN_MAX_W / src_w) if src_w else 1.0
    win_w = max(1, int(src_w * scale))
    win_h = max(1, int(src_h * scale))

    try:
        cv2.namedWindow(WIN_TITLE, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WIN_TITLE, win_w, win_h)
        # 先頭フレームを1枚描画してウインドウを生成してから、枠なし・中央・最前面に整える
        ret, first = cap.read()
        if ret:
            cv2.imshow(WIN_TITLE, first)
        cv2.waitKey(1)
        _arrange_window(WIN_TITLE, win_w, win_h)
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        # 1) アニメーションを最後まで一度通して再生する。
        #    （バックエンドは裏で起動中。再生し終わる頃には大抵起動済み）
        while True:
            ret, frame = cap.read()
            if not ret:
                break  # 末尾まで再生したら終了
            cv2.imshow(WIN_TITLE, frame)
            if cv2.waitKey(delay) == 27:  # Esc で途中スキップ
                break

        # 2) 再生し終えてもまだ起動していなければ、ウインドウを保ったまま起動を待つ
        while time.monotonic() < deadline and not is_up():
            if cv2.waitKey(50) == 27:
                break
    except Exception:
        # 何かあっても起動はブロックしない
        while time.monotonic() < deadline and not is_up():
            time.sleep(0.3)
    finally:
        cap.release()
        try:
            cv2.destroyWindow(WIN_TITLE)
            cv2.waitKey(1)
        except Exception:
            pass


def main():
    if is_up():
        # すでに起動済みならアニメーション不要、すぐ開く
        webbrowser.open(URL)
        return

    start_backend()
    play_until_ready()
    webbrowser.open(URL)


if __name__ == "__main__":
    main()
