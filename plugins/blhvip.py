"""Plugin nguon: blhvip.vn.

Trang nay dung Laravel + JavaScript: danh sach chuong, tac gia va mo ta deu
KHONG nam trong HTML ban dau ma duoc nap sau bang API rieng, nen bo do tu dong
chi thay dung 1 link chuong. Plugin goi thang API cua trang.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus, urlparse

from core.sources import Book, BookBrief, Chapter, Source

API = "https://api.blhvip.vn"
SITE = "https://blhvip.vn"


class BlhVipSource(Source):
    id = "blhvip"
    name = "BLHVIP"
    domains = ["blhvip.vn"]
    base_url = SITE
    priority = 20

    # ---------- tim kiem ----------
    def search(self, keyword: str, page: int = 1) -> list[BookBrief]:
        url = f"{API}/v1/search?keyword={quote_plus(keyword.strip())}&page={max(1, page)}"
        data = self._json(url).get("data") or []
        out = []
        for it in data:
            slug = it.get("slug")
            if not slug:
                continue
            n = it.get("chapter_count")
            out.append(BookBrief(
                title=it.get("name") or slug,
                url=f"{SITE}/truyen/{slug}",
                source=self.id,
                author=it.get("author_name") or "",
                cover=it.get("img_url") or "",
                latest=f"{n} chương" if n else (it.get("status") or ""),
            ))
        return out

    # ---------- trang truyen ----------
    def fetch_book(self, url: str) -> Book:
        slug = self._slug(url)
        url = f"{SITE}/truyen/{slug}"
        soup = self.http.soup(url)

        # og:title cua trang nay la cau quang cao dung chung cho moi trang,
        # nen chi tin the <title> va <h1>.
        title = soup.title.get_text(strip=True) if soup.title else ""
        if not title:
            h1 = soup.select_one("h1")
            title = h1.get_text(" ", strip=True) if h1 else slug.replace("-", " ")
        title = re.sub(r"^\s*\[[^\]]{1,20}\]\s*", "", title).strip()

        cover = ""
        og = soup.select_one("meta[property='og:image']")
        if og and og.get("content"):
            cover = og["content"].strip()

        book = Book(title=title, url=url, source=self.id, cover=cover)
        self._fill_meta(book, soup)
        book.chapters = self._chapters(slug)
        return book

    @staticmethod
    def _fill_meta(book: Book, soup) -> None:
        """Tac gia / trang thai / mo ta deu nam trong HTML.

        Luu y link tac gia la duong dan tuong doi ("tac-gia/..."), khong co dau
        gach cheo dau, nen phai tim theo chuoi con chu khong theo "/tac-gia/".
        Khong lay the loai: cac link "the-loai" tren trang nay la menu chung
        cua ca website chu khong phai the loai cua rieng truyen.
        """
        au = soup.select_one("a[href*='tac-gia']")
        if au:
            book.author = au.get_text(" ", strip=True)

        for p in soup.select("p.text-info, .text-info"):
            t = p.get_text(" ", strip=True)
            if re.match(r"^\s*(T[iì]nh tr[aạ]ng|Tr[aạ]ng th[aá]i)\s*:", t, re.I):
                book.status = t.split(":", 1)[1].strip()
                break

        desc = soup.select_one(".s-content, .tabcontent.active")
        if desc:
            book.description = desc.get_text("\n", strip=True)

    # ---------- danh sach chuong ----------
    def _chapters(self, slug: str) -> list[Chapter]:
        def page(n: int) -> list:
            u = f"{API}/v1/story/{slug}/chapter_list?page={n}&new=0"
            try:
                return self._json(u).get("data") or []
            except Exception:
                return []

        first = self._json(f"{API}/v1/story/{slug}/chapter_list?page=1&new=0")
        rows = list(first.get("data") or [])
        total = int(first.get("total_page") or 1)

        if total > 1:
            with ThreadPoolExecutor(max_workers=min(8, total - 1)) as pool:
                for part in pool.map(page, range(2, min(total, 400) + 1)):
                    rows += part

        chapters, seen = [], set()
        for it in rows:
            href = it.get("url") or ""
            if not href:
                continue
            full = href if href.startswith("http") else SITE + href
            if full in seen:
                continue
            seen.add(full)
            chapters.append(Chapter(
                index=len(chapters) + 1,
                title=(it.get("name") or f"Chương {len(chapters)+1}").strip(),
                url=full,
                volume="VIP" if it.get("is_vip") else "",
            ))
        return chapters

    # ---------- noi dung chuong ----------
    def fetch_content(self, chapter: Chapter) -> str:
        soup = self.http.soup(chapter.url, referer=SITE)
        # Phai lay dung .s-content. Khong dung selector rong kieu [class*='chapter-c']:
        # no khop ca khoi bao ngoai, keo theo link "Chuong truoc / Chuong tiep" va
        # dong "tac gia - so chu - ngay dang" vao dau moi chuong.
        body = (soup.select_one("#chapter-content .s-content")
                or soup.select_one(".s-content")
                or soup.select_one("#chapter-content")
                or soup.select_one(".chapter-content"))
        if body is None:
            raise RuntimeError("Khong tim thay khung noi dung chuong.")
        for el in body.select("script, style, ins, iframe, [class*='ads'], .ads,"
                              " h1.chapter-title, p.info-detail, .chapter-nav"):
            el.decompose()
        # Chuong khoa se tra ve trang moi dang nhap/mua chuong: bao loi han thay vi
        # ghi mot chuong rong vao file ebook.
        if len(body.get_text(" ", strip=True)) < 200:
            raise RuntimeError("Chương bị khoá hoặc rỗng (có thể cần đăng nhập/mở khoá).")
        return str(body)

    # ---------- tien ich ----------
    def _json(self, url: str) -> dict:
        r = self.http.get(url, referer=SITE)
        return r.json()

    @staticmethod
    def _slug(url: str) -> str:
        parts = [p for p in urlparse(url).path.split("/") if p]
        if "truyen" in parts:
            i = parts.index("truyen")
            if i + 1 < len(parts):
                return parts[i + 1]
        return parts[-1] if parts else ""
