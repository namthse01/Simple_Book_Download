# -*- coding: utf-8 -*-
"""Cao tai lieu tu web: dua mot (hay nhieu) dia chi trang, app do ra cac file
tai lieu trong do (PDF/DOCX/EPUB/TXT/MD/HTML), tai ve roi nhap thang vao thu vien.

Cach cu xu voi may chu nguoi ta (de khoi bi chan, va cung la phep lich su):
  - doc robots.txt truoc, duong nao bi cam thi khong do
  - nghi giua cac lan goi theo cai dat "delay" cua app (Http lo san)
  - chan so trang do va so file moi lan, khong di lan man ca site
"""
from __future__ import annotations

import json
import re
import threading
import urllib.robotparser
from datetime import datetime
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

# Link kieu "Tai xuong (3.7 MB)" / "/download?id=123" khong co duoi file trong
# dia chi — hoi thang may chu bang HEAD de biet co phai tai lieu khong.
_CHU_TAI = re.compile(
    r"t[aả]i\s*(xu[oố]ng|v[eề])|download|t[aả]i\s*file|b[aả]n\s*pdf|xem\s*b[aả]n|"
    r"attachment|pdf|docx?|epub|t[aà]i\s*li[eệ]u", re.I)
_DUONG_TAI = re.compile(r"/(download|tai-xuong|taixuong|file|files|attachment|uploads?|"
                        r"releases/download|media)(/|\?|$)", re.I)


def _co_ve_tai_lieu(chu: str, url: str) -> bool:
    return bool(_CHU_TAI.search(chu or "") or _DUONG_TAI.search(url or ""))


