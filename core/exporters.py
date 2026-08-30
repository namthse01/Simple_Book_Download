"""Xuat truyen da tai ra TXT va EPUB (chi dung thu vien chuan cua Python)."""
from __future__ import annotations

import html
import re
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .store import safe_name

CSS = """body{font-family:Georgia,'Times New Roman',serif;line-height:1.65;margin:0 6%;}
h1{font-size:1.4em;text-align:center;margin:1.6em 0 1em;}
p{margin:0 0 .85em;text-indent:1.4em;text-align:justify;}
.cover{margin:0;padding:0;text-align:center;}
.cover img{max-width:100%;max-height:100%;}
"""


def _esc(s: str) -> str:
    return html.escape(s or "", quote=False)


def _chunks(items: list, size: int):
    if size and size > 0:
        for i in range(0, len(items), size):
            yield items[i:i + size]
    else:
        yield items


# --------------------------------------------------------------- TXT
def export_txt(book, chapters: list, out_dir: Path, split_every: int = 0) -> list[str]:
    """chapters = [(tieu_de_chuong, [dong, ...]), ...]"""
    out_dir.mkdir(parents=True, exist_ok=True)
    parts = list(_chunks(chapters, split_every))
    paths = []
    for i, part in enumerate(parts, 1):
        name = safe_name(book.title) + (f" - Tap {i}" if len(parts) > 1 else "") + ".txt"
        path = out_dir / name
        buf = [book.title]
        if book.author:
            buf.append("Tac gia: " + book.author)
        if book.url:
            buf.append("Nguon: " + book.url)
        buf.append("=" * 60)
        for title, lines in part:
            buf.append("")
            buf.append("")
            buf.append(title)
            buf.append("-" * 40)
            buf.extend(lines)
        path.write_text("\n".join(buf), encoding="utf-8")
        paths.append(str(path))
    return paths


# --------------------------------------------------------------- EPUB
def export_epub(book, chapters: list, out_dir: Path, split_every: int = 0,
                cover_bytes: bytes | None = None, cover_ext: str = "jpg") -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    parts = list(_chunks(chapters, split_every))
    paths = []
    for i, part in enumerate(parts, 1):
        label = f"Tap {i}" if len(parts) > 1 else ""
        name = safe_name(book.title) + (f" - {label}" if label else "") + ".epub"
        path = out_dir / name
        _write_epub(path, book, part, label, cover_bytes, cover_ext)
        paths.append(str(path))
    return paths


def _write_epub(path: Path, book, chapters: list, part_label: str,
                cover_bytes: bytes | None, cover_ext: str) -> None:
    uid = "urn:uuid:" + str(uuid.uuid4())
    title = book.title + (f" ({part_label})" if part_label else "")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    has_cover = bool(cover_bytes)
    cover_file = f"images/cover.{cover_ext}"
    media = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp",
             "gif": "image/gif"}.get(cover_ext, "image/jpeg")

    files: list[tuple[str, str]] = []          # (ten file, id) theo dung thu tu doc
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        # mimetype phai la muc dau tien va khong duoc nen
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip",
                   compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", CONTAINER_XML)
        z.writestr("OEBPS/style.css", CSS)

        if has_cover:
            z.writestr("OEBPS/" + cover_file, cover_bytes)
            z.writestr("OEBPS/cover.xhtml", _page(
                "Bia", '<div class="cover"><img src="' + cover_file + '" alt="Bia"/></div>'))
            files.append(("cover.xhtml", "cover-page"))

        info = ["<h1>" + _esc(title) + "</h1>"]
        if book.author:
            info.append("<p><b>Tac gia:</b> " + _esc(book.author) + "</p>")
        if book.genres:
            info.append("<p><b>The loai:</b> " + _esc(", ".join(book.genres)) + "</p>")
        if book.status:
            info.append("<p><b>Trang thai:</b> " + _esc(book.status) + "</p>")
        if book.url:
            info.append("<p><b>Nguon:</b> " + _esc(book.url) + "</p>")
        for line in (book.description or "").split("\n"):
            if line.strip():
                info.append("<p>" + _esc(line.strip()) + "</p>")
        z.writestr("OEBPS/info.xhtml", _page("Thong tin truyen", "\n".join(info)))
        files.append(("info.xhtml", "info"))

        toc_rows = []
        for n, (ctitle, lines) in enumerate(chapters, 1):
            fname = f"c{n:05d}.xhtml"
            body = ["<h1>" + _esc(ctitle) + "</h1>"]
            body += ["<p>" + _esc(l) + "</p>" for l in lines]
            z.writestr("OEBPS/" + fname, _page(ctitle, "\n".join(body)))
            files.append((fname, f"c{n:05d}"))
            toc_rows.append((fname, ctitle))

        z.writestr("OEBPS/nav.xhtml", _nav(title, toc_rows))
        z.writestr("OEBPS/toc.ncx", _ncx(uid, title, toc_rows))
        z.writestr("OEBPS/content.opf",
                   _opf(uid, title, book, now, files, has_cover, cover_file, media))


