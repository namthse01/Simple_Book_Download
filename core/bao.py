# -*- coding: utf-8 -*-
"""Doc bao: lay RSS tu cac nguon uy tin, chia theo the loai, luu kho bao theo ngay.

Chi luu TIEU DE + TOM TAT NGAN do chinh RSS cung cap, kem ten bao va link goc —
khong tai nguyen bai bao ve. Muon doc ca bai thi bam link sang trang goc.

Kho bao: <thu muc luu>/Bao/YYYY-MM-DD/
    bao.json          du lieu day du (de app doc lai, co ban dich neu da dich)
    <the-loai>.txt    ban chu de doc/chia se ngoai app
"""
from __future__ import annotations

import json
import re
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from . import store

ROOT = Path(__file__).resolve().parent.parent
FILE_NGUON = ROOT / "core" / "nguon_bao.json"
FILE_NGUON_RIENG = store.DATA / "nguon_bao_rieng.json"   # nguoi dung them/sua/tat

_lock = threading.Lock()


# ================================================================ danh sach nguon
def _goc() -> dict:
    try:
        return json.loads(FILE_NGUON.read_text(encoding="utf-8"))
    except Exception:
        return {"quoc_gia": [], "the_loai": [], "nguon": []}


def _rieng() -> dict:
    """{"them": [...], "sua": {ma: {...}}, "tat": [ma, ...]}"""
    try:
        d = json.loads(FILE_NGUON_RIENG.read_text(encoding="utf-8"))
    except Exception:
        d = {}
    d.setdefault("them", [])
    d.setdefault("sua", {})
    d.setdefault("tat", [])
    return d


def _ghi_rieng(d: dict) -> None:
    with _lock:
        FILE_NGUON_RIENG.write_text(json.dumps(d, ensure_ascii=False, indent=2),
                                    encoding="utf-8")


def danh_sach() -> dict:
    """Tra ve {quoc_gia, the_loai, nguon} da tron phan nguoi dung tu sua."""
    g = _goc()
    r = _rieng()
    nguon = []
    for n in g.get("nguon", []) + r["them"]:
        n = dict(n)
        n.update(r["sua"].get(n["ma"], {}))
        n["tat"] = n["ma"] in r["tat"]
        n["them_tay"] = any(x["ma"] == n["ma"] for x in r["them"])
        nguon.append(n)
    return {"quoc_gia": g.get("quoc_gia", []), "the_loai": g.get("the_loai", []),
            "nguon": nguon}


def sua_nguon(ma: str, thay_doi: dict) -> dict:
    r = _rieng()
    if "tat" in thay_doi:
        tat = set(r["tat"])
        tat.add(ma) if thay_doi.pop("tat") else tat.discard(ma)
        r["tat"] = sorted(tat)
    thay_doi = {k: v for k, v in thay_doi.items() if k in ("ten", "url", "muc", "quoc", "lang")}
    if thay_doi:
        r["sua"].setdefault(ma, {}).update(thay_doi)
    _ghi_rieng(r)
    return danh_sach()


def them_nguon(n: dict) -> dict:
    r = _rieng()
    ma = re.sub(r"[^a-z0-9]+", "-", (n.get("ten") or "nguon").lower()).strip("-") or "nguon"
    ds = {x["ma"] for x in danh_sach()["nguon"]}
    goc_ma, i = ma, 2
    while ma in ds:
        ma, i = f"{goc_ma}-{i}", i + 1
    r["them"].append({"ma": ma, "ten": n.get("ten") or ma, "quoc": n.get("quoc") or "khac",
                      "lang": n.get("lang") or "", "url": n.get("url") or "",
                      "muc": n.get("muc") or ""})
    _ghi_rieng(r)
    return danh_sach()


def xoa_nguon(ma: str) -> dict:
    r = _rieng()
    r["them"] = [x for x in r["them"] if x["ma"] != ma]
    r["sua"].pop(ma, None)
    if ma not in {x["ma"] for x in _goc().get("nguon", [])}:
        r["tat"] = [x for x in r["tat"] if x != ma]
    else:
        r["tat"] = sorted(set(r["tat"]) | {ma})     # nguon co san: xoa = tat han
    _ghi_rieng(r)
    return danh_sach()