def _hoi_dau_file(http, url: str) -> tuple[str, int]:
    """HEAD xem may chu bao day la file gi. Tra ve (duoi, so byte)."""
    try:
        r = http.get(url, timeout=12, stream=True)
        h = {k.lower(): v for k, v in r.headers.items()}
        r.close()
    except Exception:
        return "", 0
    kieu = (h.get("content-type") or "").split(";")[0].strip().lower()
    duoi = KIEU_OK.get(kieu, "")
    if not duoi:
        # vai may chu bao ten file trong Content-Disposition
        ten = h.get("content-disposition") or ""
        m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", ten)
        if m:
            duoi = PurePosixPath(unquote(m.group(1))).suffix.lstrip(".").lower()
    try:
        co = int(h.get("content-length") or 0)
    except ValueError:
        co = 0
    return (duoi if duoi in DUOI_OK or duoi in DUOI_BIET_NHUNG_CHUA_DOC else ""), co


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
                        "doc_duoc": d in DUOI_OK, "co": 0,
                    }
            elif (not d and _co_ve_tai_lieu(chu, day_du)
                  and day_du not in tim_thay and len(tim_thay) < max_file):
                # link kieu "Tai xuong (3.7 MB)" — dia chi khong co duoi file,
                # hoi thang may chu xem la file gi
                d2, co = _hoi_dau_file(http, day_du)
                if d2:
                    tim_thay[day_du] = {
                        "url": day_du, "ten": _ten_file(day_du, chu) if "." in
                        _ten_file(day_du, chu) else (re.sub(r"[\/:*?\"<>|]+", " ", chu)
                                                     .strip()[:70] or "tai-lieu") + "." + d2,
                        "duoi": d2, "nhan": chu[:120], "tu_trang": goc_url,
                        "tieu_de_trang": tieu_de, "doc_duoc": d2 in DUOI_OK, "co": co,
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
    # Ghi lai da lay nhung file nao, de lan sau kiem tra chi hien tai lieu MOI
    ten_da_tai = {t for t, _ in tai_ve}
    danh_dau_da_nhap([u for u in ds_url if (ten_goi.get(u) or _ten_file(u)) in ten_da_tai],
                     ten_goi)
    return ket


# ================================================================ theo doi nguon
# Nho lai trang da cao va nhung file da lay, de lan sau chi hien TAI LIEU MOI
# chu khong nhap trung. Khop theo dia chi file; file doi ten nhung cung dia chi
# van tinh la da co.
FILE_NGUON = store.DATA / "nguon_tai_lieu.json"


def _doc_nguon() -> list[dict]:
    try:
        d = json.loads(FILE_NGUON.read_text(encoding="utf-8"))
        return d if isinstance(d, list) else []
    except Exception:
        return []


def _ghi_nguon(ds: list[dict]) -> None:
    with _lock:
        FILE_NGUON.write_text(json.dumps(ds, ensure_ascii=False, indent=1), encoding="utf-8")


def ds_nguon() -> list[dict]:
    """Danh sach nguon dang theo doi (bo bot phan da_nhap cho nhe)."""
    ra = []
    for n in _doc_nguon():
        ra.append({k: v for k, v in n.items() if k != "da_nhap"}
                  | {"so_da_nhap": len(n.get("da_nhap") or {})})
    return ra


def _ma_nguon(dia_chi: list[str]) -> str:
    goc = urlparse(dia_chi[0]).netloc or "nguon"
    return re.sub(r"[^a-z0-9]+", "-", (goc + "-" + str(abs(hash(tuple(dia_chi))) % 10000)).lower())


def them_nguon(dia_chi: list[str], ten: str = "", sau: int = 1,
               max_trang: int = 60, tung_thay: list[str] | None = None) -> list[dict]:
    """Ghi mot nguon vao so theo doi.

    `tung_thay` = cac dia chi file da thay khi do. Can no vi file tai lieu hay
    nam o ten mien khac trang (CDN, GitHub Releases) — khong co danh sach nay
    thi luc danh dau "da nhap" se khong biet file thuoc nguon nao.
    """
    ds = _doc_nguon()
    dia_chi = [u.strip() for u in dia_chi if u.strip().startswith("http")]
    if not dia_chi:
        return ds_nguon()
    cu = next((n for n in ds if n["dia_chi"] == dia_chi), None)
    if cu is None:
        cu = {"ma": _ma_nguon(dia_chi), "ten": "", "dia_chi": dia_chi,
              "da_nhap": {}, "lan_kiem": "", "moi": 0}
        ds.append(cu)
    cu.update({"sau": sau, "max_trang": max_trang,
               "ten": ten or cu.get("ten") or urlparse(dia_chi[0]).netloc})
    if tung_thay:
        cu["tung_thay"] = sorted(set(cu.get("tung_thay") or []) | set(tung_thay))
    _ghi_nguon(ds)
    return ds_nguon()


def xoa_nguon(ma: str) -> list[dict]:
    _ghi_nguon([n for n in _doc_nguon() if n.get("ma") != ma])
    return ds_nguon()


def danh_dau_da_nhap(urls: list[str], ten_goi: dict | None = None) -> None:
    """Ghi lai nhung file vua nhap, cho moi nguon co chua dia chi do."""
    ten_goi = ten_goi or {}
    ds = _doc_nguon()
    if not ds:
        return
    luc = datetime.now().isoformat(timespec="seconds")
    for n in ds:
        nha = {urlparse(u).netloc for u in n["dia_chi"]}
        for u in urls:
            # file cua nguon nay: hoac cung ten mien, hoac da tung thay khi do
            if urlparse(u).netloc in nha or u in (n.get("da_nhap") or {}) \
                    or u in (n.get("tung_thay") or []):
                n.setdefault("da_nhap", {})[u] = {"ten": ten_goi.get(u, ""), "luc": luc}
    _ghi_nguon(ds)


def kiem_tra_moi(http, ma: str = "", bao_tien_do=None) -> dict:
    """Do lai cac nguon dang theo doi, tra ve nhung file CHUA tung nhap."""
    ds = _doc_nguon()
    can = [n for n in ds if not ma or n.get("ma") == ma]
    if not can:
        return {"nguon": [], "file": [], "loi": ["không có nguồn nào đang theo dõi"]}
    tat_ca, loi = [], []
    for i, n in enumerate(can):
        kq = do_trang(http, n["dia_chi"], sau=int(n.get("sau", 1)),
                      max_trang=int(n.get("max_trang", 60)),
                      bao_tien_do=(lambda x, t, ten="", i=i: bao_tien_do(
                          i * 100 + x, len(can) * 100, ten)) if bao_tien_do else None)
        loi += kq["loi"]
        da = set((n.get("da_nhap") or {}).keys())
        n["tung_thay"] = sorted({f["url"] for f in kq["file"]})
        n["lan_kiem"] = datetime.now().isoformat(timespec="seconds")
        moi = [f for f in kq["file"] if f["url"] not in da]
        for f in moi:
            f["nguon_ma"] = n["ma"]
            f["nguon_ten"] = n.get("ten", "")
        n["moi"] = len(moi)
        tat_ca += moi
    _ghi_nguon(ds)
    return {"nguon": ds_nguon(), "file": tat_ca, "loi": loi}


# ================================================================ nho AI loc giup
# Do bang duoi file thi chac an nhung van lan rac: README, LICENSE, mau don,
# file cau hinh cua trang... Nho AI san co cua app doc ten file + chu tren link
# + tieu de trang roi noi cai nao la tai lieu that, kem goi y mot cai ten de doc.
_NHAC_AI = (
    "Bạn giúp lọc danh sách file tải được từ một trang web.\n"
    "Với mỗi dòng, quyết định đó có phải TÀI LIỆU ĐỂ ĐỌC/HỌC không "
    "(sách, giáo trình, slide bài giảng, đề thi, bài tập, tóm tắt, ghi chú, truyện, báo cáo).\n"
    "KHÔNG phải tài liệu: README, LICENSE, CONTRIBUTING, CHANGELOG, file hướng dẫn của "
    "chính trang web, mẫu đơn trống, file cấu hình, ảnh bìa lẻ, file cài đặt.\n"
    "Trả về đúng mỗi dòng một kết quả, theo dạng:\n"
    "số|có hoặc không|tên gợi ý ngắn gọn dễ đọc\n"
    "Tên gợi ý: viết như tên một cuốn tài liệu cho người đọc.\n"
    "  - bỏ tiền tố kỹ thuật trong tên file (lecture-slides, exam-past, notes, "
    "summary...), bỏ gạch dưới, bỏ đuôi file;\n"
    "  - GIỮ LẠI chi tiết phân biệt: số chương, mã đề, học kỳ, mã môn;\n"
    "  - giữ nguyên ngôn ngữ của tài liệu, viết hoa chữ đầu.\n"
    "Không giải thích gì thêm."
)


def loc_bang_ai(ds_file: list[dict], cfg_ai: dict, bao_tien_do=None) -> dict:
    """Danh dau file nao la tai lieu that + dat ten de doc. Loi thi tra nguyen ban."""
    from . import ai as ai_mod                       # noqa: PLC0415

    if not ds_file:
        return {"file": ds_file, "loi": ""}
    lo, xong = 12, 0
    loi = ""
    for i in range(0, len(ds_file), lo):
        phan = ds_file[i:i + lo]
        dong = []
        for k, f in enumerate(phan, 1):
            dong.append(f"{k}. tên file: {f['ten']} | chữ trên link: {f.get('nhan', '')}"
                        f" | trang: {f.get('tieu_de_trang', '')}")
        try:
            out = ai_mod.chat(cfg_ai, [
                {"role": "system", "content": _NHAC_AI},
                {"role": "user", "content": "\n".join(dong)},
            ], temperature=0.1, max_tokens=120 * len(phan) + 300)
        except Exception as exc:
            loi = f"{type(exc).__name__}: {exc}"
            break
        for d in out.splitlines():
            m = re.match(r"\s*(\d{1,3})\s*[.|)]\s*([^|]*)\|?\s*(.*)", d.strip())
            if not m:
                continue
            k = int(m.group(1)) - 1
            if not (0 <= k < len(phan)):
                continue
            tra_loi = (m.group(2) or "").strip().lower()
            ten_moi = (m.group(3) or "").strip(" |")
            phan[k]["ai_tai_lieu"] = not tra_loi.startswith(("khong", "không", "no"))
            if ten_moi and 3 <= len(ten_moi) <= 120:
                phan[k]["ai_ten"] = ten_moi
        xong += len(phan)
        if bao_tien_do:
            bao_tien_do(xong, len(ds_file), "AI đang lọc")
    return {"file": ds_file, "loi": loi}
