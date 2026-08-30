"""DCR - DragonCloud_reading: tai truyen chu ve may, xuat EPUB/TXT.

Chay khong tham so  -> mo cua so app rieng (dung WebView2 co san cua Windows).
--web               -> mo giao dien bang trinh duyet thay vi cua so app.
--url ...           -> tai thang tren dong lenh, khong can giao dien.
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

APP_TEN = "DCR - DragonCloud_reading"

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core import store                                    # noqa: E402
from core.downloader import Manager                       # noqa: E402
from core.net import Http                                 # noqa: E402
from core.server import serve                             # noqa: E402
from core.sources import Registry                         # noqa: E402


def _mo_server(port: int):
    """Mo server o cong dau tien con trong, ke tu `port`."""
    for buoc in range(20):
        try:
            return serve(port + buoc)
        except OSError:
            continue
    return None


def _net_dpi():
    """Cho chu khong bi mo tren man hinh co ty le phong to (Windows)."""
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def _bao_la_app_rieng():
    """De thanh tac vu Windows dung icon cua app thay vi icon chung cua Python."""
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "DCR.DragonCloud.Reading")
    except Exception:
        pass


def _gan_icon_cua_so():
    """Gan icon cho cua so bang Win32.

    pywebview co tham so icon nhung backend EdgeChromium (ban dung tren Windows)
    khong doc tham so do, nen phai tu tim cua so cua tien trinh minh roi gui
    WM_SETICON. Cua so duoc tao sau khi vong lap GUI chay nen phai cho mot chut.
    """
    ico = ROOT / "appicon.ico"
    if not ico.is_file():
        return
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        me = os.getpid()

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def thu(hwnd, lparam):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == me and user32.IsWindowVisible(hwnd):
                ctypes.cast(lparam, ctypes.POINTER(wintypes.HWND))[0] = hwnd
            return True

        IMAGE_ICON, LR_LOADFROMFILE, WM_SETICON = 1, 0x0010, 0x0080
        for _ in range(40):                       # cho toi da ~6 giay
            giu = wintypes.HWND(0)
            user32.EnumWindows(thu, ctypes.byref(giu))
            if giu.value:
                for kich, loai in ((32, 1), (16, 0)):    # 1 = ICON_BIG, 0 = ICON_SMALL
                    h = user32.LoadImageW(None, str(ico), IMAGE_ICON,
                                          kich, kich, LR_LOADFROMFILE)
                    if h:
                        user32.SendMessageW(giu, WM_SETICON, loai, h)
                return
            time.sleep(0.15)
    except Exception:
        pass                                       # khong co icon cung khong sao


def run_desktop(port: int) -> int:
    """Cua so app rieng: khong can mo trinh duyet, ton RAM it hon nhieu."""
    try:
        import webview
    except ImportError:
        print("Chua cai pywebview nen khong mo duoc cua so app.")
        print("  Cai bang:  python -m pip install pywebview")
        print("  Hoac dung trinh duyet:  python app.py --web")
        return 1

    httpd = _mo_server(port)
    if httpd is None:
        print("Khong mo duoc cong nao trong khoang", port, "-", port + 19)
        return 1
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"

    _net_dpi()
    _bao_la_app_rieng()
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    print(APP_TEN, "dang chay tai", url)
    print("Thu muc luu:", store.load_settings()["output_dir"])
    try:
        webview.create_window(APP_TEN, url, width=1180, height=820,
                              min_size=(880, 560))
        # ham nay chay sau khi vong lap GUI khoi dong -> luc do moi co cua so
        webview.start(_gan_icon_cua_so)          # chan cho den khi dong cua so
    finally:
        httpd.shutdown()
        httpd.server_close()
    return 0


def run_web(port: int, open_browser: bool) -> int:
    """Giao dien tren trinh duyet (nhu truoc)."""
    httpd = _mo_server(port)
    if httpd is None:
        print("Khong mo duoc cong nao trong khoang", port, "-", port + 19)
        return 1

    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    print("=" * 58)
    print("  " + APP_TEN + " dang chay:", url)
    print("  Thu muc luu:", store.load_settings()["output_dir"])
    print("  Dong cua so nay (hoac Ctrl+C) de tat.")
    print("=" * 58)
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nDa tat.")
    finally:
        httpd.server_close()
    return 0


def run_cli(args) -> int:
    cfg = store.load_settings()
    http = Http(delay=cfg["delay"], retries=cfg["retries"],
                timeout=cfg["timeout"], proxy=cfg["proxy"])
    reg = Registry(http, ROOT / "plugins")
    reg.load()

    src = reg.for_url(args.url)
    if not src:
        print("Khong co plugin nao xu ly duoc link nay.")
        return 1
    print("Nguon:", src.name, "- dang doc trang truyen...")
    book = src.fetch_book(args.url)
    print(f"Truyen: {book.title} | tac gia: {book.author or 'khong ro'} "
          f"| {len(book.chapters)} chuong")
    if not book.chapters:
        print("Khong tim thay chuong nao.")
        return 1

    a = max(1, args.tu)
    b = min(args.den or len(book.chapters), len(book.chapters))
    chapters = book.chapters[a - 1:b]
    formats = [f.strip() for f in (args.dinh_dang or ",".join(cfg["formats"])).split(",") if f.strip()]
    print(f"Tai chuong {a} -> {b} ({len(chapters)} chuong), xuat: {', '.join(formats)}")

    mgr = Manager(reg)
    job = mgr.submit(src, book, chapters, formats)
    last = -1
    while job.status not in ("xong", "loi", "da huy"):
        if job.done != last:
            last = job.done
            print(f"\r  {job.done}/{job.total} chuong ({job.done*100//max(1,job.total)}%)"
                  f" - {job.status}   ", end="", flush=True)
        time.sleep(0.3)
    print(f"\r  {job.done}/{job.total} chuong - {job.status}. {job.message}")
    for f in job.files:
        print("  ->", f)
    if job.failed:
        print(f"  {len(job.failed)} chuong loi, chay lai lenh nay se tai tiep.")
    return 0 if job.status == "xong" else 1


def main() -> int:
    p = argparse.ArgumentParser(description="Tai truyen chu ve may")
    p.add_argument("--url", help="link trang truyen (bo qua de mo giao dien)")
    p.add_argument("--tu", type=int, default=1, help="tai tu chuong so may")
    p.add_argument("--den", type=int, default=0, help="tai den chuong so may (0 = het)")
    p.add_argument("--dinh-dang", dest="dinh_dang", help="epub, txt hoac epub,txt")
    p.add_argument("--web", action="store_true",
                   help="mo bang trinh duyet thay vi cua so app")
    p.add_argument("--port", type=int, default=0, help="cong cho server noi bo")
    p.add_argument("--khong-mo-web", action="store_true",
                   help="chi chay server, khong tu mo gi ca")
    args = p.parse_args()

    if args.url:
        return run_cli(args)
    port = args.port or store.load_settings()["port"]
    if args.web or args.khong_mo_web:
        return run_web(port, not args.khong_mo_web)
    return run_desktop(port)


if __name__ == "__main__":
    raise SystemExit(main())