# ================================================================ doan the loai
# Duong dan trong link la dau hieu chac chan nhat, roi den the <category> cua RSS,
# cuoi cung moi doan theo tu khoa trong tieu de.
_URL_MUC = [
    ("the-thao", r"/(the-thao|sport|sports|esporte|deporte|football|bong-da|soccer|"
                 r"cricket|rugby|tennis|olympic|спорт|スポーツ|体育|足球)"),
    ("quan-su", r"/(quan-su|military|defen[cs]e|defence|war|army|navy|air-force|weapon|"
                r"vu-khi|chien-su|armee|militaire|guerre|военн|армия|军事|国防|軍事)"),
    ("chinh-tri", r"/(chinh-tri|politic|politics|election|congress|parliament|senate|"
                  r"politique|politica|política|политик|выборы|政治|选举|政局)"),
    ("y-te", r"/(y-te|suc-khoe|health|medical|medicine|disease|covid|sante|santé|saude|saúde|"
             r"здоров|медицин|医療|健康|医学|健康)"),
    ("khoa-hoc", r"/(khoa-hoc|cong-nghe|science|sciences|tech|technology|space|ai-|research|"
                 r"ciencia|ciência|tecnologia|наука|технолог|космос|科学|技術|科技|테크)"),
    ("kinh-te", r"/(kinh-te|kinh-doanh|business|economy|economics|market|finance|money|"
                r"economie|économie|economia|negocios|эконом|бизнес|финанс|经济|财经|"
                r"商业|経済|ビジネス)"),
    ("moi-truong", r"/(moi-truong|environment|climate|weather|nature|энерг|климат|"
                   r"environnement|clima|ambiente|環境|气候|环境)"),
    ("van-hoa", r"/(van-hoa|giai-tri|culture|entertainment|arts|music|film|movie|celebrit|"
                r"lifestyle|travel|du-lich|cultura|культур|文化|娱乐|芸能|エンタメ)"),
    ("thoi-su", r"/(the-gioi|thoi-su|world|international|global|monde|mundo|мир|"
                r"国際|世界|时事)"),
]
_URL_MUC = [(m, re.compile(p, re.I)) for m, p in _URL_MUC]

