"""May chu noi bo phuc vu giao dien web + API."""
from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import reader, store
from .downloader import Manager
from .net import Http
from .sources import Registry

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"


class App:
    """Giu trang thai chung cua ung dung."""

    def __init__(self):
        self.reload_http()
        self.manager = Manager(self.registry)
        self.books: dict[str, object] = {}      # nho tam Book da lay de khoi phai tai lai
        self.lock = threading.Lock()

    def reload_http(self):
        cfg = store.load_settings()
        self.http = Http(delay=cfg["delay"], retries=cfg["retries"],
                         timeout=cfg["timeout"], proxy=cfg["proxy"])
        self.registry = Registry(self.http, ROOT / "plugins")
        self.registry.load()
        if hasattr(self, "manager"):
            self.manager.registry = self.registry
        return self.registry


APP: App | None = None


class Handler(BaseHTTPRequestHandler):
    server_version = "TaiTruyen"
    protocol_version = "HTTP/1.1"

    # ---------- tien ich ----------
    def log_message(self, fmt, *args):
        pass

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError):
            pass

    def json(self, data, code=200):
        self._send(code, json.dumps(data, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def fail(self, msg: str, code=400):
        self.json({"ok": False, "loi": msg}, code)

    @staticmethod
    def _entry(url: str) -> dict | None:
        """Tim muc thu vien theo link truyen."""
        return next((x for x in store.load_library() if x.get("url") == url), None)

    def body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    # ---------- dinh tuyen ----------
    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path.startswith("/api/"):
                return self.api_get(u.path, q)
            return self.static(u.path)
        except Exception:
            self.fail(traceback.format_exc(limit=3), 500)

    def do_POST(self):
        u = urlparse(self.path)
        try:
            if u.path.startswith("/api/"):
                return self.api_post(u.path, self.body())
            self.fail("khong ho tro", 404)
        except Exception:
            self.fail(traceback.format_exc(limit=3), 500)

    # ---------- file tinh ----------
    def static(self, path: str):
        rel = "index.html" if path in ("/", "") else unquote(path.lstrip("/"))
        target = (WEB / rel).resolve()
        if not str(target).startswith(str(WEB.resolve())) or not target.is_file():
            return self._send(404, b"khong tim thay", "text/plain; charset=utf-8")
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        self._send(200, target.read_bytes(), ctype)

    # ---------- API GET ----------
    def api_get(self, path: str, q: dict):
        app = APP
        if path == "/api/sources":
            return self.json({"ok": True, "nguon": [s.info() for s in app.registry.sources],
                              "loi": app.registry.errors})

        if path == "/api/search":
            kw = (q.get("q") or "").strip()
            if not kw:
                return self.fail("chua nhap tu khoa")
            sid = q.get("source") or ""
            page = int(q.get("page") or 1)
            targets = ([app.registry.by_id(sid)] if app.registry.by_id(sid)
                       else app.registry.searchable())
            out, errs = [], []
            for s in targets:
                if not s or not s.can_search:
                    continue
                try:
                    out += [b.to_dict() for b in s.search(kw, page)]
                except Exception as exc:
                    errs.append(f"{s.name}: {exc}")
            return self.json({"ok": True, "ket_qua": out, "loi": errs})

        if path == "/api/book":
            url = (q.get("url") or "").strip()
            if not url.startswith("http"):
                return self.fail("link khong hop le")
            src = app.registry.for_url(url)
            if not src:
                return self.fail("khong co plugin nao xu ly duoc link nay")
            book = src.fetch_book(url)
            with app.lock:
                app.books[book.url] = (book, src)
                app.books[url] = (book, src)
            d = book.to_dict()
            d["chapters"] = [c.to_dict() for c in book.chapters]
            canh_bao = ""
            if len(book.chapters) <= 1 and not src.domains:
                # Plugin tong quat chi doc duoc HTML ban dau. Trang nao nap danh
                # sach chuong bang JavaScript se chi lo ra 1 link "doc tu dau".
                canh_bao = ("Chỉ tìm thấy %d chương — trang này nhiều khả năng nạp danh "
                            "sách chương bằng JavaScript nên bộ dò tự động không thấy. "
                            "Cần viết plugin riêng cho nó trong thư mục plugins."
                            % len(book.chapters))
            return self.json({"ok": True, "truyen": d, "nguon": src.id,
                              "canh_bao": canh_bao})

        if path == "/api/jobs":
            return self.json({"ok": True, "viec": app.manager.list()})

        if path == "/api/settings":
            return self.json({"ok": True, "cai_dat": store.load_settings(),
                              "bo_loc": store.load_filters()})

        if path == "/api/library":
            return self.json({"ok": True, "thu_vien": store.load_library()})

        if path == "/api/read/list":
            entry = self._entry(q.get("url") or "")
            if entry is None:
                return self.fail("không có truyện này trong thư viện")
            chapters = reader.list_chapters(entry.get("folder") or "")
            if not chapters:
                return self.fail("không tìm thấy file chương nào trong thư mục truyện")
            return self.json({"ok": True, "truyen": {
                "title": entry.get("title", ""), "author": entry.get("author", ""),
                "cover": entry.get("cover", ""), "url": entry.get("url", ""),
            }, "chuong": chapters})

        if path == "/api/read/chapter":
            entry = self._entry(q.get("url") or "")
            if entry is None:
                return self.fail("không có truyện này trong thư viện")
            data = reader.read_chapter(entry.get("folder") or "", q.get("index") or 1)
            if data is None:
                return self.fail("chưa tải chương này về máy")
            return self.json({"ok": True, "chuong": data})

        return self.fail("khong co API nay", 404)

    # ---------- API POST ----------
    def api_post(self, path: str, data: dict):
        app = APP

        if path == "/api/download":
            url = (data.get("url") or "").strip()
            with app.lock:
                cached = app.books.get(url)
            if cached:
                book, src = cached
            else:
                src = app.registry.for_url(url)
                if not src:
                    return self.fail("khong co plugin nao xu ly duoc link nay")
                book = src.fetch_book(url)
                with app.lock:
                    app.books[url] = (book, src)
            if not book.chapters:
                return self.fail("khong tim thay chuong nao o trang nay")

            a = max(1, int(data.get("tu") or 1))
            b = int(data.get("den") or len(book.chapters))
            b = min(max(a, b), len(book.chapters))
            chapters = book.chapters[a - 1:b]
            formats = data.get("dinh_dang") or store.load_settings()["formats"]
            job = app.manager.submit(src, book, chapters, formats)
            return self.json({"ok": True, "viec": job.to_dict()})

        if path == "/api/job/cancel":
            return self.json({"ok": app.manager.cancel(data.get("id", ""))})

        if path == "/api/job/clear":
            app.manager.clear_finished()
            return self.json({"ok": True})

        if path == "/api/settings":
            cfg = store.save_settings(data.get("cai_dat") or {})
            if data.get("bo_loc") is not None:
                store.save_filters(data["bo_loc"])
            app.reload_http()
            return self.json({"ok": True, "cai_dat": cfg, "bo_loc": store.load_filters()})

        if path == "/api/open":
            target = data.get("duong_dan") or store.load_settings()["output_dir"]
            p = Path(target)
            if not p.exists():
                return self.fail("duong dan khong ton tai")
            try:
                if sys.platform == "win32":
                    os.startfile(p if p.is_dir() else p.parent)
                else:
                    subprocess.Popen(["xdg-open", str(p if p.is_dir() else p.parent)])
            except Exception as exc:
                return self.fail(str(exc))
            return self.json({"ok": True})

        if path == "/api/library/remove":
            return self.json({"ok": True, "thu_vien": store.remove_library(data.get("url", ""))})

        if path == "/api/library/delete":
            return self.json(reader.delete_book(data.get("url", "")))

        if path == "/api/reload":
            reg = app.reload_http()
            return self.json({"ok": True, "nguon": [s.info() for s in reg.sources],
                              "loi": reg.errors})

        return self.fail("khong co API nay", 404)


def serve(port: int) -> ThreadingHTTPServer:
    global APP
    APP = App()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    return httpd
