"""Nhap tai lieu co san tren may (EPUB/TXT) vao thu vien.

Nguoi dung co file EPUB hoac TXT roi thi khong can tim nguon web nua: nhap
thang vao day, app tach chuong, luu cache y het truyen tai ve (moi chuong mot
file chuong/00001.txt) roi dong goi lai EPUB/TXT. Tu do doc trong app, loc
chu, xuat file... deu dung chung mot duong voi truyen tai tu web.

Ho tro gop nhieu file thanh MOT cuon — vi du sach bi tach thanh phan1.txt,
phan2.txt... thi chon het roi tich "Gop", moi file thanh mot (chum) chuong
theo thu tu.
"""
from __future__ import annotations

import codecs
import io
import posixpath
import re
import time
import unicodedata
import uuid
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

from . import store
from .cleaner import Cleaner, detect_boilerplate, html_to_lines
from .exporters import export_epub, export_txt
from .models import Book
from .store import safe_name


# ================================================================ TXT
def _decode(data: bytes) -> str:
    """Doan bang ma cua file TXT. Uu tien BOM, roi UTF-8; con lai thu dan."""
    for bom, enc in ((codecs.BOM_UTF8, "utf-8-sig"),
                     (codecs.BOM_UTF16_LE, "utf-16"),
                     (codecs.BOM_UTF16_BE, "utf-16")):
        if data.startswith(bom):
            return unicodedata.normalize("NFC", data.decode(enc, errors="replace"))
    for enc in ("utf-8", "gb18030", "cp1258", "cp1252"):
        try:
            return unicodedata.normalize("NFC", data.decode(enc))
        except (UnicodeDecodeError, UnicodeError):
            continue
    return unicodedata.normalize("NFC", data.decode("utf-8", errors="replace"))


# Dong mo dau chuong: "Chương 12", "Chapter 3:", "Hồi 5 - ...", "Quyển 2 Chương 7"...
_HEAD = re.compile(
    r"^\s*(?:quy[eêể]n\s+\d+\s*[-–—:.]*\s*)?"
    r"(?:ch[uư][oơ]ng|chapter|h[oôồ]i|ph[aâầ]n|t[aâập]p|m[uụ]c)"
    r"\s*(?:th[uứ]\s+)?\d+", re.IGNORECASE)
_HEAD_CN = re.compile(r"^\s*第\s*[0-9〇零一二三四五六七八九十百千万]+\s*[章节回卷]")
# Dong gach ngang ke duoi ten chuong (dinh dang TXT chinh app nay xuat ra)
_DASHES = re.compile(r"^\s*-{6,}\s*$")

_FALLBACK_LINES = 300          # khong tim thay chuong -> tu chia moi phan bay nhieu dong


def _dang_mo_dau(lines: list[str]) -> bool:
    """Phan chu truoc chuong dau co dang giu lam 'Mo dau' khong, hay chi la vai
    dong rac? Dem theo luong chu vi 2 doan van dai cung dang giu."""
    return len(lines) >= 3 or sum(len(l) for l in lines) >= 120


def _la_dau_chuong(lines: list[str], i: int) -> bool:
    s = lines[i]
    if not s or len(s) > 100:
        return False
    if _HEAD.match(s) or _HEAD_CN.match(s):
        return True
    # dong ngan ma ngay duoi la mot hang toan dau gach -> chac la ten chuong
    return i + 1 < len(lines) and _DASHES.match(lines[i + 1]) is not None \
        and _DASHES.match(s) is None


def split_txt(text: str, fallback_title: str) -> list[tuple[str, list[str]]]:
    """Tach van ban tho thanh [(ten chuong, [dong...]), ...]."""
    lines = [re.sub(r"[ \t\r\f\v]+", " ", l).strip() for l in text.split("\n")]
    lines = [l for l in lines if l]

    heads = [i for i in range(len(lines)) if _la_dau_chuong(lines, i)]
    if len(heads) >= 2:
        chapters: list[tuple[str, list[str]]] = []
        if _dang_mo_dau(lines[:heads[0]]):      # phan truoc chuong dau: loi tua/gioi thieu
            chapters.append(("Mở đầu", lines[:heads[0]]))
        for k, i in enumerate(heads):
            end = heads[k + 1] if k + 1 < len(heads) else len(lines)
            body = lines[i + 1:end]
            if body and _DASHES.match(body[0]):  # bo hang gach ke duoi ten chuong
                body = body[1:]
            if body:
                chapters.append((lines[i], body))
        if chapters:
            return chapters

    # Khong nhan ra chuong nao -> file ngan de nguyen, file dai tu chia phan
    if len(lines) <= _FALLBACK_LINES * 3 // 2:
        return [(fallback_title, lines)] if lines else []
    return [(f"Phần {n}", lines[i:i + _FALLBACK_LINES])
            for n, i in enumerate(range(0, len(lines), _FALLBACK_LINES), 1)]


