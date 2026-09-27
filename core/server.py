"""May chu noi bo phuc vu giao dien web + API."""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import socket
import subprocess
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import ai, bao, dich_bao, importer, reader, store, world
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

# Viec chay nen cua muc Doc bao (cap nhat / dich). Chi cho 1 viec mot luc cho
# khoi vua tai RSS vua goi AI lam nghen may.
VIEC_BAO = {"dang": False, "loai": "", "xong": 0, "tong": 0, "ten": "",
            "ket_qua": None, "loi": "", "xong_luc": 0.0}


def _chay_nen(loai: str, ham) -> None:
    """Chay `ham(bao_tien_do)` trong luong rieng, cap nhat VIEC_BAO cho giao dien theo doi."""
    VIEC_BAO.update({"dang": True, "loai": loai, "xong": 0, "tong": 0, "ten": "",
                     "ket_qua": None, "loi": "", "xong_luc": 0.0})

    def tien_do(xong, tong, ten=""):
        VIEC_BAO.update({"xong": xong, "tong": tong, "ten": ten})

    def chay():
        try:
            VIEC_BAO["ket_qua"] = ham(tien_do)
        except Exception:
            VIEC_BAO["loi"] = traceback.format_exc(limit=3)
        finally:
            VIEC_BAO["dang"] = False
            VIEC_BAO["xong_luc"] = __import__("time").time()

    threading.Thread(target=chay, daemon=True).start()