# Tu khoa trong tieu de/tom tat — phai khop CA CUM, khong tach le tung am tiet
# (tach le thi "quan doi" thanh "doi", tin mua sam cung bi xep vao quan su).
# Tieng Viet viet khong dau de khop ca hai kieu go.
_TU_KHOA = {
    "the-thao": """the thao|bong da|cau thu|vo dich|giai dau|world cup|sea games|olympic|
        hlv|tran dau|ghi ban|v-league|ngoai hang anh|tuyen thu|dt viet nam|chung ket|
        sport|sports|football|soccer|match|goal|league|coach|striker|tournament|
        nba|nfl|mlb|tennis|golf|olympics|championship|athlete|fifa|premier league|
        futebol|jogador|campeonato|esporte|gol|
        спорт|футбол|матч|чемпионат|игрок|
        サッカー|野球|選手|試合|優勝|五輪|体育|足球|比赛|冠军""",
    "quan-su": """quan su|quan doi|vu khi|ten lua|chien tranh|xung dot|khong kich|
        binh si|tau chien|may bay chien dau|phong khong|hat nhan|dan phao|quan nhan|
        bo quoc phong|tap tran|
        military|army|troops|missile|warfare|airstrike|weapon|drone strike|warship|nato|
        ceasefire|offensive|artillery|nuclear weapon|soldier|pentagon|defense ministry|
        guerre|militaire|armee|
        военн|армия|ракет|войск|оруж|
        軍事|自衛隊|ミサイル|导弹|军队|国防""",
    "chinh-tri": """chinh tri|quoc hoi|thu tuong|chu tich nuoc|tong thong|bo truong|bau cu|
        nghi quyet|chinh phu|ngoai giao|nghi si|dai bieu|tong bi thu|
        president|parliament|congress|senate|election|minister|government|
        policy|diplomat|vote|campaign|white house|prime minister|lawmaker|
        ministre|elections|gouvernement|
        президент|парламент|выбор|министр|правительств|
        首相|国会|選挙|政府|总统|议会|选举""",
    "kinh-te": """kinh te|kinh doanh|chung khoan|lam phat|gia vang|ty gia|doanh nghiep|
        xuat khau|nhap khau|ngan hang|thi truong|co phieu|bat dong san|mua sam|
        tieu dung|tieu thuong|suc mua|dau tu|thue quan|gia xang|
        economy|business|market|stocks|inflation|trade|tariff|bank|gdp|
        revenue|profit|investor|shares|startup|ipo|earnings|
        economie|marche|bourse|entreprise|economia|
        эконом|рынок|банк|акци|инфляц|бизнес|
        経済|市場|企業|经济|市场|股市|企业""",
    "khoa-hoc": """khoa hoc|cong nghe|nghien cuu|vu tru|ve tinh|tri tue nhan tao|
        ban dan|may tinh|dien thoai|phan mem|nha khoa hoc|chip|robot|
        science|research|space|satellite|nasa|scientists|technology|
        semiconductor|software|quantum|rocket|telescope|artificial intelligence|
        recherche|espace|technologie|ciencia|tecnologia|
        наука|исследован|космос|спутник|технолог|
        科学|研究|宇宙|技術|科技|航天""",
    "y-te": """y te|suc khoe|benh vien|benh nhan|dich benh|vaccine|bac si|ung thu|
        virus|sot xuat huyet|dinh duong|phau thuat|bo y te|thuoc|cum a|
        health|hospital|patient|disease|vaccine|doctor|cancer|flu|
        outbreak|medicine|clinical|covid|mental health|surgery|
        sante|hopital|maladie|vaccin|medecin|saude|
        здоров|больниц|врач|вакцин|лечен|
        医療|病院|患者|ワクチン|医疗|医院|疫苗""",
    "moi-truong": """moi truong|khi hau|bao lu|lu lut|han han|dong dat|song than|
        o nhiem|rac thai|nang luong tai tao|thien tai|sat lo|
        climate|environment|flood|drought|earthquake|typhoon|hurricane|
        wildfire|pollution|emissions|renewable|heatwave|
        climat|environnement|inondation|seisme|
        климат|наводнен|землетрясен|эколог|
        気候|地震|台風|环境|气候""",
    "van-hoa": """van hoa|giai tri|am nhac|dien anh|ca si|dien vien|le hoi|du lich|
        nghe thuat|trien lam|thoi trang|phim|hoa hau|sach|
        culture|entertainment|music|film|movie|actor|singer|festival|travel|
        art|fashion|celebrity|album|concert|box office|museum|
        cinema|musique|cultura|
        культур|кино|музык|фестивал|
        映画|音楽|文化|芸能|电影|音乐|娱乐""",
}