def parse_txt(name: str, data: bytes) -> dict:
    title = re.sub(r"\.txt$", "", name, flags=re.I).strip() or "Không tên"
    chapters = split_txt(_decode(data), title)
    if not chapters:
        raise ValueError("file rỗng hoặc không đọc được chữ nào")
    return {"title": title, "author": "", "description": "", "genres": [],
            "cover": None, "cover_ext": "jpg", "chapters": chapters}


# ================================================================ EPUB
def _tag(el) -> str:
    return el.tag.rsplit("}", 1)[-1].lower()


def _strip_tags(html: str) -> str:
    s = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", s).strip()


_H_TAG = re.compile(r"<h([1-4])[^>]*>(.*?)</h\1\s*>", re.I | re.S)
_TITLE_TAG = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


def _doc_title(html: str, fallback: str) -> str:
    m = _H_TAG.search(html) or _TITLE_TAG.search(html)
    t = _strip_tags(m.group(2) if m and m.re is _H_TAG else (m.group(1) if m else ""))
    return t[:200] if t else fallback


def _bo_head(html: str) -> str:
    """Bo khoi <head> de chu trong <title> khong lot vao noi dung chuong."""
    return re.sub(r"(?is)<head\b.*?</head\s*>", "", html or "", count=1)


def _split_one_doc(html: str) -> list[tuple[str, list[str]]]:
    """Ca sach don trong 1 trang HTML -> tach lai theo the h1/h2/h3."""
    parts = re.split(r"(?is)(<h[123][^>]*>.*?</h[123]\s*>)", _bo_head(html))
    if len(parts) < 7:                          # duoi 3 tieu de thi khoi tach
        return []
    out = []
    intro = html_to_lines(parts[0])
    if _dang_mo_dau(intro):
        out.append(("Mở đầu", intro))
    for i in range(1, len(parts), 2):
        title = _strip_tags(parts[i]) or f"Chương {len(out) + 1}"
        body = html_to_lines(parts[i + 1] if i + 1 < len(parts) else "")
        if body:
            out.append((title, body))
    return out


