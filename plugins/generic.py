"""Plugin tong quat: doan cau truc HTML cho web la (dan link la thu tai)."""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

from core.sources import Book, Chapter, Source

CHAP_TEXT = re.compile(
    r"^\s*(ch[uư][oơ]ng|chapter|chuong|h[oồ]i|t[aậ]p|quy[eể]n|ch\.)\s*[:.\-]?\s*\d+", re.I)
CHAP_HREF = re.compile(r"(chuong|chapter|/c\d+(?:[./-]|$)|/ch\d+|episode|/p\d+\.html)", re.I)
PAGE_HREF = re.compile(r"(trang[-=/](\d+)|[?&]page=(\d+)|/page/(\d+))", re.I)

DROP_IN_CONTENT = [
    "script", "style", "ins", "iframe", "noscript", "nav", "header", "footer",
    "form", "button", ".ads", "[class*='ads']", "[id*='ads']", ".quangcao",
    ".share", ".social", ".comment", ".comments", ".pagination", ".breadcrumb",
]


class GenericSource(Source):
    id = "generic"
    name = "Nguồn chung (tự đoán)"
    domains = []            # rong = nhan moi URL khong khop plugin nao khac
    can_search = False
    priority = 999

    # ---------- trang truyen ----------
    def fetch_book(self, url: str) -> Book:
        soup = self.http.soup(url)
        # Nhieu web dat og:title la khau hieu chung cho MOI trang
        # ("Truyen hay, full dich"...), nen chi dung no khi khong con gi khac.
        # <h1> va <title> mo ta dung trang hien tai hon nhieu.
        title = (self._text(soup, "h1")
                 or (soup.title.get_text(strip=True) if soup.title else "")
                 or self._meta(soup, "og:title") or "Truyen")
        title = re.sub(r"^\s*\[[^\]]{1,20}\]\s*", "", title)          # bo [Free], [Hot]...
        title = re.sub(r"\s*[-|–]\s*[^-|–]{0,40}$", "", title).strip() or "Truyen"

        cover = self._meta(soup, "og:image")
        cover = urljoin(url, cover) if cover else ""
        desc = self._meta(soup, "og:description") or self._meta(soup, "description")
        # og:description dung chung ca site thi bo di cho khoi hieu nham
        if desc and desc == self._meta(soup, "og:title"):
            desc = ""

        author = ""
        for pat in ("[itemprop='author']", "[class*='author']", "[rel='author']"):
            el = soup.select_one(pat)
            if el:
                author = el.get_text(" ", strip=True)[:120]
                break

        book = Book(title=title, url=url, source=self.id, author=author,
                    cover=cover, description=desc)
        book.chapters = self._chapters(url, soup, title)
        return book

    # ---------- danh sach chuong ----------
    def _chapters(self, url: str, soup, book_title: str = "") -> list[Chapter]:
        pages = [soup]
        tmpl, max_page = self._page_pattern(url, soup)

        if tmpl and max_page > 1:
            # Danh sach chuong duoc danh so trang -> doc thang tu trang 2 den trang cuoi.
            def grab(n: int):
                try:
                    return self.http.soup(tmpl.replace("\x00", str(n)), referer=url)
                except Exception:
                    return None

            with ThreadPoolExecutor(max_workers=min(8, max_page - 1)) as pool:
                pages += [s for s in pool.map(grab, range(2, max_page + 1)) if s is not None]
        else:
            # Khong doan duoc kieu danh so -> do lan theo tung link phan trang tim duoc.
            visited = {url.split("#")[0]}
            todo = [p for p in self._page_links(url, soup) if p not in visited]
            while todo and len(visited) < 300:
                p = todo.pop(0)
                if p in visited:
                    continue
                visited.add(p)
                try:
                    s = self.http.soup(p, referer=url)
                except Exception:
                    continue
                pages.append(s)
                todo += [q for q in self._page_links(url, s) if q not in visited]

        prefix = None
        if book_title:
            prefix = re.compile(r"^" + re.escape(book_title) + r"\s*[-–—:]\s*", re.I)

        seen: dict[str, str] = {}
        order: list[str] = []
        for s in pages:
            for href, name in self._links_of(url, s):
                if href not in seen:
                    if prefix:
                        name = prefix.sub("", name)
                    seen[href] = name
                    order.append(href)

        return [Chapter(index=i + 1, title=seen[h] or f"Chuong {i+1}", url=h)
                for i, h in enumerate(order)]

    def _page_pattern(self, base: str, soup) -> tuple[str, int]:
        """Doan mau URL phan trang. Tra ve (mau co \\x00 thay cho so trang, so trang lon nhat)."""
        best_tmpl, max_page = "", 1
        for link in self._page_links(base, soup):
            m = PAGE_HREF.search(link)
            if not m:
                continue
            digits = re.search(r"\d+", m.group(0))
            if not digits:
                continue
            n = int(digits.group(0))
            max_page = max(max_page, n)
            if not best_tmpl:
                seg = m.group(0).replace(digits.group(0), "\x00", 1)
                best_tmpl = link[:m.start()] + seg + link[m.end():]
        return best_tmpl, min(max_page, 400)

    def _links_of(self, base: str, soup) -> list[tuple[str, str]]:
        """Gom link chuong trong khoi 'sach' nhat trang.

        Khong the chi lay cum <a> dong nhat, vi nhieu web chia danh sach chuong
        thanh 2-3 cot <ul> canh nhau. Thay vao do cham diem tung khoi cha theo
        so link chuong va ty le link chuong tren tong so link cua khoi do:
        khoi danh sach chuong that co ca hai chi so deu cao, con <body> hay
        thanh ben ("chuong moi nhat") thi ty le rat thap.
        """
        host = urlparse(base).netloc
        found = []                       # [(the <a>, url day du, ten)]
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue
            full = urljoin(base, href)
            if urlparse(full).netloc != host:
                continue
            name = (a.get("title") or a.get_text(" ", strip=True)).strip()
            # Doi chieu tren URL da bo phan #... , neu khong link phan trang dang
            # ".../trang-2/#chapter-list" se bi tuong nham la link chuong.
            if CHAP_TEXT.match(name) or CHAP_HREF.search(full.split("#")[0]):
                found.append((a, full, name))
        if not found:
            return []

        count: dict[int, int] = {}
        node: dict[int, object] = {}
        for a, _, _ in found:
            el = a.parent
            for _ in range(6):           # chi soi len 6 tang, du cho moi bo cuc thuong gap
                if el is None or getattr(el, "name", None) in (None, "[document]"):
                    break
                count[id(el)] = count.get(id(el), 0) + 1
                node[id(el)] = el
                el = el.parent

        best, best_score = None, -1.0
        for key, n_chap in count.items():
            el = node[key]
            n_all = max(1, len(el.select("a[href]")))
            score = n_chap * n_chap / n_all
            if score > best_score:
                best, best_score = el, score

        out, seen = [], set()
        for a, full, name in found:
            if best is not None and best not in a.parents:
                continue
            if full not in seen:
                seen.add(full)
                out.append((full, name))
        return out

    def _page_links(self, base: str, soup) -> list[str]:
        host = urlparse(base).netloc
        out = []
        for a in soup.select("[class*='pag'] a[href], [id*='pag'] a[href]"):
            full = urljoin(base, a.get("href", ""))
            if urlparse(full).netloc == host and PAGE_HREF.search(full):
                out.append(full.split("#")[0])
        return list(dict.fromkeys(out))

    # ---------- noi dung chuong ----------
    def fetch_content(self, chapter: Chapter) -> str:
        soup = self.http.soup(chapter.url)
        for sel in DROP_IN_CONTENT:
            for el in soup.select(sel):
                el.decompose()

        # uu tien cac id/class quen thuoc
        for sel in ("#chapter-c", ".chapter-c", "#chapter-content", ".chapter-content",
                    "#content", ".content-chapter", "#chr-content", ".reading-content",
                    "article .entry-content", "[itemprop='articleBody']"):
            el = soup.select_one(sel)
            if el and len(el.get_text(strip=True)) > 200:
                return str(el)

        # khong co thi cham diem: nhieu chu, it link
        best, best_score = None, 0
        for el in soup.select("div, article, section, td"):
            text = el.get_text(" ", strip=True)
            n = len(text)
            if n < 300:
                continue
            link_len = sum(len(a.get_text(" ", strip=True)) for a in el.select("a"))
            breaks = len(el.find_all(["p", "br"]))
            score = n - 4 * link_len + 12 * breaks
            depth = len(list(el.parents))
            score += depth * 5          # uu tien khoi sau, sat noi dung
            if score > best_score:
                best, best_score = el, score
        if best is None:
            raise RuntimeError("Khong doan duoc khung noi dung o trang nay.")
        return str(best)

    # ---------- tien ich ----------
    @staticmethod
    def _meta(soup, prop: str) -> str:
        el = soup.select_one(f"meta[property='{prop}'], meta[name='{prop}']")
        return (el.get("content") or "").strip() if el else ""

    @staticmethod
    def _text(soup, sel: str) -> str:
        el = soup.select_one(sel)
        return el.get_text(" ", strip=True) if el else ""