def _bo_dau(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn").lower()


def _lam_bang(chuoi: str):
    """Tach bang tu khoa thanh (regex cho chu latin, list cum chu tuong hinh)."""
    cum = [c.strip() for c in chuoi.replace("\n", "").split("|")]
    cum = [c for c in cum if c]
    latin = [re.escape(c) for c in cum if c.isascii()]
    khac = [c for c in cum if not c.isascii()]
    re_latin = re.compile(r"(?<![a-z0-9])(?:" + "|".join(latin) + r")(?![a-z0-9])") \
        if latin else None
    return re_latin, khac


_BANG = {muc: _lam_bang(chuoi) for muc, chuoi in _TU_KHOA.items()}


def doan_muc(tieu_de: str, tom_tat: str, link: str, the_rss: list, goi_y: str) -> str:
    """Xep bai vao the loai. goi_y = the loai mac dinh cua feed (manh nhat)."""
    if goi_y:
        return goi_y
    duong = (link or "").lower()
    for muc, pat in _URL_MUC:
        if pat.search(duong):
            return muc
    tags = " ".join(the_rss or "").lower()
    for muc, pat in _URL_MUC:
        if pat.search("/" + tags.replace(" ", "-")):
            return muc

    # Tieu de nang ky hon han tom tat: tom tat hay nhac ten rieng lac de
    # ("Dai hoc Kinh te", "mot bac si...") — mot tu lac trong tom tat khong du
    # de doi the loai, phai co dau hieu ngay o tieu de hoac nhac lai nhieu lan.
    def cham(chu: str) -> dict[str, int]:
        ra = {}
        for muc, (re_latin, khac) in _BANG.items():
            n = len(set(re_latin.findall(chu))) if re_latin else 0
            n += sum(1 for c in khac if c in chu)
            if n:
                ra[muc] = n
        return ra

    d_td = cham(_bo_dau(tieu_de))
    d_tt = cham(_bo_dau((tom_tat or "")[:220]))
    diem = {m: 3 * d_td.get(m, 0) + d_tt.get(m, 0) for m in set(d_td) | set(d_tt)}
    if diem:
        muc, top = max(diem.items(), key=lambda kv: (kv[1], kv[0] != "thoi-su"))
        if top >= 2:
            return muc
    return "thoi-su"


# ================================================================ doc RSS
_HTML = re.compile(r"<[^>]+>")
DAI_TOM_TAT = 400          # chi giu tom tat ngan do chinh RSS cung cap


# Vai feed nhet cau moi doc vao tom tat ("Read more", "記事を読む"...) — bo di,
# ke ca khi no bam o cuoi doan chu khong dung mot minh.
_RAC = (r"read (the )?(full )?(article|more|story)|continue reading|記事を読む|"
        r"続きを読む|xem chi tiet|xem them|详情|閱讀全文|the post .{0,80} appeared first on .{0,60}")
_TOM_TAT_RAC = re.compile(r"^(?:" + _RAC + r"|\[…\]|\.\.\.)$", re.I)
_DUOI_RAC = re.compile(r"[\s　…\.\-–—|]*(?:" + _RAC + r")[\s…\.]*$", re.I)


def _sach(s: str, dai=0) -> str:
    s = _HTML.sub(" ", s or "")
    s = BeautifulSoup(s, "html.parser").get_text(" ")
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"\s+", " ", s).strip()
    if dai and len(s) > dai:
        s = s[:dai].rsplit(" ", 1)[0] + "…"
    return s


# The duoc phep giu lai khi hien bai trong app: du de doc + xem anh/video,
# khong co script hay bieu mau.
_THE_OK = {"p", "br", "b", "strong", "i", "em", "u", "h2", "h3", "h4", "blockquote",
           "ul", "ol", "li", "figure", "figcaption", "img", "a", "iframe", "video",
           "source", "table", "thead", "tbody", "tr", "td", "th", "hr", "span", "div"}
_THUOC_TINH_OK = {"src", "href", "alt", "title", "srcset", "width", "height",
                  "controls", "poster", "allowfullscreen", "frameborder"}
DAI_NOI_DUNG = 60000        # chan bai qua dai cho kho bao khoi phinh


def lam_sach_html(html: str, goc: str = "") -> str:
    """Giu lai phan doc duoc (chu, anh, video nhung) va bo het thu nguy hiem/rac."""
    soup = BeautifulSoup(html or "", "html.parser")
    for el in soup.find_all(["script", "style", "noscript", "form", "button", "input"]):
        el.decompose()
    for el in soup.find_all(True):
        if el.name not in _THE_OK:
            el.unwrap()
            continue
        for ten in list(el.attrs):
            if ten not in _THUOC_TINH_OK:
                del el.attrs[ten]
        for ten in ("src", "href", "poster"):
            v = el.attrs.get(ten)
            if v and goc and not str(v).startswith(("http", "data:", "//")):
                el.attrs[ten] = urljoin(goc, str(v))
        if el.name == "a":
            el.attrs["target"] = "_blank"
            el.attrs["rel"] = "noopener noreferrer"
        if el.name == "img":
            el.attrs["loading"] = "lazy"
    ra = str(soup).strip()
    return ra[:DAI_NOI_DUNG]


def _giong(a: str, b: str) -> bool:
    """Tom tat trung lap tieu de thi bo di cho do rac."""
    rut = lambda s: re.sub(r"\W+", "", _bo_dau(s))[:60]   # noqa: E731
    return bool(rut(a)) and rut(a) == rut(b)