def parse_epub(data: bytes) -> dict:
    z = zipfile.ZipFile(io.BytesIO(data))
    names = set(z.namelist())

    m = re.search(r'full-path="([^"]+)"',
                  z.read("META-INF/container.xml").decode("utf-8", "replace"))
    if not m:
        raise ValueError("EPUB hỏng: không thấy đường dẫn OPF trong container.xml")
    opf_path = m.group(1)
    opf_dir = posixpath.dirname(opf_path)
    root = ET.fromstring(z.read(opf_path))

    def _in_zip(href: str) -> str | None:
        p = posixpath.normpath(posixpath.join(opf_dir, unquote(href.split("#")[0])))
        return p if p in names else None

    # ----- metadata -----
    meta = {"title": "", "author": "", "description": "", "genres": []}
    cover_id = ""
    for el in root.iter():
        t = _tag(el)
        txt = (el.text or "").strip()
        if t == "title" and txt and not meta["title"]:
            meta["title"] = txt
        elif t == "creator" and txt and not meta["author"]:
            meta["author"] = txt
        elif t == "description" and txt and not meta["description"]:
            meta["description"] = _strip_tags(txt)
        elif t == "subject" and txt:
            meta["genres"].append(txt)
        elif t == "meta" and el.get("name") == "cover":
            cover_id = el.get("content") or ""

    # ----- manifest + spine -----
    items: dict[str, tuple[str, str, str]] = {}    # id -> (href, media-type, properties)
    spine: list[str] = []
    for el in root.iter():
        t = _tag(el)
        if t == "item" and el.get("id"):
            items[el.get("id")] = (el.get("href") or "", el.get("media-type") or "",
                                   el.get("properties") or "")
        elif t == "itemref" and el.get("idref"):
            spine.append(el.get("idref"))

    # ----- anh bia -----
    cover_bytes, cover_ext = None, "jpg"
    cands = ([cover_id] if cover_id in items else []) + \
        [i for i, (_, mt, pr) in items.items() if "cover-image" in pr]
    for cid in cands:
        href = items[cid][0]
        p = _in_zip(href)
        if p:
            raw = z.read(p)
            if len(raw) > 200:
                cover_bytes = raw
                ext = posixpath.splitext(p)[1].lstrip(".").lower()
                cover_ext = {"jpeg": "jpg"}.get(ext, ext) or "jpg"
                break

    # ----- chuong: doc theo dung thu tu spine -----
    docs = []
    for idref in spine:
        href, mtype, props = items.get(idref, ("", "", ""))
        if "nav" in props.split():
            continue
        if "html" not in mtype and not re.search(r"\.x?html?$", href, re.I):
            continue
        p = _in_zip(href)
        if p:
            docs.append(z.read(p).decode("utf-8", "replace"))
    if not docs:                                  # spine hong -> quet dai moi file html
        docs = [z.read(n).decode("utf-8", "replace")
                for n in sorted(names) if re.search(r"\.x?html?$", n, re.I)]

    chapters: list[tuple[str, list[str]]] = []
    for html in docs:
        title = _doc_title(html, f"Chương {len(chapters) + 1}")
        lines = html_to_lines(_bo_head(html))
        if not lines:
            continue
        while lines and lines[0] == title:        # tieu de lap lai o dau noi dung
            lines.pop(0)
        if lines:
            chapters.append((title, lines))

    if len(chapters) == 1:                        # ca sach don trong 1 file
        tach = _split_one_doc(docs[0] if len(docs) == 1 else "")
        if len(tach) >= 3:
            chapters = tach
    if not chapters:
        raise ValueError("không lấy được chữ nào từ EPUB này")

    meta["title"] = meta["title"] or "Không tên"
    return {**meta, "cover": cover_bytes, "cover_ext": cover_ext, "chapters": chapters}


# ================================================================ nhieu cap tieu de
def _sach(title, author="", chapters=None, description="", genres=None,
          cover=None, cover_ext="jpg") -> dict:
    return {"title": title or "Không tên", "author": author,
            "description": description, "genres": genres or [],
            "cover": cover, "cover_ext": cover_ext, "chapters": chapters or []}


def _chon_muc(levels: list[int]) -> int:
    """Tai lieu co nhieu cap tieu de (Phan > Chuong > Muc) thi tach chuong o cap
    nao? Lay cap co NHIEU tieu de nhat (hoa thi lay cap sau) — sach 3 Phan,
    40 Chuong se tach theo Chuong; Phan thanh tien to ten chuong."""
    dem: dict[int, int] = {}
    for lv in levels:
        dem[lv] = dem.get(lv, 0) + 1
    return max(dem.items(), key=lambda kv: (kv[1], kv[0]))[0]


def _ghep_chuong(items: list[tuple[int | None, str]]) -> list[tuple[str, list[str]]]:
    """items = [(cap tieu de hoac None neu la dong noi dung, chu), ...]."""
    levels = [lv for lv, _ in items if lv is not None]
    if len(levels) < 2:
        return []
    muc = _chon_muc(levels)
    if sum(1 for lv in levels if lv == muc) < 2:
        return []
    out: list[tuple[str, list[str]]] = []
    intro: list[str] = []
    title, body, prefix = None, [], ""

    def chot():
        nonlocal title, body
        if title is not None and body:
            out.append((title, body))
        title, body = None, []

    for lv, text in items:
        if lv is None or lv > muc:               # noi dung / tieu de con
            (body if title is not None else intro).append(text)
        elif lv < muc:                            # Phan/Quyen -> lam tien to
            chot()
            prefix = text
        else:
            chot()
            title = f"{prefix} · {text}" if prefix else text
    chot()
    if _dang_mo_dau(intro):
        out.insert(0, ("Mở đầu", intro))
    return out


