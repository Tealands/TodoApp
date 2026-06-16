"""TodoApp ランチャー（共通モジュール）

非フリーズ実行（launch_todo.pyw 経由）とフリーズ実行（entry.py / TodoApp.exe）の
両方から使われる起動ロジック。

1. バックエンドがまだ起動していなければ、コンソール無しで起動する。
   - 通常実行 : python で app.py を起動
   - フリーズ : 自分自身(TodoApp.exe)を --backend 付きで再起動
2. 起動を待つ間、mini_animaiton.mov を小さなウインドウでループ再生する。
   （動画が無い／再生できない場合は、ただ待つだけにフォールバックする）
3. サーバーが応答したら小ウインドウを閉じ、既定のブラウザで画面を開く。
"""
import os
import sys
import time
import socket
import subprocess
import webbrowser
import threading

# ── 実行環境のパス解決（app.py と同じ考え方）────────────────
FROZEN = getattr(sys, 'frozen', False)
# RES_DIR : 同梱リソース（動画など）の場所
RES_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
# HERE    : 実行ファイルの隣（作業ディレクトリ・db_config.json などの基準）
HERE = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))

HOST = "127.0.0.1"
PORT = 5000
URL = f"http://{HOST}:{PORT}"
MOVIE = os.path.join(RES_DIR, "KeepOut", "mini_animaiton.mov")

WAIT_TIMEOUT = 60.0   # アニメ再生後にサーバー起動を待つ最大秒数
WIN_MAX_W = 480       # 小ウインドウの最大幅(px)
WIN_TITLE = "TodoApp"


def is_up():
    """サーバーがポートで応答していれば True。loopback なので即座に返る。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex((HOST, PORT)) == 0


def start_backend():
    """コンソールウインドウを出さずにバックエンドを起動する。"""
    CREATE_NO_WINDOW = 0x08000000
    if FROZEN:
        # .exe 化されている場合、sys.executable は TodoApp.exe 自身。
        # --backend 付きで再起動し、entry.py 側でサーバーモードに分岐させる。
        args = [sys.executable, "--backend"]
    else:
        args = [sys.executable, os.path.join(HERE, "app.py")]
    subprocess.Popen(
        args,
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
            try:
                EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
                found = {'hwnd': None}

                user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
                user32.GetWindowTextW.restype = ctypes.c_int

                def _enum_proc(h, lparam):
                    buf = ctypes.create_unicode_buffer(512)
                    user32.GetWindowTextW(h, buf, 512)
                    txt = buf.value or ''
                    if title in txt:
                        found['hwnd'] = h
                        return False
                    return True

                user32.EnumWindows.argtypes = [EnumWindowsProc, ctypes.c_void_p]
                user32.EnumWindows.restype = wintypes.BOOL
                user32.EnumWindows(EnumWindowsProc(_enum_proc), 0)
                hwnd = found['hwnd']
            except Exception:
                hwnd = None

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

        # ウインドウが属するプライマリモニタの作業領域を取得して中央に配置する
        try:
            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.c_ulong),
                    ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT),
                    ("dwFlags", ctypes.c_ulong),
                ]

            primary = {'mi': None}

            EnumMonProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

            def _enum_mon(hmon, hdc, lprc, lparam):
                mi = MONITORINFO()
                mi.cbSize = ctypes.sizeof(MONITORINFO)
                try:
                    if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                        # MONITORINFOF_PRIMARY == 1
                        if mi.dwFlags & 1:
                            primary['mi'] = mi
                            return False
                except Exception:
                    pass
                return True

            user32.EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT), EnumMonProc, wintypes.LPARAM]
            user32.EnumDisplayMonitors.restype = wintypes.BOOL
            user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
            user32.GetMonitorInfoW.restype = wintypes.BOOL

            try:
                user32.EnumDisplayMonitors(None, None, EnumMonProc(_enum_mon), 0)
            except Exception:
                pass

            if primary['mi'] is not None:
                mi = primary['mi']
                mleft = mi.rcWork.left
                mtop = mi.rcWork.top
                mwidth = mi.rcWork.right - mi.rcWork.left
                mheight = mi.rcWork.bottom - mi.rcWork.top
            else:
                mleft = 0
                mtop = 0
                mwidth = user32.GetSystemMetrics(0)
                mheight = user32.GetSystemMetrics(1)

            x = mleft + max(0, (mwidth - w) // 2)
            y = mtop + max(0, (mheight - h) // 2)
        except Exception:
            sw = user32.GetSystemMetrics(0)
            sh = user32.GetSystemMetrics(1)
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)

        # OpenCV の moveWindow でも明示的に位置を指定しておく
        try:
            import cv2 as _cv2
            _cv2.moveWindow(title, x, y)
        except Exception:
            pass

        # 表示してから位置を設定する（何度かリトライ）
        try:
            SW_SHOW = 5
            user32.ShowWindow(hwnd, SW_SHOW)
        except Exception:
            pass

        # 最初の配置
        user32.SetWindowPos(
            hwnd, HWND_TOPMOST, x, y, w, h,
            SWP_FRAMECHANGED | SWP_SHOWWINDOW,
        )

        # 少し待って再適用（ウインドウマネージャが位置を調整する場合に備える）
        try:
            import time as _time
            _time.sleep(0.05)
            user32.SetWindowPos(
                hwnd, HWND_TOPMOST, x, y, w, h,
                SWP_FRAMECHANGED | SWP_SHOWWINDOW,
            )
        except Exception:
            pass

        try:
            # フォアグラウンドに持ってくる
            user32.SetForegroundWindow(hwnd)
        except Exception:
            pass
    except Exception:
        pass


def play_until_ready(start_backend_during_play=True):
    """動画を1回通し再生しながらサーバー起動を待つ。動画が使えなければ単純待機。"""
    try:
        import cv2
    except Exception:
        cv2 = None

    deadline = time.monotonic() + WAIT_TIMEOUT

    if cv2 is None or not os.path.exists(MOVIE):
        # フォールバック: 動画なしで待つだけ
        if start_backend_during_play:
            # バックエンドを再生中に起動する（非同期）
            threading.Thread(target=start_backend, daemon=True).start()
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
        # アニメ表示が始まったらバックエンドを並列で起動
        if start_backend_during_play:
            threading.Thread(target=start_backend, daemon=True).start()
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
    # アニメを表示しながら並列でバックエンドを起動する
    play_until_ready(start_backend_during_play=True)
    webbrowser.open(URL)


if __name__ == "__main__":
    main()
