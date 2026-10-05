# -*- coding: utf-8 -*-
"""Cao tai lieu tu web: dua mot (hay nhieu) dia chi trang, app do ra cac file
tai lieu trong do (PDF/DOCX/EPUB/TXT/MD/HTML), tai ve roi nhap thang vao thu vien.

Cach cu xu voi may chu nguoi ta (de khoi bi chan, va cung la phep lich su):
  - doc robots.txt truoc, duong nao bi cam thi khong do
  - nghi giua cac lan goi theo cai dat "delay" cua app (Http lo san)
  - chan so trang do va so file moi lan, khong di lan man ca site
"""
from __future__ import annotations

import re
import threading
import urllib.robotparser
from concurrent.futures import ThreadPoolExecutor
from pathlib import PurePosixPath
from urllib.parse import unquote, urljoin, urlparse

from bs4 import BeautifulSoup

from . import importer, store

# Duoi file bo nhap tai lieu doc duoc (xem core/importer.py)
DUOI_OK = {"pdf", "docx", "epub", "txt", "md", "markdown", "htm", "html", "xhtml"}
DUOI_BIET_NHUNG_CHUA_DOC = {"doc", "pptx", "ppt", "xlsx", "zip", "rar"}

KIEU_OK = {
    "application/pdf": "pdf",
    "application/epub+zip": "epub",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
    "text/markdown": "md",
}

MAX_FILE_MB = 80
_lock = threading.Lock()


def _duoi(url: str) -> str:
    duong = unquote(urlparse(url).path)
    return PurePosixPath(duong).suffix.lstrip(".").lower()


def _ten_file(url: str, chu: str = "") -> str:
    ten = unquote(PurePosixPath(urlparse(url).path).name)
    if not ten or "." not in ten:
        ten = re.sub(r"[\/:*?\"<>|]+", " ", chu or "tai-lieu").strip()[:80]
        d = _duoi(url)
        ten = f"{ten or 'tai-lieu'}.{d or 'bin'}"
    return ten


class _Robots:
    """Doc robots.txt mot lan cho moi ten mien roi nho lai."""

    def __init__(self, http):
        self.http = http
        self.bo = {}

    def cho_phep(self, url: str) -> bool:
        goc = "{0.scheme}://{0.netloc}".format(urlparse(url))
        rp = self.bo.get(goc)
        if rp is None:
            rp = urllib.robotparser.RobotFileParser()
            try:
                rp.parse(self.http.text(goc + "/robots.txt", timeout=10).splitlines())
            except Exception:
                rp = None          # khong co robots.txt = khong cam gi
            self.bo[goc] = rp
        if rp is None:
            return True
        try:
            return rp.can_fetch("*", url)
        except Exception:
            return True


def do_trang(http, dia_chi: list[str], sau: int = 1, max_trang: int = 60,
             max_file: int = 300, bao_tien_do=None) -> dict:
    """Do cac trang da cho (va trang con neu sau>0), tra ve danh sach file tai lieu."""
    robots = _Robots(http)
    hang_doi = [(u.strip(), 0) for u in dia_chi if u.strip().startswith("http")]
    da_tham: set[str] = set()
    tim_thay: dict[str, dict] = {}
    loi: list[str] = []

    while hang_doi and len(da_tham) < max_trang and len(tim_thay) < max_file:
        url, muc = hang_doi.pop(0)
        goc_url = url.split("#")[0]
        if goc_url in da_tham:
            continue
        da_tham.add(goc_url)
        if not robots.cho_phep(goc_url):
            loi.append("robots.txt chặn: " + goc_url)
            continue
        try:
            soup = http.soup(goc_url, timeout=20)
        except Exception as exc:
            loi.append(f"{goc_url}: {type(exc).__name__}")
            continue
        if bao_tien_do:
            bao_tien_do(len(da_tham), min(max_trang, len(da_tham) + len(hang_doi)), goc_url)

        tieu_de = soup.title.get_text(strip=True) if soup.title else ""
        cung_nha = urlparse(goc_url).netloc
        for a in soup.select("a[href]"):
            href = (a.get("href") or "").strip()
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue
            day_du = urljoin(goc_url, href).split("#")[0]
            d = _duoi(day_du)
            chu = a.get_text(" ", strip=True)
            if d in DUOI_OK or d in DUOI_BIET_NHUNG_CHUA_DOC:
                # file tai lieu co the nam o ten mien khac (CDN, GitHub release...)
                if day_du not in tim_thay and len(tim_thay) < max_file:
                    tim_thay[day_du] = {
                        "url": day_du, "ten": _ten_file(day_du, chu), "duoi": d,
                        "nhan": chu[:120], "tu_trang": goc_url, "tieu_de_trang": tieu_de,
                        "doc_duoc": d in DUOI_OK,
                    }
            elif muc < sau and urlparse(day_du).netloc == cung_nha:
                if day_du not in da_tham:
                    hang_doi.append((day_du, muc + 1))

    ds = sorted(tim_thay.values(), key=lambda x: (not x["doc_duoc"], x["ten"].lower()))
    return {"file": ds, "so_trang_da_do": len(da_tham), "loi": loi}


def tai_va_nhap(http, ds_url: list[str], ten_goi: dict | None = None,
                formats=None, bao_tien_do=None) -> dict:
    """Tai cac file da chon roi day qua bo nhap tai lieu san co -> vao thu vien."""
    ten_goi = ten_goi or {}
    xong = [0]
    tai_ve: list[tuple[str, bytes]] = []
    loi: list[str] = []

    def mot(url: str):
        try:
            r = http.get(url, timeout=60, stream=True)
            co = int(r.headers.get("Content-Length") or 0)
            if co > MAX_FILE_MB * 1048576:
                raise ValueError(f"file {co // 1048576} MB, quá {MAX_FILE_MB} MB")
            data = r.content
            if len(data) > MAX_FILE_MB * 1048576:
                raise ValueError("file quá lớn")
            ten = ten_goi.get(url) or _ten_file(url)
            if "." not in ten:
                kieu = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                ten += "." + KIEU_OK.get(kieu, "bin")
            with _lock:
                tai_ve.append((ten, data))
        except Exception as exc:
            with _lock:
                loi.append(f"{_ten_file(url)}: {type(exc).__name__}: {exc}")
        finally:
            with _lock:
                xong[0] += 1
                if bao_tien_do:
                    bao_tien_do(xong[0], len(ds_url), _ten_file(url))

    cfg = store.load_settings()
    with ThreadPoolExecutor(max_workers=min(4, max(1, int(cfg.get("threads", 4))))) as pool:
        list(pool.map(mot, ds_url))

    if not tai_ve:
        return {"sach": [], "loi": loi or ["không tải được file nào"]}
    ket = importer.import_files(tai_ve, formats=formats)
    ket["loi"] = loi + list(ket.get("loi") or [])
    return ket