def _bo_tieu_de_sach(items: list[tuple[int | None, str]]) -> str:
    """Tieu de dau tien la cap nong nhat va chi xuat hien 1 lan -> do la ten
    sach, khong phai chuong. Rut no ra khoi danh sach va tra ve."""
    if not items or items[0][0] is None:
        return ""
    lv0 = items[0][0]
    if sum(1 for lv, _ in items if lv is not None and lv <= lv0) == 1:
        return items.pop(0)[1]
    return ""


# ================================================================ DOCX
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def parse_docx(name: str, data: bytes) -> dict:
    z = zipfile.ZipFile(io.BytesIO(data))
    try:
        root = ET.fromstring(z.read("word/document.xml"))
    except KeyError:
        raise ValueError("không phải file .docx chuẩn (.doc đời cũ thì mở bằng "
                         "Word rồi Lưu thành .docx)") from None

    items: list[tuple[int | None, str]] = []
    for p in root.iter(_W + "p"):
        text = re.sub(r"\s+", " ", "".join(t.text or "" for t in p.iter(_W + "t"))).strip()
        if not text:
            continue
        lv = None
        ppr = p.find(_W + "pPr")
        if ppr is not None:
            ol = ppr.find(_W + "outlineLvl")            # muc trong Outline: 0..8
            if ol is not None and (ol.get(_W + "val") or "").isdigit():
                lv = int(ol.get(_W + "val")) + 1
            if lv is None:
                st = ppr.find(_W + "pStyle")
                m = re.fullmatch(r"(?i)(?:heading|h)\s*([1-6])",
                                 (st.get(_W + "val") if st is not None else "") or "")
                if m:
                    lv = int(m.group(1))
        if lv is not None and (lv > 6 or len(text) > 150):
            lv = None                                    # doan dai thi khong the la tieu de
        items.append((lv, text))

    title = author = ""
    try:
        for el in ET.fromstring(z.read("docProps/core.xml")).iter():
            txt = (el.text or "").strip()
            if _tag(el) == "title" and txt:
                title = txt
            elif _tag(el) == "creator" and txt:
                author = txt
    except Exception:
        pass

    # rut tieu de sach o dau ra TRUOC khi ghep, ke ca khi metadata da co ten —
    # neu de lai, Heading do se thanh tien to dinh vao moi ten chuong
    tieu_de_dau = _bo_tieu_de_sach(items)
    title = title or tieu_de_dau \
        or re.sub(r"\.docx$", "", name, flags=re.I).strip() or "Không tên"
    chapters = _ghep_chuong(items)
    if not chapters:                                     # khong dung Heading -> do theo chu
        chapters = split_txt("\n".join(t for _, t in items), title)
    if not chapters:
        raise ValueError("file không có chữ nào")
    return _sach(title, author, chapters)


# ================================================================ PDF
def parse_pdf(name: str, data: bytes) -> dict:
    try:
        import pymupdf
    except ImportError:
        try:
            import fitz as pymupdf                       # ten cu cua PyMuPDF
        except ImportError:
            raise ValueError("đọc PDF cần thư viện PyMuPDF — mở cmd chạy: "
                             "python -m pip install pymupdf") from None

    doc = pymupdf.open(stream=data, filetype="pdf")
    if doc.needs_pass:
        raise ValueError("PDF có mật khẩu, mở khoá trước rồi hãy nhập")
    meta = doc.metadata or {}
    fallback = re.sub(r"\.pdf$", "", name, flags=re.I).strip() or "Không tên"
    title = re.sub(r"\s+", " ", meta.get("title") or "").strip() or fallback
    author = re.sub(r"\s+", " ", meta.get("author") or "").strip()

    def dong(page) -> list[str]:
        # "blocks" gom cac dong cung mot doan lai voi nhau -> doan van lien mach,
        # khong bi be vun theo tung dong nhu get_text thuong
        out = []
        for b in page.get_text("blocks"):
            if len(b) > 6 and b[6] != 0:                 # khoi anh
                continue
            s = re.sub(r"\s+", " ", b[4]).strip()
            if s:
                out.append(s)
        return out

    n = doc.page_count
    chapters: list[tuple[str, list[str]]] = []

    # Co muc luc (bookmark) thi tach theo do — chinh xac nhat
    toc = [t for t in (doc.get_toc(simple=True) or []) if (t[1] or "").strip()]
    if len(toc) >= 2:
        muc = _chon_muc([t[0] for t in toc])
        marks, prefix = [], ""
        for lv, t, pg in toc:
            t = re.sub(r"\s+", " ", t).strip()
            if lv < muc:
                prefix = t
            elif lv == muc:
                marks.append((f"{prefix} · {t}" if prefix else t, max(0, (pg or 1) - 1)))
        for i in range(1, len(marks)):                   # trang phai khong giam dan
            if marks[i][1] < marks[i - 1][1]:
                marks[i] = (marks[i][0], marks[i - 1][1])
        if len(marks) >= 2:
            if marks[0][1] >= 1:
                intro = [l for p in range(marks[0][1]) for l in dong(doc[p])]
                if _dang_mo_dau(intro):
                    chapters.append(("Mở đầu", intro))
            for i, (t, a) in enumerate(marks):
                b = marks[i + 1][1] if i + 1 < len(marks) else n
                lines = [l for p in range(a, max(a + 1, b)) for l in dong(doc[p])]
                if lines:
                    chapters.append((t, lines))

    if not chapters:                                     # khong co muc luc -> do theo chu
        lines = [l for p in range(n) for l in dong(doc[p])]
        if not lines:
            raise ValueError("PDF này là ảnh scan, không có chữ để lấy "
                             "(cần OCR nên chưa hỗ trợ)")
        chapters = split_txt("\n".join(lines), title)
    return _sach(title, author, chapters)


