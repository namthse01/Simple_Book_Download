"""Doc lai truyen da tai va xoa truyen khoi thu vien.

Chuong da tai nam san trong <thu muc truyen>/chuong/00001.txt, dong dau la ten
chuong, cac dong sau la noi dung -> dung luon lam nguon cho trinh doc, khong
can tai lai tu web.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from . import store
from .cleaner import Cleaner, detect_boilerplate


def _cache_dir(folder: str | Path) -> Path:
    return Path(folder) / "chuong"


def list_chapters(folder: str | Path) -> list[dict]:
    """Danh sach chuong da tai. Chi doc dong dau moi file cho nhanh."""
    d = _cache_dir(folder)
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.glob("*.txt")):
        try:
            idx = int(p.stem)
        except ValueError:
            continue
        try:
            with p.open(encoding="utf-8") as f:
                title = f.readline().strip()
        except OSError:
            continue
        out.append({"index": idx, "title": title or f"Chương {idx}"})
    out.sort(key=lambda x: x["index"])
    return out


_bp_cache: dict[tuple, set] = {}


def _boilerplate(folder: str | Path) -> set[str]:
    """Dong rac lap lai o hau het cac chuong (chan trang, ten truyen, ten tac gia).

    Luc xuat EPUB/TXT da co buoc nay roi; lam them o day de doc trong app thay
    giong het file xuat ra. Chi doc mau vai chuong cho nhanh, va nho ket qua lai.
    """
    files = sorted(_cache_dir(folder).glob("*.txt"))
    key = (str(folder), len(files))
    if key in _bp_cache:
        return _bp_cache[key]

    if len(files) < 4:
        _bp_cache[key] = set()
        return _bp_cache[key]

    step = max(1, len(files) // 15)
    mau = []
    for p in files[::step][:15]:
        try:
            mau.append(p.read_text(encoding="utf-8").split("\n")[1:])
        except OSError:
            pass
    _bp_cache[key] = detect_boilerplate(mau)
    return _bp_cache[key]


def read_chapter(folder: str | Path, index: int) -> dict | None:
    """Noi dung mot chuong, da ap dung bo loc chu giong luc xuat file."""
    p = _cache_dir(folder) / f"{int(index):05d}.txt"
    if not p.is_file():
        return None
    raw = p.read_text(encoding="utf-8").split("\n")
    title = raw[0].strip() if raw else f"Chương {index}"
    lines = Cleaner(store.load_filters()).clean(raw[1:], _boilerplate(folder))
    # Vai trang nhet lai ten chuong vao dau noi dung -> bo di cho khoi lap voi
    # tieu de hien ben tren. Phai lam SAU khi loc, vi truoc do no con bi ke sau
    # may dong rac khac nen khong nam o vi tri dau tien.
    while lines and lines[0].strip() == title:
        lines.pop(0)
    return {"index": int(index), "title": title, "lines": lines}


def delete_book(url: str) -> dict:
    """Xoa truyen khoi so thu vien va xoa ca thu muc file cua no.

    Chi xoa thu muc nam ben trong thu muc luu truyen da cau hinh, de mot muc
    thu vien hong khong the khien app xoa nham cho khac tren o dia.
    """
    entry = next((x for x in store.load_library() if x.get("url") == url), None)
    if entry is None:
        return {"ok": False, "loi": "khong co truyen nay trong thu vien"}

    folder = entry.get("folder") or ""
    da_xoa_file = False
    loi = ""
    if folder:
        try:
            root = Path(store.load_settings()["output_dir"]).resolve()
            target = Path(folder).resolve()
            if target != root and target.is_relative_to(root):
                if target.is_dir():
                    shutil.rmtree(target)
                    da_xoa_file = True
            else:
                loi = "thư mục nằm ngoài nơi lưu truyện nên không xoá file"
        except OSError as exc:
            loi = f"không xoá được thư mục: {exc}"

    store.remove_library(url)
    return {"ok": True, "da_xoa_file": da_xoa_file, "loi": loi,
            "ten": entry.get("title", ""), "thu_vien": store.load_library()}
