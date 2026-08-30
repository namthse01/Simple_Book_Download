"""Hang doi tai truyen: tai song song, tu nghi giua cac lan goi, tai tiep khi dut."""
from __future__ import annotations

import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import store
from .cleaner import Cleaner, detect_boilerplate, html_to_lines
from .exporters import export_epub, export_txt, guess_ext
from .store import safe_name


class Job:
    def __init__(self, book, chapters, formats):
        self.id = uuid.uuid4().hex[:10]
        self.book = book
        self.chapters = chapters
        self.formats = formats or ["epub"]
        self.total = len(chapters)
        self.done = 0
        self.cached = 0                 # so chuong da co san tu lan tai truoc
        self.failed: list[dict] = []
        self.status = "dang cho"        # dang cho | dang tai | dang xuat | xong | loi | da huy
        self.message = ""
        self.files: list[str] = []
        self.folder = ""
        self.created = time.time()
        self.finished = 0.0
        self.cancel = threading.Event()
        self._lock = threading.Lock()

    def tick(self, ok: bool, chapter=None, err: str = ""):
        with self._lock:
            self.done += 1
            if not ok and chapter is not None:
                self.failed.append({"index": chapter.index, "title": chapter.title,
                                    "url": chapter.url, "loi": err[:200]})

    def to_dict(self) -> dict:
        pct = round(self.done * 100 / self.total, 1) if self.total else 0.0
        return {
            "id": self.id, "title": self.book.title, "author": self.book.author,
            "cover": self.book.cover, "url": self.book.url,
            "total": self.total, "done": self.done, "cached": self.cached,
            "percent": pct, "status": self.status, "message": self.message,
            "failed": self.failed[:50], "failed_count": len(self.failed),
            "files": self.files, "folder": self.folder,
            "created": self.created, "finished": self.finished,
        }