class Handler(BaseHTTPRequestHandler):
    server_version = "DCR"
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

        if path == "/api/lan-info":
            # dia chi de dien thoai trong cung mang vao doc + ma QR quet cho nhanh
            lan = bool(store.load_settings().get("lan"))
            mo_rong = getattr(app, "bound_host", "127.0.0.1") == "0.0.0.0"
            ip = _lan_ip()
            url = f"http://{ip}:{getattr(app, 'bound_port', 0)}/" if mo_rong else ""
            qr = ""
            if url:
                try:
                    import io as _io
                    import qrcode
                    import qrcode.image.svg
                    q = qrcode.QRCode(box_size=8, border=2)
                    q.add_data(url)
                    buf = _io.BytesIO()
                    q.make_image(image_factory=qrcode.image.svg.SvgPathImage).save(buf)
                    qr = buf.getvalue().decode("utf-8")
                except Exception:
                    pass                       # thieu thu vien qrcode thi chi hien link
            return self.json({"ok": True, "lan": lan, "mo_rong": mo_rong,
                              "ip": ip, "url": url, "qr": qr})

        if path == "/api/cover":
            # anh bia cua sach nhap tu may: nam trong thu muc sach, file cover.*
            entry = self._entry(q.get("url") or "")
            folder = Path(entry.get("folder") or "") if entry else None
            for p in (sorted(folder.glob("cover.*")) if folder and folder.is_dir() else []):
                ctype = mimetypes.guess_type(p.name)[0] or "image/jpeg"
                return self._send(200, p.read_bytes(), ctype)
            return self._send(404, b"", "image/jpeg")

        if path == "/api/read/chapter":
            entry = self._entry(q.get("url") or "")
            if entry is None:
                return self.fail("không có truyện này trong thư viện")
            data = reader.read_chapter(entry.get("folder") or "", q.get("index") or 1)
            if data is None:
                return self.fail("chưa tải chương này về máy")
            return self.json({"ok": True, "chuong": data})

        # ---------- tham nhap the gioi ----------
        if path == "/api/ai/models":
            try:
                return self.json({"ok": True,
                                  "models": ai.list_models(store.load_settings()["ai"])})
            except ai.AiError as exc:
                return self.fail(str(exc))

        if path == "/api/world/status":
            entry = self._entry(q.get("url") or "")
            if entry is None:
                return self.fail("không có truyện này trong thư viện")
            folder = entry.get("folder") or ""
            w = world.load_world(folder)
            return self.json({
                "ok": True,
                "build": world.build_status(entry["url"]),
                "world": bool(w),
                "meta": {k: w.get(k) for k in ("created", "updated", "model",
                                               "chapters_total", "mode")} if w else None,
                "sections_done": sorted(k for k, v in (w or {}).get("sections", {}).items()
                                        if (v or "").strip()),
                "sections_total": len(world._MUC_SO_TAY),
                "status": entry.get("status", ""),
                "phien": world.list_sessions(folder),
            })

        if path == "/api/world/info":
            entry = self._entry(q.get("url") or "")
            if entry is None:
                return self.fail("không có truyện này trong thư viện")
            w = world.load_world(entry.get("folder") or "")
            if not w:
                return self.fail("truyện này chưa khởi tạo thế giới")
            return self.json({"ok": True, "world": w})

        if path == "/api/world/session":
            entry = self._entry(q.get("url") or "")
            if entry is None:
                return self.fail("không có truyện này trong thư viện")
            s = world.load_session(entry.get("folder") or "", q.get("id") or "")
            if not s:
                return self.fail("không tìm thấy phiên chơi này")
            return self.json({"ok": True, "phien": s})

        # ---------- doc bao ----------
        if path == "/api/bao/nguon":
            return self.json({"ok": True, **bao.danh_sach()})

        if path == "/api/bao/ngay":
            return self.json({"ok": True, "ngay": bao.ds_ngay(),
                              "thu_muc": str(bao.thu_muc_kho())})

        if path == "/api/bao/doc":
            return self.json({"ok": True, **bao.doc_ngay(
                q.get("ngay") or "", q.get("muc") or "", q.get("quoc") or "",
                q.get("tim") or "", int(q.get("tu") or 0), int(q.get("so") or 60))})

        if path == "/api/bao/tien-do":
            return self.json({"ok": True, "viec": dict(VIEC_BAO)})

        if path == "/api/bao/dich-trang-thai":
            return self.json({"ok": True, "dich": dich_bao.trang_thai()})

        if path == "/api/bao/bai":
            b = bao.doc_bai(q.get("ngay") or "", q.get("link") or "")
            if b is None:
                return self.fail("không tìm thấy bài này trong kho")
            return self.json({"ok": True, "bai": b})

        if path == "/api/bao/nhung":
            u = q.get("url") or ""
            if not u.startswith("http"):
                return self.fail("link không hợp lệ")
            return self.json({"ok": True, **bao.co_cho_nhung(APP.http, u)})

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

        if path == "/api/import":
            # Nhap tai lieu co san: file gui len dang base64 trong JSON.
            files = []
            for f in data.get("files") or []:
                name = (f.get("name") or "").strip()
                try:
                    raw = base64.b64decode(f.get("b64") or "")
                except Exception:
                    raw = b""
                if name and raw:
                    files.append((name, raw))
            if not files:
                return self.fail("chưa nhận được file nào "
                                 "(nhận .epub, .txt, .docx, .pdf, .html, .md)")
            ket = importer.import_files(
                files, merge=bool(data.get("gop")),
                title=(data.get("ten") or "").strip(),
                author=(data.get("tac_gia") or "").strip(),
                formats=data.get("dinh_dang"),
                chi_thu=bool(data.get("thu")))
            return self.json({"ok": True, "sach": ket["sach"], "loi": ket["loi"],
                              "thu_vien": store.load_library()})

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
            if str(target).startswith(("http://", "https://")):
                # bai bao: mo ra trinh duyet that, vi cua so app (WebView) khong
                # phai cho de doc ca trang web ngoai
                import webbrowser
                webbrowser.open(str(target))
                return self.json({"ok": True})
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

        if path == "/api/library/update":
            return self.cap_nhat_truyen(data.get("url", ""))

        if path == "/api/reload":
            reg = app.reload_http()
            return self.json({"ok": True, "nguon": [s.info() for s in reg.sources],
                              "loi": reg.errors})

        # ---------- tham nhap the gioi ----------
        if path == "/api/world/build":
            entry = self._entry(data.get("url") or "")
            if entry is None:
                return self.fail("không có truyện này trong thư viện")
            cfg_ai = store.load_settings()["ai"]
            if not (cfg_ai.get("model") or "").strip():
                return self.fail("Chưa chọn model AI — vào Cài đặt › Nhập vai AI trước.")
            b = world.start_build(entry["url"], entry.get("folder") or "",
                                  entry.get("title") or "",
                                  mode=data.get("che_do") or "day_du",
                                  lam_lai=bool(data.get("lam_lai")))
            return self.json({"ok": True, "build": b})

        if path == "/api/world/cancel":
            return self.json({"ok": world.cancel_build(data.get("url") or "")})

        if path == "/api/world/create":
            entry = self._entry(data.get("url") or "")
            if entry is None:
                return self.fail("không có truyện này trong thư viện")
            nv = data.get("nhan_vat") or {}
            if not (nv.get("ten") or "").strip():
                return self.fail("nhân vật phải có tên")
            try:
                s = world.create_session(entry.get("folder") or "",
                                         entry.get("title") or "", nv)
            except ai.AiError as exc:
                return self.fail(str(exc))
            return self.json({"ok": True, "phien": s})

        if path == "/api/world/act":
            entry = self._entry(data.get("url") or "")
            if entry is None:
                return self.fail("không có truyện này trong thư viện")
            try:
                s = world.act(entry.get("folder") or "", data.get("id") or "",
                              data.get("hanh_dong") or "")
            except ai.AiError as exc:
                return self.fail(str(exc))
            return self.json({"ok": True, "phien": s})

        if path == "/api/world/session/delete":
            entry = self._entry(data.get("url") or "")
            if entry is None:
                return self.fail("không có truyện này trong thư viện")
            return self.json({"ok": world.delete_session(entry.get("folder") or "",
                                                         data.get("id") or "")})

        # ---------- doc bao ----------
        if path == "/api/bao/cap-nhat":
            if VIEC_BAO["dang"]:
                return self.fail("đang chạy một việc khác, đợi xong đã")
            _chay_nen("cap_nhat", lambda bao_tien_do: bao.cap_nhat(bao_tien_do))
            return self.json({"ok": True, "viec": dict(VIEC_BAO)})

        if path == "/api/bao/dich":
            if VIEC_BAO["dang"]:
                return self.fail("đang chạy một việc khác, đợi xong đã")
            cfg = store.load_settings()
            sang = (data.get("sang") or cfg.get("bao_ngon_ngu") or "vi")
            ngay = data.get("ngay") or ""
            kq = bao.doc_ngay(ngay, data.get("muc") or "", data.get("quoc") or "",
                              data.get("tim") or "", 0, int(data.get("so") or 60))
            can = [b for b in kq["bai"] if not b.get("dich")
                   or b["dich"].get("lang") != sang]
            if not can:
                return self.json({"ok": True, "xong_ngay": True, "so_dich": 0})

            def chay(bao_tien_do):
                ra = dich_bao.dich_bai(can, sang,
                                       bool(cfg.get("bao_dich_tom_tat", True)), bao_tien_do)
                ra["da_luu"] = bao.luu_dich(ngay, ra["ban_dich"])
                ra.pop("ban_dich", None)
                return ra

            _chay_nen("dich", chay)
            return self.json({"ok": True, "viec": dict(VIEC_BAO), "so_can": len(can)})

        if path == "/api/bao/tai-bai":
            # Bam vao bai nao thi lay bai do ve doc trong app (kieu "che do doc"),
            # de con dich duoc — nhung trang cua ho thi bo dich khong voi toi chu.
            ngay, link = data.get("ngay") or "", data.get("link") or ""
            if not link.startswith("http"):
                return self.fail("bài này không có link gốc")
            san = bao.doc_bai(ngay, link)
            if san and san.get("noi_dung") and san.get("doan"):
                return self.json({"ok": True, "bai": san, "tu_kho": True})
            try:
                ra = bao.boc_bai(APP.http, link)
            except Exception as exc:
                return self.fail(f"không đọc được nội dung: {type(exc).__name__}: {exc}")
            bao.luu_bai_day_du(ngay, link, ra["html"], ra["doan"])
            b = dict(san or {})
            b.update({"noi_dung": ra["html"], "doan": ra["doan"]})
            return self.json({"ok": True, "bai": b, "tu_kho": False})

        if path == "/api/bao/dich-bai":
            if VIEC_BAO["dang"]:
                return self.fail("đang chạy một việc khác, đợi xong đã")
            cfg = store.load_settings()
            sang = data.get("sang") or cfg.get("bao_ngon_ngu") or "vi"
            ngay, link = data.get("ngay") or "", data.get("link") or ""
            b = bao.doc_bai(ngay, link)
            if not b or not b.get("doan"):
                return self.fail("chưa có nội dung bài — mở lại bài một lần nữa")
            if (b.get("dich_bai") or {}).get("lang") == sang:
                return self.json({"ok": True, "xong_ngay": True,
                                  "doan": b["dich_bai"]["doan"]})

            def chay(bao_tien_do):
                ra = dich_bao.dich_doan(b["doan"], b.get("lang", ""), sang, bao_tien_do)
                bao.luu_dich_bai(ngay, link, sang, ra["doan"])
                return {"so_doan": len(ra["doan"]), "loi": ra["loi"]}

            _chay_nen("dich_bai", chay)
            return self.json({"ok": True, "viec": dict(VIEC_BAO)})

        if path == "/api/bao/nguon/them":
            if not (data.get("url") or "").startswith("http"):
                return self.fail("thiếu địa chỉ RSS")
            return self.json({"ok": True, **bao.them_nguon(data)})

        if path == "/api/bao/nguon/sua":
            return self.json({"ok": True, **bao.sua_nguon(data.get("ma") or "", data)})

        if path == "/api/bao/nguon/xoa":
            return self.json({"ok": True, **bao.xoa_nguon(data.get("ma") or "")})

        if path == "/api/bao/nguon/thu":
            # bam "Thu" khi them nguon moi: xem feed co doc duoc khong
            n = {"ma": "thu", "ten": data.get("ten") or "Thử", "url": data.get("url") or "",
                 "quoc": data.get("quoc") or "", "lang": data.get("lang") or "",
                 "muc": data.get("muc") or ""}
            try:
                ds = bao.doc_feed(APP.http, n, gioi_han=5)
            except Exception as exc:
                return self.fail(f"{type(exc).__name__}: {exc}")
            if not ds:
                return self.fail("đọc được trang nhưng không thấy bài nào — có phải RSS không?")
            return self.json({"ok": True, "so_bai": len(ds),
                              "vi_du": [{"tieu_de": b["tieu_de"], "muc": b["muc"]}
                                        for b in ds[:3]]})

        if path == "/api/bao/xoa-ngay":
            return self.json({"ok": bao.xoa_ngay(data.get("ngay") or "")})

        return self.fail("khong co API nay", 404)

    # ---------- cap nhat chuong moi ----------
    def cap_nhat_truyen(self, url: str):
        """Doc lai trang nguon, xem co chuong nao moi hon phan da tai khong."""
        app = APP
        entry = self._entry(url)
        if entry is None:
            return self.fail("không có truyện này trong thư viện")
        if url.startswith("local:"):
            return self.fail("sách nhập từ máy không có nguồn web để kiểm tra chương mới")
        src = app.registry.for_url(url)
        if src is None:
            return self.fail("không có plugin nào xử lý được link này")

        book = src.fetch_book(url)
        if not book.chapters:
            return self.fail("đọc lại trang nguồn nhưng không thấy chương nào")

        da_co = reader.list_chapters(entry.get("folder") or "")
        # Dung so thu tu lon nhat da tai, khong dung so luong file: neu lan truoc
        # co chuong tai loi thi so file it hon so chuong thuc su.
        moc = da_co[-1]["index"] if da_co else 0

        # Neu danh sach chuong o nguon bi doi (chen them chuong o giua, doi thu
        # tu) thi chuong da tai se khong con khop voi vi tri cu -> phai bao,
        # vi luc do tai tiep se ghep nham noi dung.
        canh_bao = ""
        if 0 < moc <= len(book.chapters):
            if not _cung_ten(da_co[-1]["title"], book.chapters[moc - 1].title):
                canh_bao = ("Danh sách chương ở nguồn đã thay đổi so với lúc tải "
                            "(chương số %d giờ là %r chứ không phải %r). Nên xoá "
                            "truyện rồi tải lại để khỏi ghép nhầm nội dung."
                            % (moc, book.chapters[moc - 1].title[:60],
                               da_co[-1]["title"][:60]))

        moi = len(book.chapters) - moc
        ket = {"ok": True, "moi": max(0, moi), "tong": len(book.chapters),
               "da_co": moc, "canh_bao": canh_bao}
        if moi <= 0:
            return self.json(ket)

        # Giao ca danh sach: chuong nao da co file thi trinh tai tu bo qua,
        # va buoc xuat file cuoi cung se dong lai EPUB/TXT gom du ca chuong moi.
        with app.lock:
            app.books[url] = (book, src)
        job = app.manager.submit(src, book, book.chapters,
                                 store.load_settings()["formats"])
        ket["viec"] = job.to_dict()
        return self.json(ket)


def _cung_ten(a: str, b: str) -> bool:
    chuan = lambda s: re.sub(r"\s+", " ", (s or "")).strip().lower()   # noqa: E731
    return chuan(a) == chuan(b)


def _lan_ip() -> str:
    """IP cua may nay trong mang noi bo (khong gui goi tin nao di that)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))              # UDP connect khong gui goi tin nao;
                                                # chi de he dieu hanh chon interface
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"


def serve(port: int) -> ThreadingHTTPServer:
    global APP
    APP = App()
    # bat "lan" trong cai dat -> dien thoai cung mang vao duoc (can khoi dong lai
    # app sau khi doi, va Windows co the hoi cho phep qua tuong lua lan dau)
    host = "0.0.0.0" if store.load_settings().get("lan") else "127.0.0.1"
    httpd = ThreadingHTTPServer((host, port), Handler)
    APP.bound_host = host
    APP.bound_port = httpd.server_address[1]
    return httpd