def _ngay(s: str):
    s = (s or "").strip()
    if not s:
        return None
    for f in (parsedate_to_datetime,
              lambda x: datetime.fromisoformat(x.replace("Z", "+00:00")),
              lambda x: datetime.strptime(x[:19], "%Y-%m-%d %H:%M:%S"),
              lambda x: datetime.strptime(x[:19], "%d/%m/%Y %H:%M:%S"),
              lambda x: datetime.strptime(x[:16], "%d/%m/%Y %H:%M"),
              lambda x: datetime.strptime(x.strip(), "%m/%d/%Y %I:%M:%S %p"),
              lambda x: datetime.strptime(x[:10], "%Y-%m-%d")):
        try:
            d = f(s)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


def doc_feed(http, nguon: dict, gioi_han=30) -> list[dict]:
    """Lay bai tu 1 feed. Tra ve list bai da lam sach (chua phan muc)."""
    xml = http.text(nguon["url"], timeout=20)
    soup = BeautifulSoup(xml, "xml")
    muc_xml = soup.find_all(["item", "entry"])[:gioi_han]
    ra = []
    for it in muc_xml:
        tieu_de = _sach(it.title.get_text() if it.title else "")
        if not tieu_de:
            continue
        link = ""
        if it.link:
            link = (it.link.get("href") or it.link.get_text() or "").strip()
        if not link and it.find("guid"):
            g = it.find("guid").get_text().strip()
            link = g if g.startswith("http") else ""
        mo_ta = ""
        for the in ("description", "summary", "content", "content:encoded"):
            el = it.find(the)
            if el and el.get_text(strip=True):
                mo_ta = el.get_text()
                break
        # Toa soan nao tu phat CA BAI trong feed (content:encoded) thi doc luon
        # trong app — do la muc dich cua o do. Con lai chi giu tom tat.
        noi_dung = ""
        for the in ("content:encoded", "content"):
            el = it.find(the)
            if el:
                thu = el.get_text()
                if len(_HTML.sub("", thu)) > max(400, len(_HTML.sub("", mo_ta)) + 200):
                    noi_dung = lam_sach_html(thu, link)
                    break
        ngay = None
        for the in ("pubDate", "published", "updated", "dc:date", "date"):
            el = it.find(the)
            if el:
                ngay = _ngay(el.get_text())
                if ngay:
                    break
        anh = ""
        for el in it.find_all(["enclosure", "media:content", "media:thumbnail"]):
            u = el.get("url") or ""
            if re.search(r"\.(jpe?g|png|webp)", u, re.I) or "image" in (el.get("type") or ""):
                anh = u
                break
        tags = [c.get_text(strip=True) for c in it.find_all("category")][:6]
        tom_tat = _DUOI_RAC.sub("", _sach(mo_ta, DAI_TOM_TAT)).strip()
        if len(tom_tat) < 15 or _TOM_TAT_RAC.match(tom_tat.strip(" .…")) \
                or _giong(tom_tat, tieu_de):
            tom_tat = ""
        ra.append({
            "tieu_de": tieu_de,
            "noi_dung": noi_dung,
            "tom_tat": tom_tat,
            "link": link,
            "anh": anh,
            "luc": ngay.isoformat() if ngay else "",
            "nguon": nguon["ten"],
            "nguon_ma": nguon["ma"],
            "quoc": nguon.get("quoc", ""),
            "lang": nguon.get("lang", ""),
            "muc": doan_muc(tieu_de, mo_ta, link, tags, nguon.get("muc", "")),
        })
    return ra