# ================================================================ HTML & Markdown
def parse_html(name: str, data: bytes) -> dict:
    html = _decode(data)
    fallback = re.sub(r"\.x?html?$", "", name, flags=re.I).strip() or "Không tên"
    m = _TITLE_TAG.search(html)
    title = (_strip_tags(m.group(1)) if m else "") or fallback
    chapters = _split_one_doc(html)
    if not chapters:
        lines = html_to_lines(_bo_head(html))
        if not lines:
            raise ValueError("trang không có chữ nào")
        chapters = [(title, lines)]
    return _sach(title, "", chapters)


_MD_HEAD = re.compile(r"^(#{1,4})\s+(.+?)\s*#*\s*$")


def _md_chu(s: str) -> str:
    s = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", s)      # anh -> loi chu thich
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)       # link -> phan chu
    return s.strip()


def parse_md(name: str, data: bytes) -> dict:
    fallback = re.sub(r"\.(md|markdown)$", "", name, flags=re.I).strip() or "Không tên"
    items: list[tuple[int | None, str]] = []
    trong_code = False
    for raw in _decode(data).split("\n"):
        s = raw.rstrip()
        if s.lstrip().startswith("```"):
            trong_code = not trong_code
            continue
        if trong_code:
            if s.strip():
                items.append((None, s.strip()))
            continue
        m = _MD_HEAD.match(s)
        if m:
            items.append((len(m.group(1)), _md_chu(m.group(2))))
        elif _md_chu(s):
            items.append((None, _md_chu(s)))

    title = _bo_tieu_de_sach(items) or fallback
    chapters = _ghep_chuong(items)
    if not chapters:
        chapters = split_txt("\n".join(t for _, t in items), title)
    if not chapters:
        raise ValueError("file không có chữ nào")
    return _sach(title, "", chapters)


# ================================================================ luu vao thu vien
def _parse_one(name: str, data: bytes) -> dict:
    low = name.lower()
    if low.endswith(".epub"):
        d = parse_epub(data)
    elif low.endswith(".txt"):
        d = parse_txt(name, data)
    elif low.endswith(".docx"):
        d = parse_docx(name, data)
    elif low.endswith(".pdf"):
        d = parse_pdf(name, data)
    elif low.endswith((".html", ".htm", ".xhtml")):
        d = parse_html(name, data)
    elif low.endswith((".md", ".markdown")):
        d = parse_md(name, data)
    elif low.endswith(".doc"):
        raise ValueError(".doc đời cũ chưa đọc được — mở bằng Word rồi "
                         "Lưu thành .docx")
    else:
        raise ValueError("chỉ nhận .epub, .txt, .docx, .pdf, .html, .md")
    d["file"] = name
    return d


