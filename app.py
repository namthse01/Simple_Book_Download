"""TaiTruyen - tai truyen chu ve may, xuat EPUB/TXT.

Chay khong tham so  -> mo giao dien web tren trinh duyet.
Chay voi --url      -> tai thang tren dong lenh, khong can giao dien.
"""
from __future__ import annotations

import argparse
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core import store                                    # noqa: E402
from core.downloader import Manager                       # noqa: E402
from core.net import Http                                 # noqa: E402
from core.server import serve                             # noqa: E402
from core.sources import Registry                         # noqa: E402


def run_gui(port: int, open_browser: bool):
    for attempt in range(20):
        try:
            httpd = serve(port + attempt)
            break
        except OSError:
            continue
    else:
        print("Khong mo duoc cong nao trong khoang", port, "-", port + 19)
        return 1

    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    print("=" * 58)
    print("  TaiTruyen dang chay:", url)
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
    p.add_argument("--url", help="link trang truyen (bo qua de mo giao dien web)")
    p.add_argument("--tu", type=int, default=1, help="tai tu chuong so may")
    p.add_argument("--den", type=int, default=0, help="tai den chuong so may (0 = het)")
    p.add_argument("--dinh-dang", dest="dinh_dang", help="epub, txt hoac epub,txt")
    p.add_argument("--port", type=int, default=0, help="cong cho giao dien web")
    p.add_argument("--khong-mo-web", action="store_true", help="khong tu mo trinh duyet")
    args = p.parse_args()

    if args.url:
        return run_cli(args)
    return run_gui(args.port or store.load_settings()["port"], not args.khong_mo_web)


if __name__ == "__main__":
    raise SystemExit(main())