CONTAINER_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
    '<rootfiles><rootfile full-path="OEBPS/content.opf" '
    'media-type="application/oebps-package+xml"/></rootfiles></container>')


def _opf(uid, title, book, now, files, has_cover, cover_file, media) -> str:
    manifest = [
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
        '<item id="css" href="style.css" media-type="text/css"/>',
    ]
    if has_cover:
        manifest.append('<item id="cover-img" href="' + cover_file + '" media-type="'
                        + media + '" properties="cover-image"/>')
    for fname, fid in files:
        manifest.append('<item id="' + fid + '" href="' + fname
                        + '" media-type="application/xhtml+xml"/>')
    spine = "".join('<itemref idref="' + fid + '"/>' for _, fid in files)
    subjects = "".join("<dc:subject>" + _esc(g) + "</dc:subject>" for g in (book.genres or []))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
            'unique-identifier="bookid" xml:lang="vi">\n'
            '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
            '<dc:identifier id="bookid">' + uid + '</dc:identifier>\n'
            '<dc:title>' + _esc(title) + '</dc:title>\n'
            '<dc:creator>' + _esc(book.author or "Khong ro") + '</dc:creator>\n'
            '<dc:language>vi</dc:language>\n' + subjects
            + '<meta property="dcterms:modified">' + now + '</meta>\n'
            + ('<meta name="cover" content="cover-img"/>\n' if has_cover else "")
            + '</metadata>\n<manifest>' + "".join(manifest) + '</manifest>\n'
            + '<spine toc="ncx">' + spine + '</spine>\n</package>')


def _page(title: str, body: str) -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE html>\n<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="vi">\n'
            '<head><meta charset="utf-8"/><title>' + _esc(title) + '</title>'
            '<link rel="stylesheet" type="text/css" href="style.css"/></head>\n'
            '<body>' + body + '</body>\n</html>')


def _nav(title: str, rows: list) -> str:
    items = "".join('<li><a href="' + f + '">' + _esc(t) + '</a></li>' for f, t in rows)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" '
            'xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="vi">\n'
            '<head><meta charset="utf-8"/><title>' + _esc(title) + '</title></head><body>'
            '<nav epub:type="toc" id="toc"><h1>Muc luc</h1><ol>' + items + '</ol></nav>'
            '</body></html>')


def _ncx(uid: str, title: str, rows: list) -> str:
    points = "".join(
        '<navPoint id="n' + str(i) + '" playOrder="' + str(i) + '"><navLabel><text>'
        + _esc(t) + '</text></navLabel><content src="' + f + '"/></navPoint>'
        for i, (f, t) in enumerate(rows, 1))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
            '<head><meta name="dtb:uid" content="' + uid + '"/></head>'
            '<docTitle><text>' + _esc(title) + '</text></docTitle>'
            '<navMap>' + points + '</navMap></ncx>')


def guess_ext(url: str, content_type: str = "") -> str:
    m = re.search(r"\.(jpe?g|png|webp|gif)(?:$|[?#])", url or "", re.I)
    if m:
        return m.group(1).lower().replace("jpeg", "jpg")
    for key in ("png", "webp", "gif"):
        if key in (content_type or ""):
            return key
    return "jpg"