def _merge(parsed: list[dict], title: str, author: str) -> dict:
    """Gop nhieu file thanh mot cuon: chuong noi duoi nhau theo thu tu file."""
    chapters: list[tuple[str, list[str]]] = []
    for d in parsed:
        if len(d["chapters"]) == 1:
            # moi file mot khoi chu -> lay ten sach con lam ten chuong
            chapters.append((d["title"], d["chapters"][0][1]))
        else:
            chapters.extend(d["chapters"])
    first = parsed[0]
    cover = next((d for d in parsed if d.get("cover")), None)
    return {
        "title": title or first["title"],
        "author": author or next((d["author"] for d in parsed if d.get("author")), ""),
        "description": first.get("description", ""),
        "genres": first.get("genres", []),
        "cover": cover["cover"] if cover else None,
        "cover_ext": cover["cover_ext"] if cover else "jpg",
        "chapters": chapters,
    }


def _folder_moi(out_root: Path, title: str) -> Path:
    base = safe_name(title)
    folder = out_root / base
    n = 2
    while folder.exists():
        folder = out_root / f"{base} ({n})"
        n += 1
    return folder


def _save_book(d: dict, cfg: dict, formats: list[str]) -> dict:
    chuan = lambda s: unicodedata.normalize("NFC", s or "")   # noqa: E731
    book = Book(title=chuan(d["title"]), url="", source="nhập từ máy",
                author=chuan(d.get("author", "")),
                description=chuan(d.get("description", "")),
                genres=d.get("genres", []))

    folder = _folder_moi(Path(cfg["output_dir"]), book.title)
    cache = folder / "chuong"
    cache.mkdir(parents=True, exist_ok=True)
    for i, (ctitle, lines) in enumerate(d["chapters"], 1):
        (cache / f"{i:05d}.txt").write_text(
            ctitle + "\n" + "\n".join(lines), encoding="utf-8")

    if d.get("cover"):
        (folder / f"cover.{d.get('cover_ext') or 'jpg'}").write_bytes(d["cover"])

    # lam sach + dong goi giong het truyen tai tu web
    cleaner = Cleaner(store.load_filters())
    drop = detect_boilerplate([l for _, l in d["chapters"]]) \
        if cfg.get("auto_clean", True) else set()
    chapters = [(t, cleaner.clean(l, drop)) for t, l in d["chapters"]]
    chapters = [(t, l) for t, l in chapters if l]
    if not chapters:
        raise ValueError("nội dung rỗng sau khi lọc")

    split = int(cfg.get("split_every", 0) or 0)
    files: list[str] = []
    if "epub" in formats:
        files += export_epub(book, chapters, folder, split,
                             d.get("cover"), d.get("cover_ext") or "jpg")
    if "txt" in formats:
        files += export_txt(book, chapters, folder, split)

    key = "local:" + uuid.uuid4().hex[:12]
    entry = {
        "title": book.title, "author": book.author, "url": key,
        "source": "nhập từ máy",
        "cover": ("/api/cover?url=" + key) if d.get("cover") else "",
        "chapters": len(chapters), "folder": str(folder), "files": files,
        "updated": time.time(),
    }
    store.upsert_library(entry)
    return entry


def import_files(files: list[tuple[str, bytes]], merge=False,
                 title="", author="", formats=None, chi_thu=False) -> dict:
    """files = [(ten file, bytes), ...] -> {"sach": [muc thu vien], "loi": [chuoi]}.

    chi_thu=True: chi tach chuong roi tra ve muc luc de xem truoc,
    khong ghi gi vao dia ca.
    """
    cfg = store.load_settings()
    formats = [f for f in (formats or cfg["formats"]) if f in ("epub", "txt")] or ["epub"]

    parsed, errors = [], []
    for name, data in files:
        try:
            parsed.append(_parse_one(name, data))
        except Exception as exc:
            errors.append(f"{name}: {exc}")

    entries = []
    if parsed:
        goi = [_merge(parsed, title, author)] if (merge and len(parsed) > 1) else parsed
        if not merge and len(parsed) == 1:
            if title:
                goi[0]["title"] = title
            if author:
                goi[0]["author"] = author
        if chi_thu:
            entries = [{"file": d.get("file", ""), "title": d["title"],
                        "author": d.get("author", ""), "chapters": len(d["chapters"]),
                        "muc_luc": [t for t, _ in d["chapters"]][:300]}
                       for d in goi]
            return {"sach": entries, "loi": errors}
        for d in goi:
            try:
                entries.append(_save_book(d, cfg, formats))
            except Exception as exc:
                errors.append(f"{d.get('file') or d['title']}: {exc}")
    return {"sach": entries, "loi": errors}