class Manager:
    """Chay toi da 1 truyen mot luc de khoi bi web chan."""

    def __init__(self, registry):
        self.registry = registry
        self.jobs: dict[str, Job] = {}
        self.order: list[str] = []
        self._queue: list[Job] = []
        self._lock = threading.Lock()
        self._worker: threading.Thread | None = None

    # ---------- API ----------
    def submit(self, source, book, chapters, formats) -> Job:
        job = Job(book, chapters, formats)
        with self._lock:
            self.jobs[job.id] = job
            self.order.insert(0, job.id)
            self._queue.append((job, source))
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._loop, daemon=True)
                self._worker.start()
        return job

    def cancel(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if not job or job.status in ("xong", "loi", "da huy"):
            return False
        job.cancel.set()
        if job.status == "dang cho":
            job.status = "da huy"
            job.finished = time.time()
        return True

    def list(self) -> list[dict]:
        return [self.jobs[i].to_dict() for i in self.order if i in self.jobs]

    def clear_finished(self):
        with self._lock:
            keep = [i for i in self.order
                    if self.jobs[i].status not in ("xong", "loi", "da huy")]
            self.jobs = {i: self.jobs[i] for i in keep}
            self.order = keep

    # ---------- vong chay ----------
    def _loop(self):
        while True:
            with self._lock:
                if not self._queue:
                    self._worker = None
                    return
                job, source = self._queue.pop(0)
            if job.cancel.is_set():
                job.status = "da huy"
                job.finished = time.time()
                continue
            try:
                self._run(job, source)
            except Exception:
                job.status = "loi"
                job.message = traceback.format_exc(limit=3)
                job.finished = time.time()

    def _run(self, job: Job, source):
        cfg = store.load_settings()
        out_root = Path(cfg["output_dir"])
        folder = out_root / safe_name(job.book.title)
        cache = folder / "chuong"
        cache.mkdir(parents=True, exist_ok=True)
        job.folder = str(folder)
        job.status = "dang tai"

        paths = {c.index: cache / f"{c.index:05d}.txt" for c in job.chapters}
        todo = [c for c in job.chapters if not self._cached(paths[c.index])]
        job.cached = job.total - len(todo)
        job.done = job.cached

        if todo:
            with ThreadPoolExecutor(max_workers=cfg["threads"]) as pool:
                list(pool.map(lambda c: self._one(job, source, c, paths[c.index]), todo))

        if job.cancel.is_set():
            job.status = "da huy"
            job.message = f"Da dung. Da luu {job.done}/{job.total} chuong, lan sau tai tiep."
            job.finished = time.time()
            return

        # thu lai cac chuong loi mot lan nua, cham hon
        if job.failed:
            retry = [c for c in job.chapters
                     if any(f["index"] == c.index for f in job.failed)]
            job.failed.clear()
            time.sleep(2)
            for c in retry:
                if job.cancel.is_set():
                    break
                self._one(job, source, c, paths[c.index], count=False)

        job.status = "dang xuat"
        job.message = "Dang lam sach chu va dong goi file..."
        self._export(job, cfg, paths)

        job.status = "xong"
        job.finished = time.time()
        job.message = (f"Xong {job.total - len(job.failed)}/{job.total} chuong"
                       + (f", {len(job.failed)} chuong loi" if job.failed else ""))
        store.upsert_library({
            "title": job.book.title, "author": job.book.author, "url": job.book.url,
            "source": job.book.source, "cover": job.book.cover,
            "chapters": job.total, "folder": str(folder), "files": job.files,
            "updated": time.time(),
        })

    @staticmethod
    def _cached(path: Path) -> bool:
        try:
            return path.stat().st_size > 20
        except OSError:
            return False

    def _one(self, job: Job, source, chapter, path: Path, count=True):
        if job.cancel.is_set():
            if count:
                job.tick(True)
            return
        try:
            html = source.fetch_content(chapter)
            lines = html_to_lines(html)
            if not lines:
                raise RuntimeError("Chuong rong hoac web tra ve trang chan.")
            path.write_text(chapter.title + "\n" + "\n".join(lines), encoding="utf-8")
            if count:
                job.tick(True)
        except Exception as exc:
            if count:
                job.tick(False, chapter, f"{type(exc).__name__}: {exc}")
            else:
                job.failed.append({"index": chapter.index, "title": chapter.title,
                                   "url": chapter.url, "loi": str(exc)[:200]})

    # ---------- xuat file ----------
    def _export(self, job: Job, cfg: dict, paths: dict):
        cleaner = Cleaner(store.load_filters())
        raw: list[tuple[str, list[str]]] = []
        for c in job.chapters:
            p = paths[c.index]
            if not self._cached(p):
                continue
            body = p.read_text(encoding="utf-8").split("\n")
            raw.append((body[0] or c.title, body[1:]))

        drop = set()
        if cfg.get("auto_clean", True):
            drop = detect_boilerplate([lines for _, lines in raw])

        chapters = [(title, cleaner.clean(lines, drop)) for title, lines in raw]
        chapters = [(t, l) for t, l in chapters if l]
        if not chapters:
            raise RuntimeError("Khong co chuong nao tai duoc, khong the xuat file.")

        folder = Path(job.folder)
        split = int(cfg.get("split_every", 0) or 0)
        files: list[str] = []

        cover_bytes, cover_ext = None, "jpg"
        if job.book.cover and "epub" in job.formats:
            try:
                r = self.registry.http.get(job.book.cover, referer=job.book.url, timeout=20)
                if len(r.content) > 500:
                    cover_bytes = r.content
                    cover_ext = guess_ext(job.book.cover, r.headers.get("Content-Type", ""))
            except Exception:
                pass

        if "epub" in job.formats:
            files += export_epub(job.book, chapters, folder, split, cover_bytes, cover_ext)
        if "txt" in job.formats:
            files += export_txt(job.book, chapters, folder, split)
        job.files = files