# ================================================================ kho bao
# ================================================================ bóc bài để đọc trong app
# Kieu "che do doc" (reader mode): mo bai nao thi lay bai do ve, bo menu/quang
# cao, giu lai chu + anh + video de doc va DICH ngay trong app. Chi lam khi
# nguoi dung bam vao bai, khong quet hang loat.
_KHUNG_BAI = (
    "article .article-body", "div.article-body", "div.entry-content", "div.post-content",
    "div.article__content", "div.article-content", "div.content-detail", "div.detail-content",
    "[itemprop='articleBody']", "div.fck_detail", "div#maincontent", "div.singular-content",
    "div.__MASTERCMS_CONTENT", "div.article-detail", "div.detail__content", "article",
)
_RAC_TRONG_BAI = (
    "script", "style", "noscript", "form", "button", "nav", "header", "footer", "aside",
    "figure.video-js", ".ads", "[class*='ads']", "[id*='ads']", ".quangcao", ".banner",
    ".share", ".social", ".comment", ".comments", ".related", ".tin-lien-quan",
    ".newsletter", ".subscribe", ".paywall", ".breadcrumb", ".tags", ".author-box",
    "[class*='recommend']", "[class*='promo']", "[class*='popup']",
)


def _diem_khoi(el) -> float:
    chu = len(el.get_text(" ", strip=True))
    if chu < 250:
        return 0.0
    link = sum(len(a.get_text(" ", strip=True)) for a in el.find_all("a"))
    doan = len(el.find_all(["p", "br"]))
    return chu - 4 * link + 14 * doan


def boc_bai(http, url: str) -> dict:
    """Tai trang bao va boc lay phan noi dung chinh (chu + anh + video nhung).

    Tra ve {"html": ..., "doan": [chuoi...]} — `doan` la cac doan van tho de
    dua cho bo dich, `html` de hien trong app.
    """
    soup = http.soup(url, timeout=25)
    for sel in _RAC_TRONG_BAI:
        for el in soup.select(sel):
            el.decompose()

    khung = None
    for sel in _KHUNG_BAI:
        el = soup.select_one(sel)
        if el and len(el.get_text(" ", strip=True)) > 400:
            khung = el
            break
    if khung is None:                       # khong nhan ra khung -> cham diem
        tot, diem_tot = None, 0.0
        for el in soup.select("div, section, main, article, td"):
            d = _diem_khoi(el)
            if d > diem_tot:
                tot, diem_tot = el, d
        khung = tot
    if khung is None:
        raise RuntimeError("không tìm thấy phần nội dung trên trang này")

    soup2 = BeautifulSoup(lam_sach_html(str(khung), url), "html.parser")
    # Danh so tung doan (data-d) de ban dich thay dung cho, anh/video giu nguyen vi tri
    doan = []
    for p in soup2.find_all(["p", "h2", "h3", "h4", "li", "blockquote"]):
        if p.find(["p", "li"]):                 # khoi bao ngoai, de con no dich
            continue
        t = _sach(p.get_text(" "))
        if len(t) >= 25 and (not doan or doan[-1] != t):
            p.attrs["data-d"] = str(len(doan))
            doan.append(t)
    if not doan:
        raise RuntimeError("trang này không có đoạn chữ nào đọc được")
    return {"html": str(soup2).strip()[:DAI_NOI_DUNG], "doan": doan}


def luu_bai_day_du(ngay: str, link: str, html: str, doan: list) -> None:
    """Cat ban da boc vao kho cua ngay do — lan sau mo lai la co ngay."""
    js = _doc_ngay_raw(ngay)
    for b in js.get("bai", []):
        if b.get("link") == link:
            b["noi_dung"] = html
            b["doan"] = doan
            _ghi_ngay(ngay, js, danh_sach()["the_loai"])
            return


def luu_dich_bai(ngay: str, link: str, sang: str, doan: list) -> None:
    js = _doc_ngay_raw(ngay)
    for b in js.get("bai", []):
        if b.get("link") == link:
            b["dich_bai"] = {"lang": sang, "doan": doan}
            _ghi_ngay(ngay, js, danh_sach()["the_loai"])
            return


def co_cho_nhung(http, url: str) -> dict:
    """Trang bao nay co cho hien trong khung nhung cua app khong?

    Nhieu toa soan dat X-Frame-Options / CSP frame-ancestors de chan nhung.
    Hoi truoc de con bao nguoi doc mo ra trinh duyet, thay vi de ho nhin
    mot khung trang tron."""
    try:
        r = http.get(url, timeout=12, stream=True)
        h = {k.lower(): v for k, v in r.headers.items()}
        r.close()
    except Exception as exc:
        return {"cho_nhung": False, "ly_do": f"không mở được trang ({type(exc).__name__})"}
    xfo = (h.get("x-frame-options") or "").lower()
    if "deny" in xfo or "sameorigin" in xfo:
        return {"cho_nhung": False, "ly_do": "trang báo không cho hiển thị trong khung"}
    csp = (h.get("content-security-policy") or "").lower()
    m = re.search(r"frame-ancestors([^;]*)", csp)
    if m and "*" not in m.group(1):
        return {"cho_nhung": False, "ly_do": "trang báo không cho hiển thị trong khung"}
    return {"cho_nhung": True, "ly_do": ""}


