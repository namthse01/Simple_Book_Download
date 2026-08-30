"""Khung nguon truyen (plugin) + bo nap plugin tu thu muc plugins/."""
from __future__ import annotations

import importlib.util
import sys
import traceback
from pathlib import Path
from urllib.parse import urlparse

from .models import Book, BookBrief, Chapter  # noqa: F401  (plugin import lai tu day)


class Source:
    """Lop co so cho moi nguon truyen.

    Plugin chi can ke thua lop nay va cai dat 4 ham duoi.
    File plugin dat trong thu muc plugins/, app tu nap khi khoi dong.
    """

    id = "base"
    name = "Base"
    domains: list[str] = []       # cac domain plugin nay xu ly duoc
    base_url = ""
    mirrors: list[str] = []       # domain du phong khi domain chinh bi chan
    can_search = True
    priority = 50                 # so nho = uu tien cao khi chon plugin cho 1 URL

    def __init__(self, http):
        self.http = http

    # ---------- nhan dien ----------
    def can_handle(self, url: str) -> bool:
        host = urlparse(url).netloc.lower().removeprefix("www.")
        return any(host == d or host.endswith("." + d) for d in self.domains)

    # ---------- cac ham plugin phai cai dat ----------
    def search(self, keyword: str, page: int = 1) -> list[BookBrief]:
        return []

    def fetch_book(self, url: str) -> Book:
        raise NotImplementedError

    def fetch_chapters(self, book: Book) -> list[Chapter]:
        return book.chapters

    def fetch_content(self, chapter: Chapter) -> str:
        """Tra ve HTML tho cua noi dung chuong (chua lam sach)."""
        raise NotImplementedError

    # ---------- tien ich ----------
    def info(self) -> dict:
        return {
            "id": self.id, "name": self.name, "base_url": self.base_url,
            "domains": self.domains, "can_search": self.can_search,
        }


class Registry:
    """Nap va giu tat ca plugin nguon."""

    def __init__(self, http, plugin_dir: Path):
        self.http = http
        self.plugin_dir = Path(plugin_dir)
        self.sources: list[Source] = []
        self.errors: list[str] = []

    def load(self):
        self.sources.clear()
        self.errors.clear()
        classes = []
        for path in sorted(self.plugin_dir.glob("*.py")):
            if path.name.startswith("_"):
                continue
            mod_name = "taitruyen_plugin_" + path.stem
            try:
                spec = importlib.util.spec_from_file_location(mod_name, path)
                mod = importlib.util.module_from_spec(spec)
                sys.modules[mod_name] = mod
                spec.loader.exec_module(mod)
            except Exception:
                self.errors.append(f"{path.name}: {traceback.format_exc(limit=2)}")
                continue
            for obj in vars(mod).values():
                if (isinstance(obj, type) and issubclass(obj, Source)
                        and obj is not Source and obj.__module__ == mod_name):
                    classes.append(obj)
        for cls in sorted(classes, key=lambda c: c.priority):
            try:
                self.sources.append(cls(self.http))
            except Exception:
                self.errors.append(f"{cls.__name__}: {traceback.format_exc(limit=2)}")
        return self.sources

    def by_id(self, sid: str) -> Source | None:
        return next((s for s in self.sources if s.id == sid), None)

    def for_url(self, url: str) -> Source | None:
        """Chon plugin chuyen biet truoc, khong co thi rot ve plugin tong quat."""
        for s in self.sources:
            if s.domains and s.can_handle(url):
                return s
        return next((s for s in self.sources if not s.domains), None)

    def searchable(self) -> list[Source]:
        return [s for s in self.sources if s.can_search]
