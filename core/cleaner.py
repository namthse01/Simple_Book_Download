"""Bien HTML chuong thanh cac dong van ban sach + bo loc rac do nguoi dung dat."""
from __future__ import annotations

import re
from bs4 import BeautifulSoup, NavigableString, Tag

# Cac the/khoi gan nhu chac chan la rac trong moi trang truyen
JUNK_SELECTORS = [
    "script", "style", "noscript", "iframe", "ins", "form", "button",
    "svg", "video", "audio", "nav", "header", "footer",
    ".ads", ".ad", ".ads-holder", ".adsbygoogle", ".quangcao", ".banner",
    "[id*='ads']", "[class*='ads-']", "[class*='advert']",
    ".share", ".social", ".comment", ".comments", "#comment",
    ".breadcrumb", ".pagination", ".control", ".chapter-nav",
]

# Dong chi gom ky tu trang tri thi bo
_DECOR_LINE = re.compile(r"^[\s\W_]{0,40}$", re.UNICODE)


def html_to_lines(html: str) -> list[str]:
    """HTML chuong -> danh sach doan van, da bo the rac."""
    soup = BeautifulSoup(html or "", "lxml")
    for sel in JUNK_SELECTORS:
        for el in soup.select(sel):
            el.decompose()
    for br in soup.find_all("br"):
        br.replace_with(NavigableString("\n"))
    for tag in soup.find_all(["p", "div", "h1", "h2", "h3", "h4", "li", "tr"]):
        tag.append(NavigableString("\n"))
    text = soup.get_text("")
    text = text.replace("\xa0", " ").replace("\u200b", "")
    lines = []
    for raw in text.split("\n"):
        s = re.sub(r"[ \t\r\f\v]+", " ", raw).strip()
        if s:
            lines.append(s)
    return lines


class Cleaner:
    """Ap dung bo quy tac loc do nguoi dung cau hinh.

    rules = {
      "remove":     ["chuoi bi xoa khoi dong", ...],
      "drop_line":  ["regex - dong khop se bi xoa han", ...],
      "regex":      [["pattern", "thay the"], ...],
      "names":      {"ten cu": "ten moi", ...}     # doi ten nhan vat
    }
    """

    def __init__(self, rules: dict | None = None):
        rules = rules or {}
        self.remove = [s for s in rules.get("remove", []) if s]
        self.names = {k: v for k, v in (rules.get("names") or {}).items() if k}
        self.regex = []
        for item in rules.get("regex", []):
            try:
                pat, rep = (item + ["", ""])[:2] if isinstance(item, list) else (item, "")
                self.regex.append((re.compile(pat, re.IGNORECASE | re.UNICODE), rep))
            except re.error:
                pass
        self.drop_line = []
        for pat in rules.get("drop_line", []):
            try:
                self.drop_line.append(re.compile(pat, re.IGNORECASE | re.UNICODE))
            except re.error:
                pass

    def clean(self, lines: list[str], extra_drop: set[str] | None = None) -> list[str]:
        extra_drop = extra_drop or set()
        out: list[str] = []
        for line in lines:
            for s in self.remove:
                line = line.replace(s, "")
            for pat, rep in self.regex:
                line = pat.sub(rep, line)
            for old, new in self.names.items():
                line = line.replace(old, new)
            line = re.sub(r"[ \t]+", " ", line).strip()
            if not line or _DECOR_LINE.match(line):
                continue
            if line in extra_drop:
                continue
            if any(p.search(line) for p in self.drop_line):
                continue
            if out and out[-1] == line:      # bo dong lap lien tiep
                continue
            out.append(line)
        return out


def detect_boilerplate(chapters_lines: list[list[str]], threshold=0.6, max_len=160) -> set[str]:
    """Tim dong rac lap lai o hau het cac chuong (chan trang, loi quang cao cua web).

    Chi xet dong ngan; dong xuat hien tu `threshold` ty le chuong tro len thi coi la rac.
    """
    if len(chapters_lines) < 4:
        return set()
    count: dict[str, int] = {}
    for lines in chapters_lines:
        for line in set(lines):
            if len(line) <= max_len:
                count[line] = count.get(line, 0) + 1
    need = max(3, int(len(chapters_lines) * threshold))
    return {line for line, c in count.items() if c >= need}