def thu_muc_kho() -> Path:
    p = Path(store.load_settings()["output_dir"]) / "Bao"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _khoa(b: dict) -> str:
    """Khoa chong trung: uu tien link, khong co thi dung tieu de rut gon."""
    if b.get("link"):
        return re.sub(r"[?#].*$", "", b["link"]).rstrip("/").lower()
    return _bo_dau(b["tieu_de"])[:80]


def cap_nhat(bao_tien_do=None, ngay: str = "", so_luong_feed=8) -> dict:
    """Lay tin moi tu moi nguon dang bat, gop lai, luu vao kho bao cua ngay hom nay."""
    ds = danh_sach()
    nguon = [n for n in ds["nguon"] if not n["tat"] and n.get("url")]
    cfg = store.load_settings()
    from .net import Http
    http = Http(delay=0, retries=1, timeout=20, proxy=cfg.get("proxy", ""))

    ngay = ngay or datetime.now().strftime("%Y-%m-%d")
    tat_ca: list[dict] = []
    loi: list[str] = []
    xong = [0]

    def mot(n):
        try:
            bai = doc_feed(http, n)
            with _lock:
                tat_ca.extend(bai)
        except Exception as exc:
            with _lock:
                loi.append(f"{n['ten']}: {type(exc).__name__}")
        finally:
            with _lock:
                xong[0] += 1
                if bao_tien_do:
                    bao_tien_do(xong[0], len(nguon), n["ten"])

    with ThreadPoolExecutor(max_workers=so_luong_feed) as pool:
        list(pool.map(mot, nguon))

    # bo trung, uu tien bai co tom tat dai hon
    gop: dict[str, dict] = {}
    for b in tat_ca:
        k = _khoa(b)
        cu = gop.get(k)
        if cu is None or len(b["tom_tat"]) > len(cu["tom_tat"]):
            if cu is not None:
                b["cung_dua"] = sorted(set(cu.get("cung_dua", []) + [cu["nguon"]]))
            gop[k] = b
    bai = sorted(gop.values(), key=lambda x: x["luc"], reverse=True)

    # chi giu tin trong 48h (bai cu hon thuong la bai lap cua feed)
    han = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    bai = [b for b in bai if not b["luc"] or b["luc"] >= han]

    kho = _doc_ngay_raw(ngay)
    cu = {_khoa(b): b for b in kho.get("bai", [])}
    for b in bai:                                  # giu lai ban dich da co cua bai cu
        k = _khoa(b)
        if k in cu and cu[k].get("dich"):
            b["dich"] = cu[k]["dich"]
    for k, b in cu.items():                        # giu bai cu trong ngay, khong xoa
        if k not in gop:
            bai.append(b)
    bai.sort(key=lambda x: x.get("luc", ""), reverse=True)

    du_lieu = {"ngay": ngay, "cap_nhat_luc": datetime.now().isoformat(timespec="seconds"),
               "so_nguon": len(nguon), "loi": loi, "bai": bai}
    _ghi_ngay(ngay, du_lieu, ds["the_loai"])
    return {"ngay": ngay, "so_bai": len(bai), "so_nguon": len(nguon), "loi": loi,
            "thong_ke": thong_ke(bai)}


def thong_ke(bai: list[dict]) -> dict:
    d: dict[str, int] = {}
    for b in bai:
        d[b["muc"]] = d.get(b["muc"], 0) + 1
    return d


