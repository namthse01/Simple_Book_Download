"""Doc/ghi cai dat, bo loc va so thu vien."""
from __future__ import annotations

import json
import re
import threading
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

DEFAULT_SETTINGS = {
    "output_dir": str(ROOT / "Truyen"),
    "threads": 6,          # so luong tai song song
    "delay": 0.4,          # giay nghi giua 2 lan goi cung 1 web
    "retries": 4,
    "timeout": 25,
    "proxy": "",
    "formats": ["epub", "txt"],
    "auto_clean": True,    # tu do va bo dong rac lap lai o moi chuong
    "split_every": 0,      # >0 = tach thanh nhieu tap, moi tap bay nhieu chuong
    "port": 8765,
}

DEFAULT_FILTERS = {"remove": [], "drop_line": [], "regex": [], "names": {}}

_lock = threading.Lock()


def _read(path: Path, default: dict) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        merged = dict(default)
        merged.update(data if isinstance(data, dict) else {})
        return merged
    except Exception:
        return dict(default)


def _write(path: Path, data) -> None:
    with _lock:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_settings() -> dict:
    s = _read(DATA / "settings.json", DEFAULT_SETTINGS)
    s["threads"] = max(1, min(32, int(s.get("threads", 6))))
    s["delay"] = max(0.0, float(s.get("delay", 0.4)))
    return s


def save_settings(data: dict) -> dict:
    cur = load_settings()
    for k in DEFAULT_SETTINGS:
        if k in data:
            cur[k] = data[k]
    _write(DATA / "settings.json", cur)
    return cur


def load_filters() -> dict:
    return _read(DATA / "filters.json", DEFAULT_FILTERS)


def save_filters(data: dict) -> dict:
    cur = dict(DEFAULT_FILTERS)
    for k in DEFAULT_FILTERS:
        if k in data:
            cur[k] = data[k]
    _write(DATA / "filters.json", cur)
    return cur


# ---------- so thu vien ----------
def load_library() -> list:
    try:
        return json.loads((DATA / "library.json").read_text(encoding="utf-8"))
    except Exception:
        return []


def save_library(items: list) -> None:
    _write(DATA / "library.json", items)


def upsert_library(entry: dict) -> list:
    items = load_library()
    items = [x for x in items if x.get("url") != entry.get("url")]
    items.insert(0, entry)
    save_library(items)
    return items


def remove_library(url: str) -> list:
    items = [x for x in load_library() if x.get("url") != url]
    save_library(items)
    return items


# ---------- ten file an toan tren Windows ----------
_BAD = re.compile(r'[<>:"/\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
             *(f"LPT{i}" for i in range(1, 10))}


def safe_name(name: str, limit: int = 90) -> str:
    name = unicodedata.normalize("NFC", (name or "").strip())
    name = _BAD.sub("", name).replace("\n", " ")
    name = re.sub(r"\s+", " ", name).strip(" .")
    if name.upper().split(".")[0] in _RESERVED:
        name = "_" + name
    return (name[:limit].strip(" .") or "khong-ten")
