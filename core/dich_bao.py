# -*- coding: utf-8 -*-
"""Dich tin tuc — muon nguyen bo may dich cua du an DichVanNang.

Thu tu uu tien (dung dung "mang loc" cua ban goc):
  1. Bo nho dich (TM) khop 100%        -> lay luon, khong ton AI
  2. Trung -> Viet: tach cum bang tu dien VietPhrase/HanViet -> ban nhap
     -> AI danh bong (co bang tu vung + vi du TM lam guide)
  3. Cac huong con lai (Anh/Phap/Nga/Nhat/Bo Dao Nha -> Viet/Trung/Anh):
     AI dich theo lo, co cache
Thieu DichVanNang hoac Ollama tat thi tra ve nguyen van, khong lam app chet.
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import re
import sys
import threading
import unicodedata
from pathlib import Path

from . import store

DUONG_MAC_DINH = r"D:\Code\DichVanNang"
FILE_CACHE = store.DATA / "dich_bao_cache.json"

TEN_NGON_NGU = {"vi": "tiếng Việt", "zh": "中文（简体）", "en": "English"}
TEN_NGUON = {"vi": "tiếng Việt", "en": "tiếng Anh", "zh": "tiếng Trung", "ja": "tiếng Nhật",
             "fr": "tiếng Pháp", "ru": "tiếng Nga", "pt": "tiếng Bồ Đào Nha"}

_lock = threading.Lock()
_may = None            # bo may da nap (nap 1 lan, dung lai)
_cache = None

# Ca hai du an deu co goi ten "core" -> khong the `from core import ...`, se an
# nham core cua chinh app nay. Nap goi cua DichVanNang duoi ten rieng "dvn_core"
# de import tuong doi (`from . import config`) ben trong no van chay dung.
GOI = "dvn_core"


def _nap_goi(goc: Path):
    if GOI not in sys.modules:
        thu_muc = goc / "core"
        spec = importlib.util.spec_from_file_location(
            GOI, thu_muc / "__init__.py", submodule_search_locations=[str(thu_muc)])
        mod = importlib.util.module_from_spec(spec)
        sys.modules[GOI] = mod
        spec.loader.exec_module(mod)
    return lambda ten: importlib.import_module(f"{GOI}.{ten}")


# ================================================================ cache
def _doc_cache() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(FILE_CACHE.read_text(encoding="utf-8"))
        except Exception:
            _cache = {}
    return _cache


def _ghi_cache() -> None:
    if _cache is None:
        return
    try:
        with _lock:
            FILE_CACHE.write_text(json.dumps(_cache, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _khoa(text: str, sang: str) -> str:
    return hashlib.md5((sang + "\u0000" + text).encode("utf-8")).hexdigest()


# ================================================================ nap bo may
class _BoMay:
    def __init__(self, goc: Path):
        self.goc = goc
        self.tu_dien = None
        self.ai = None
        self.fuse = None
        self.cfg = None
        self.loi = ""
        self._nap_xong = False
        self._nap_lock = threading.Lock()

    def nap(self):
        """Nap tu dien (nang, ~679k dong) — chi lam khi that su can dich."""
        if self._nap_xong:
            return
        with self._nap_lock:
            if self._nap_xong:
                return
            try:
                lay = _nap_goi(self.goc)
                dvn_ai, dvn_config = lay("ai"), lay("config")
                dvn_dict, dvn_fuse = lay("dictionary"), lay("fuse")
                self.cfg = dvn_config.doc()
                cd = store.load_settings()
                self.cfg["ai"]["url"] = cd.get("bao_ai_url") or self.cfg["ai"]["url"]
                self.cfg["ai"]["model"] = cd.get("bao_ai_model") or self.cfg["ai"]["model"]
                self.ai = dvn_ai.OllamaAI(self.cfg)
                self.fuse = dvn_fuse
                self.tu_dien = dvn_dict.TuDien(self.cfg)
                self.tu_dien.nap()
            except Exception as exc:
                self.loi = f"{type(exc).__name__}: {exc}"
            self._nap_xong = True


def _bo_may() -> _BoMay | None:
    global _may
    if _may is None:
        goc = Path(store.load_settings().get("dich_thu_muc") or DUONG_MAC_DINH)
        if not (goc / "core" / "dictionary.py").is_file():
            return None
        _may = _BoMay(goc)
    return _may


def trang_thai() -> dict:
    """Bao cho giao dien biet bo dich co san sang khong (khong nap tu dien)."""
    goc = Path(store.load_settings().get("dich_thu_muc") or DUONG_MAC_DINH)
    co = (goc / "core" / "dictionary.py").is_file()
    ra = {"co_bo_dich": co, "thu_muc": str(goc), "co_ai": False, "model": "", "loi": ""}
    if not co:
        ra["loi"] = "không thấy DichVanNang ở " + str(goc)
        return ra
    try:
        lay = _nap_goi(goc)
        dvn_ai, dvn_config = lay("ai"), lay("config")
        cfg = dvn_config.doc()
        cd = store.load_settings()
        cfg["ai"]["url"] = cd.get("bao_ai_url") or cfg["ai"]["url"]
        cfg["ai"]["model"] = cd.get("bao_ai_model") or cfg["ai"]["model"]
        may = dvn_ai.OllamaAI(cfg)
        ra["co_ai"] = may.san_sang()
        ra["model"] = cfg["ai"]["model"]
        ra["url"] = cfg["ai"]["url"]
    except Exception as exc:
        ra["loi"] = f"{type(exc).__name__}: {exc}"
    return ra


# ================================================================ dich
def _giong_nhau(a: str, b: str) -> bool:
    chuan = lambda s: re.sub(r"\W+", "", unicodedata.normalize("NFC", s or "")).lower()  # noqa: E731
    return chuan(a) == chuan(b)


HE_THONG = (
    "Bạn là biên dịch viên báo chí. Dịch sang {dich}.\n"
    "Quy tắc:\n"
    "1. Chỉ trả về bản dịch theo đúng định dạng được yêu cầu, không giải thích.\n"
    "2. Giữ nguyên tên riêng, tên người, địa danh, tên tổ chức theo cách gọi phổ biến "
    "trong {dich}; số liệu và ngày tháng giữ nguyên.\n"
    "3. Văn phong báo chí: ngắn gọn, trung tính, không thêm bình luận.\n"
    "4. Không bỏ sót mục nào, giữ đúng số thứ tự."
)


def _dich_lo_ai(may: _BoMay, cac_doan: list[str], tu_lang: str, sang: str) -> list[str]:
    """Dich mot lo cau ngan bang AI. Tra ve list cung do dai (thieu thi de nguyen van)."""
    if not cac_doan:
        return []
    danh_sach = "\n".join(f"{i + 1}. {d}" for i, d in enumerate(cac_doan))
    msgs = [
        {"role": "system", "content": HE_THONG.format(dich=TEN_NGON_NGU.get(sang, sang))},
        {"role": "user", "content":
            f"Dịch {len(cac_doan)} dòng {TEN_NGUON.get(tu_lang, tu_lang)} dưới đây sang "
            f"{TEN_NGON_NGU.get(sang, sang)}. Trả về đúng {len(cac_doan)} dòng, "
            f"mỗi dòng bắt đầu bằng số thứ tự và dấu chấm:\n\n" + danh_sach},
    ]
    out = may.ai.chat(msgs, temperature=0.2, num_predict=200 * len(cac_doan) + 200)
    ra = [""] * len(cac_doan)
    for dong in out.splitlines():
        m = re.match(r"\s*(\d{1,3})\s*[.)\]:]\s*(.+)", dong)
        if m:
            i = int(m.group(1)) - 1
            if 0 <= i < len(ra) and not ra[i]:
                ra[i] = m.group(2).strip()
    return [r or goc for r, goc in zip(ra, cac_doan)]


def _dich_zh_vi(may: _BoMay, text: str) -> str:
    """Trung -> Viet: di dung duong cua DichVanNang (TM -> tu dien -> AI danh bong)."""
    san = may.tu_dien.tra_cau(text)
    if san is not None:
        return san
    segments = may.tu_dien.tach(text)
    ban_nhap = may.fuse.ghep_convert(segments)
    phu = may.tu_dien.phu_song(segments)
    if may.ai.san_sang() and phu < 0.99:
        try:
            out = may.ai.dich(text, lang="zh", ban_nhap=ban_nhap,
                              tu_vung=may.fuse.tu_vung_tu_segments(segments),
                              vi_du=may.tu_dien.vi_du(text, 4))
            if out and not re.search(r"[\u4e00-\u9fff]", out):
                may.tu_dien.them_cache(text, out)
                return out
        except Exception:
            pass
    return ban_nhap


def dich_doan(doan: list[str], tu_lang: str, sang: str, bao_tien_do=None) -> dict:
    """Dich tron mot bai (danh sach doan van) sang `sang`.

    Gop lo theo SO KY TU chu khong theo so doan — doan bao dai ngan that thuong,
    gop cung 8 doan de co lo dai qua cua so cua model.
    """
    if sang not in TEN_NGON_NGU:
        return {"doan": doan, "loi": "ngôn ngữ đích không hợp lệ"}
    tu_lang = (tu_lang or "").lower()[:2]
    if tu_lang == sang:
        return {"doan": doan, "loi": ""}
    may = _bo_may()
    if may is None:
        return {"doan": doan, "loi": "chưa cài DichVanNang — vào Cài đặt chỉ đúng thư mục"}
    may.nap()
    if may.loi:
        return {"doan": doan, "loi": "không nạp được bộ dịch: " + may.loi}

    cache = _doc_cache()
    ra: list[str] = [""] * len(doan)
    con: list[int] = []
    for i, d in enumerate(doan):
        san = cache.get(_khoa(d, sang))
        if san:
            ra[i] = san
        else:
            con.append(i)
    if not con:
        return {"doan": ra, "loi": ""}

    co_ai = may.ai.san_sang()
    xong = 0

    def nhip(n):
        nonlocal xong
        xong += n
        if bao_tien_do:
            bao_tien_do(xong, len(con))

    if tu_lang == "zh" and sang == "vi":            # di duong tu dien VietPhrase
        for i in con:
            try:
                ra[i] = _dich_zh_vi(may, doan[i])
                cache[_khoa(doan[i], sang)] = ra[i]
            except Exception:
                ra[i] = doan[i]
            nhip(1)
    elif not co_ai:
        for i in con:
            ra[i] = doan[i]
        nhip(len(con))
        return {"doan": ra,
                "loi": "Ollama đang tắt nên chưa dịch được thứ tiếng này. "
                       "Bật Ollama rồi bấm dịch lại."}
    else:
        lo, dai = [], 0
        for i in con + [None]:
            if i is not None and (dai + len(doan[i]) < 1200 or not lo):
                lo.append(i)
                dai += len(doan[i])
                if len(lo) < 8:
                    continue
            if lo:
                try:
                    kq = _dich_lo_ai(may, [doan[k] for k in lo], tu_lang, sang)
                except Exception:
                    kq = [doan[k] for k in lo]
                for k, v in zip(lo, kq):
                    ra[k] = v
                    if v and not _giong_nhau(v, doan[k]):
                        cache[_khoa(doan[k], sang)] = v
                nhip(len(lo))
            lo, dai = ([i], len(doan[i])) if i is not None else ([], 0)
    _ghi_cache()
    return {"doan": [r or g for r, g in zip(ra, doan)], "loi": ""}


def dich_bai(bai: list[dict], sang: str, dich_tom_tat=True, bao_tien_do=None) -> dict:
    """Dich list bai (moi bai co tieu_de/tom_tat/lang) sang `sang` (vi|zh|en).

    Tra ve {"ban_dich": {khoa_bai: {...}}, "so_dich": n, "loi": ""}.
    """
    if sang not in TEN_NGON_NGU:
        return {"ban_dich": {}, "so_dich": 0, "loi": "ngôn ngữ đích không hợp lệ"}
    may = _bo_may()
    if may is None:
        return {"ban_dich": {}, "so_dich": 0,
                "loi": "chưa cài DichVanNang — vào Cài đặt chỉ đúng thư mục"}

    cache = _doc_cache()
    ban_dich: dict[str, dict] = {}
    can_ai: dict[str, list[tuple[str, str]]] = {}     # lang -> [(khoa, text)]
    from .bao import _khoa as khoa_bai                 # dung chung cach dat khoa

    def lay_cache(t):
        return cache.get(_khoa(t, sang))

    # ---- vong 1: cai gi lay duoc ngay thi lay (cache / khong can dich) ----
    can_nap = False
    for b in bai:
        lang = (b.get("lang") or "").lower()[:2]
        cac_doan = [("tieu_de", b.get("tieu_de", ""))]
        if dich_tom_tat and b.get("tom_tat"):
            cac_doan.append(("tom_tat", b["tom_tat"]))
        d = {}
        for ten_truong, text in cac_doan:
            if not text:
                continue
            if lang == sang:                           # da dung ngon ngu roi
                continue
            sn = lay_cache(text)
            if sn:
                d[ten_truong] = sn
            else:
                can_nap = True
                can_ai.setdefault(lang or "en", []).append((khoa_bai(b) + "|" + ten_truong, text))
        if d:
            d["lang"] = sang
            ban_dich[khoa_bai(b)] = d

    if not can_nap:
        return {"ban_dich": ban_dich, "so_dich": len(ban_dich), "loi": ""}

    may.nap()
    if may.loi:
        return {"ban_dich": ban_dich, "so_dich": len(ban_dich),
                "loi": "không nạp được bộ dịch: " + may.loi}

    co_ai = may.ai.san_sang()
    tong = sum(len(v) for v in can_ai.values())
    xong = 0
    moi = {}

    for lang, muc in can_ai.items():
        # Trung -> Viet: di duong tu dien (chay duoc ca khi tat AI)
        if lang == "zh" and sang == "vi":
            for khoa, text in muc:
                try:
                    moi[khoa] = _dich_zh_vi(may, text)
                except Exception:
                    moi[khoa] = text
                xong += 1
                if bao_tien_do:
                    bao_tien_do(xong, tong)
            continue
        if not co_ai:
            xong += len(muc)
            if bao_tien_do:
                bao_tien_do(xong, tong)
            continue
        lo = 8
        for i in range(0, len(muc), lo):
            phan = muc[i:i + lo]
            try:
                kq = _dich_lo_ai(may, [t for _, t in phan], lang, sang)
            except Exception:
                kq = [t for _, t in phan]
            for (khoa, goc), ra in zip(phan, kq):
                moi[khoa] = ra
            xong += len(phan)
            if bao_tien_do:
                bao_tien_do(xong, tong)

    # ---- gop ket qua + ghi cache ----
    for khoa_truong, ra in moi.items():
        khoa, truong = khoa_truong.rsplit("|", 1)
        goc = next((b for b in bai if khoa_bai(b) == khoa), None)
        if goc is None or not ra:
            continue
        text_goc = goc.get(truong, "")
        if _giong_nhau(ra, text_goc):
            continue
        cache[_khoa(text_goc, sang)] = ra
        ban_dich.setdefault(khoa, {"lang": sang})[truong] = ra
    _ghi_cache()

    loi = ""
    if not co_ai and any(k != "zh" for k in can_ai):
        loi = ("Ollama đang tắt nên chỉ dịch được Trung→Việt bằng từ điển. "
               "Bật Ollama rồi bấm dịch lại để dịch các thứ tiếng khác.")
    return {"ban_dich": ban_dich, "so_dich": len(ban_dich), "loi": loi}