def _doc_ngay_raw(ngay: str) -> dict:
    p = thu_muc_kho() / ngay / "bao.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _ghi_ngay(ngay: str, du_lieu: dict, the_loai: list[dict]) -> None:
    thu_muc = thu_muc_kho() / ngay
    thu_muc.mkdir(parents=True, exist_ok=True)
    with _lock:
        (thu_muc / "bao.json").write_text(
            json.dumps(du_lieu, ensure_ascii=False, indent=1), encoding="utf-8")
    ten_muc = {m["ma"]: m["ten"] for m in the_loai}
    for ma, ten in ten_muc.items():
        ds = [b for b in du_lieu["bai"] if b["muc"] == ma]
        f = thu_muc / f"{ma}.txt"
        if not ds:
            f.unlink(missing_ok=True)
            continue
        dong = [f"{ten.upper()} — {ngay}", "=" * 60, ""]
        for b in ds:
            gio = (b["luc"][11:16] + "  ") if len(b["luc"]) >= 16 else ""
            dong.append(f"{gio}[{b['nguon']}] {b.get('dich', {}).get('tieu_de') or b['tieu_de']}")
            tt = b.get("dich", {}).get("tom_tat") or b["tom_tat"]
            if tt:
                dong.append("    " + tt)
            if b["link"]:
                dong.append("    " + b["link"])
            dong.append("")
        f.write_text("\n".join(dong), encoding="utf-8")


def ds_ngay() -> list[dict]:
    """Danh sach cac ngay da co trong kho bao, moi nhat truoc."""
    ra = []
    for d in sorted(thu_muc_kho().glob("20*-*-*"), reverse=True):
        if not d.is_dir():
            continue
        try:
            js = json.loads((d / "bao.json").read_text(encoding="utf-8"))
        except Exception:
            continue
        ra.append({"ngay": js.get("ngay", d.name), "so_bai": len(js.get("bai", [])),
                   "cap_nhat_luc": js.get("cap_nhat_luc", ""),
                   "thong_ke": thong_ke(js.get("bai", []))})
    return ra


def doc_ngay(ngay: str, muc: str = "", quoc: str = "", tim: str = "",
             tu: int = 0, so: int = 60) -> dict:
    js = _doc_ngay_raw(ngay)
    bai = js.get("bai", [])
    if muc:
        bai = [b for b in bai if b["muc"] == muc]
    if quoc:
        bai = [b for b in bai if b.get("quoc") == quoc]
    if tim:
        q = _bo_dau(tim)
        bai = [b for b in bai if q in _bo_dau(
            b["tieu_de"] + " " + b["tom_tat"] + " " +
            (b.get("dich", {}).get("tieu_de", "") if b.get("dich") else ""))]
    # Khong gui kem ca noi dung bai trong danh sach (nang vai MB moi lan lat
    # trang) — chi danh dau bai nao doc tron duoc, mo bai moi lay noi dung.
    nhe = []
    for b in bai[tu:tu + so]:
        x = {k: v for k, v in b.items() if k != "noi_dung"}
        x["co_bai"] = bool(b.get("noi_dung"))
        nhe.append(x)
    return {"ngay": js.get("ngay", ngay), "cap_nhat_luc": js.get("cap_nhat_luc", ""),
            "tong": len(bai), "bai": nhe,
            "thong_ke": thong_ke(js.get("bai", []))}


def doc_bai(ngay: str, link: str) -> dict | None:
    """Lay tron mot bai da luu (co noi_dung) de hien trong app."""
    for b in _doc_ngay_raw(ngay).get("bai", []):
        if b.get("link") == link or _khoa(b) == link:
            return b
    return None


def xoa_ngay(ngay: str) -> bool:
    import shutil
    d = thu_muc_kho() / ngay
    if d.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", ngay):
        shutil.rmtree(d)
        return True
    return False


def luu_dich(ngay: str, ban_dich: dict) -> int:
    """ban_dich = {khoa_bai: {tieu_de, tom_tat, lang}} -> ghi vao kho."""
    js = _doc_ngay_raw(ngay)
    if not js:
        return 0
    n = 0
    for b in js.get("bai", []):
        d = ban_dich.get(_khoa(b))
        if d:
            b["dich"] = d
            n += 1
    if n:
        _ghi_ngay(ngay, js, danh_sach()["the_loai"])
    return n
