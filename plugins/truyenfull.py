"""Plugin nguon: he truyen chu dung layout TruyenFull (nhieu ten mien mirror)."""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus, urljoin, urlparse

from core.sources import Book, BookBrief, Chapter, Source


class TruyenFullSource(Source):
    id = "truyenfull"
    name = "TruyenFull (& mirror)"
    base_url = "https://truyenhoan.com"
    mirrors = [
        "https://truyenhoan.com",
        "https://truyenfull.vision",
        "https://truyenfull.vn",
        "https://truyenfull.tv",
        "https://truyenfull.com",
    ]
    domains = [
        "truyenhoan.com", "truyenfull.vision", "truyenfull.vn",
        "truyenfull.tv", "truyenfull.com", "truyenfull.io",
    ]
    priority = 10

    def __init__(self, http):
        super().__init__(http)
        self._live = None

    # ---------- chon ten mien con song ----------
    def live_base(self) -> str:
        if self._live:
            return self._live
        for m in self.mirrors:
            if self.http.alive(m + "/", timeout=8):
                self._live = m
                return m
        self._live = self.base_url
        return self._live

    def _host_ok(self, url: str) -> bool:
        return self.http.alive(f"{urlparse(url).scheme}://{urlparse(url).netloc}/", timeout=8)

    # ---------- tim kiem ----------
    def search(self, keyword: str, page: int = 1) -> list[BookBrief]:
        base = self.live_base()
        q = quote_plus(keyword.strip())
        url = f"{base}/tim-kiem/?tukhoa={q}" if page <= 1 else f"{base}/tim-kiem/trang-{page}/?tukhoa={q}"
        soup = self.http.soup(url)
        out: list[BookBrief] = []
        for row in soup.select(".list-truyen .row, .list .row"):
            a = row.select_one("h3.truyen-title a, .truyen-title a")
            if not a or not a.get("href"):
                continue
            img = row.select_one(".lazyimg")
            cover = ""
            if img:
                cover = img.get("data-desk-image") or img.get("data-image") or ""
            elif row.select_one("img"):
                cover = row.select_one("img").get("src", "")
            author = ""
            au = row.select_one(".author, [itemprop='author']")
            if au:
                author = au.get_text(" ", strip=True)
            latest = ""
            ch = row.select_one(".text-info a, .chapter-text")
            if ch:
                latest = ch.get_text(" ", strip=True)
            out.append(BookBrief(
                title=a.get_text(" ", strip=True), url=urljoin(base, a["href"]),
                source=self.id, author=author, cover=cover, latest=latest,
            ))
        return out

    # ---------- trang truyen ----------
    def fetch_book(self, url: str) -> Book:
        url = self._resolve(url)
        soup = self.http.soup(url)

        title_el = soup.select_one("h1.title, h3.title, .title[itemprop='name'], h1")
        title = title_el.get_text(" ", strip=True) if title_el else "Khong ro ten"

        cover = ""
        img = soup.select_one("div.book img, .books img, .book-img img, [itemprop='image']")
        if img:
            cover = img.get("src") or img.get("data-src") or img.get("content") or ""
            cover = urljoin(url, cover)

        info_text = ""
        info = soup.select_one(".info, .info-holder, #truyen .info")
        if info:
            info_text = info.get_text(" | ", strip=True)

        author = ""
        au = soup.select_one("[itemprop='author'], .info a[href*='tac-gia']")
        if au:
            author = au.get_text(" ", strip=True)
        elif info_text:
            m = re.search(r"T[aá]c gi[aả]\s*:?\s*\|?\s*([^|]+)", info_text, re.I)
            author = m.group(1).strip() if m else ""

        genres = []
        scope = info or soup.select_one("#truyen")
        if scope:
            for a in scope.select("a[href*='the-loai'], [itemprop='genre']"):
                g = a.get_text(" ", strip=True)
                if g and g not in genres:
                    genres.append(g)

        status = ""
        m = re.search(r"Tr[aạ]ng th[aá]i\s*:?\s*\|?\s*([^|]+)", info_text, re.I)
        if m:
            status = m.group(1).strip()

        desc_el = soup.select_one(".desc-text, [itemprop='description'], #desc, .desc")
        description = desc_el.get_text("\n", strip=True) if desc_el else ""

        book = Book(title=title, url=url, source=self.id, author=author, cover=cover,
                    description=description, status=status, genres=genres)
        book.chapters = self._chapters(url, soup, title)
        return book

    def _resolve(self, url: str) -> str:
        """Neu ten mien trong link bi chan thi tim lai truyen tren mirror con song."""
        if self._host_ok(url):
            return url
        slug = [p for p in urlparse(url).path.split("/") if p]
        if not slug:
            raise RuntimeError("Khong mo duoc link va khong doan duoc ten truyen.")
        keyword = re.sub(r"\.\d+$", "", slug[0]).replace("-", " ")
        hits = self.search(keyword)
        if not hits:
            raise RuntimeError(
                f"Ten mien {urlparse(url).netloc} khong truy cap duoc va khong tim thay "
                f"'{keyword}' tren mirror {self.live_base()}."
            )
        return hits[0].url

    def _chapters(self, url: str, soup, book_title: str = "") -> list[Chapter]:
        pages = [soup]
        tmpl = ""
        fmt = soup.select_one("input[name='format']")
        if fmt and fmt.get("value"):
            tmpl = fmt["value"]

        # Trang 1 da co san link toi trang cuoi -> tai song song cac trang con lai.
        # Bo gioi han toc do trong Http van giu nhip goi nen khong so bi web chan.
        max_page = min(self._max_page(soup), 400)

        def page_url(n: int) -> str:
            if tmpl and "%d" in tmpl:
                return tmpl.replace("%d", str(n))
            return url.rstrip("/") + f"/trang-{n}/#chapter-list"

        def grab(n: int):
            try:
                return self.http.soup(page_url(n), referer=url)
            except Exception:
                return None

        if max_page > 1:
            with ThreadPoolExecutor(max_workers=min(8, max_page - 1)) as pool:
                pages += [s for s in pool.map(grab, range(2, max_page + 1)) if s is not None]

        seen, chapters = set(), []
        prefix = re.compile(r"^" + re.escape(book_title) + r"\s*[-–—:]\s*", re.I) if book_title else None
        for s in pages:
            box = s.select_one("#list-chapter") or s.select_one(".list-chapter")
            if box is None:
                continue
            for junk in box.select(".pagination, [class*='pagination'], .select-page"):
                junk.decompose()
            links = box.select("ul.list-chapter li a") or box.select("a[href]")
            for a in links:
                href = (a.get("href") or "").strip()
                if not href or href.startswith(("#", "javascript:")):
                    continue
                full = urljoin(url, href)
                if full in seen:
                    continue
                seen.add(full)
                name = a.get("title") or a.get_text(" ", strip=True)
                if prefix:
                    name = prefix.sub("", name)
                name = re.sub(r"^(Ch[uư][oơ]ng)\s*(\d)", r"\1 \2", name).strip()
                chapters.append(Chapter(index=len(chapters) + 1, title=name, url=full))
        return chapters

    @staticmethod
    def _max_page(soup) -> int:
        best = 1
        for a in soup.select("ul.pagination a, .pagination a"):
            m = re.search(r"trang-(\d+)", a.get("href") or "")
            if m:
                best = max(best, int(m.group(1)))
        return best

    # ---------- noi dung chuong ----------
    def fetch_content(self, chapter: Chapter) -> str:
        soup = self.http.soup(chapter.url, referer=self.live_base())
        body = soup.select_one("#chapter-c, .chapter-c, #chapter-content, .chapter-content")
        if body is None:
            body = soup.select_one("#chapter-big-container")
        if body is None:
            raise RuntimeError("Khong tim thay khung noi dung chuong.")
        for el in body.select("div.ads, ins, script, style, .ads-holder, [class*='ads']"):
            el.decompose()
        return str(body)
