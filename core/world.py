"""Tham nhap the gioi truyen: AI phan tich toan bo chuong, dung "so tay the
gioi" (world bible), roi cho nguoi dung tao nhan vat va song trong truyen —
moi hanh dong sinh ra mot chuong moi.

Du lieu nam ngay trong thu muc truyen:
    <thu muc truyen>/the-gioi/
        phan-tich/lo-0001.json   ghi chu AI rut ra tu tung lo chuong (de tai tiep)
        tong-hop.json            ghi chu da gop lai vua tam mot lan goi AI
        world.json               so tay the gioi hoan chinh (7 muc)
        phien/<id>.json          tung lan choi: nhan vat + cac chuong da sinh
"""
from __future__ import annotations

import json
import re
import threading
import time
import traceback
import uuid
from pathlib import Path

from . import ai, reader, store

# mot lan choi giu toi da bay nhieu chuong gan nhat trong prompt
SO_CHUONG_NHO = 2
# cach may chuong thi gop bot vao tom tat hanh trinh
NHIP_TOM_TAT = 4
# ngan sach ky tu cho moi lan gop ghi chu
NGAN_SACH_GOP = 48000

# ---------------------------------------------------------------- duong dan
def _wdir(folder: str | Path) -> Path:
    return Path(folder) / "the-gioi"


def world_path(folder) -> Path:
    return _wdir(folder) / "world.json"


def has_world(folder) -> bool:
    return world_path(folder).is_file()


def load_world(folder) -> dict | None:
    try:
        return json.loads(world_path(folder).read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def _cap(text: str, n: int) -> str:
    """Cat bot cho vua ngan sach prompt, giu phan dau (phan quan trong nhat)."""
    text = (text or "").strip()
    return text if len(text) <= n else text[:n] + "\n…(đã cắt bớt cho vừa)…"


# ================================================================ XAY THE GIOI
GIAI_DOAN = [
    ("doc",          "Đọc và phân tích toàn bộ chương truyện"),
    ("gop",          "Gộp ghi chú, nắm khái quát thế giới"),
    ("tong_quan",    "Tổng quan: thế giới, cốt truyện, văn phong"),
    ("lich_su",      "Lịch sử: thời đại, chiến tranh, nguyên nhân – hậu quả"),
    ("ban_do",       "Bản đồ: quốc gia, khu vực, khoảng cách, liên kết"),
    ("the_gioi_song", "Thời gian & môi trường: mùa, thời tiết, sinh thái"),
    ("nhan_vat",     "Nhân vật chính/phụ và quy tắc sinh NPC mới"),
    ("phe_phai",     "Phe phái & chính trị: lợi ích, xung đột, quyền lực"),
    ("van_hoa",      "Văn hoá & kinh tế: phong tục, tiền tệ, giá cả"),
    ("quy_luat",     "Quy luật thế giới: ma pháp, nhân quả, cái chết"),
    ("gioi_han",     "Giới hạn & hệ thống sức mạnh"),
    ("bi_an",        "Bí mật & ba tầng thông tin"),
    ("khu_vuc",      "Khu vực & sự kiện theo độ hiếm, điều kiện kích hoạt"),
]

_PROMPT_TRICH = """Bạn là trợ lý phân tích tiểu thuyết. Dưới đây là các chương {tu}–{den} của truyện "{ten}".
Hãy RÚT RA GHI CHÚ NGẮN GỌN phục vụ xây dựng thế giới, theo đúng các đề mục sau (mục nào không có thông tin thì ghi "không"):

## Nhân vật
(tên — vai trò, tính cách, sức mạnh/cấp bậc, đang ở đâu, quan hệ đáng chú ý)
## Địa điểm
(tên — thuộc vùng nào, đặc điểm, nối với nơi nào)
## Thế lực / tổ chức
## Hệ thống sức mạnh & giới hạn
(cấp bậc, quy tắc, cái giá phải trả, điều KHÔNG thể làm)
## Vật phẩm / cơ duyên
(kèm độ hiếm nếu đoán được)
## Sự kiện chính
(tóm tắt 1 dòng mỗi sự kiện, theo thứ tự)
## Bí ẩn / phục bút
(điều được úp mở nhưng chưa giải thích)
## Thời tiết / môi trường / phong tục

Viết bằng tiếng Việt, gạch đầu dòng, tổng cộng dưới 600 từ. KHÔNG bình luận gì thêm.

--- NỘI DUNG CHƯƠNG ---
{noi_dung}"""

_PROMPT_GOP = """Bạn là trợ lý xây dựng thế giới tiểu thuyết. Dưới đây là nhiều phần ghi chú rút ra từ truyện "{ten}" (theo thứ tự thời gian truyện).
Hãy GỘP chúng thành MỘT bản ghi chú duy nhất, giữ nguyên các đề mục (Nhân vật, Địa điểm, Thế lực, Hệ thống sức mạnh & giới hạn, Vật phẩm/cơ duyên, Sự kiện chính, Bí ẩn, Thời tiết/môi trường):
- Gộp mục trùng nhau, giữ chi tiết quan trọng, cập nhật theo diễn biến mới nhất.
- Nhân vật/địa điểm/thế lực quan trọng giữ đủ; loại lặt vặt chỉ xuất hiện 1 lần và không ảnh hưởng gì.
- Sự kiện chính giữ mạch cốt truyện từ đầu đến cuối, mỗi sự kiện 1 dòng.
Viết tiếng Việt, gạch đầu dòng, dưới 1200 từ. KHÔNG bình luận gì thêm.

--- CÁC PHẦN GHI CHÚ ---
{noi_dung}"""

# moi muc cua so tay the gioi: (khoa, huong dan viet)
_MUC_SO_TAY = {
    "tong_quan": """Viết mục **TỔNG QUAN THẾ GIỚI**: bối cảnh, thời đại, không khí truyện, văn phong tác giả (để sau này viết tiếp đúng giọng), các chủ đề chính, quy luật và chi tiết ẩn đáng chú ý ngay từ đầu, và dòng thời gian cốt truyện gốc tóm gọn (10–25 mốc, có ước lượng thời gian giữa các mốc). Dưới 700 từ.""",
    "lich_su": """Viết mục **LỊCH SỬ THẾ GIỚI**: các thời đại từ xa xưa đến hiện tại, những nền văn minh đã tồn tại/diệt vong, các cuộc chiến tranh và sự kiện lớn — với MỖI sự kiện ghi rõ nguyên nhân → diễn biến → hậu quả còn ảnh hưởng đến hiện tại. Di sản, tàn tích, mối thù truyền kiếp bắt nguồn từ lịch sử. Dưới 700 từ.""",
    "ban_do": """Viết mục **CẤU TRÚC & BẢN ĐỒ THẾ GIỚI**: các quốc gia/lãnh thổ lớn → thành phố/khu vực bên trong → địa hình đặc trưng; KHOẢNG CÁCH và thời gian di chuyển giữa các nơi (theo phương tiện phổ biến của truyện); tuyến đường, cửa ngõ, mức nguy hiểm từng tuyến; cơ duyên/bảo vật gắn với từng vùng. Trình bày dạng cây + gạch đầu dòng cho dễ tra. Dưới 900 từ.""",
    "the_gioi_song": """Viết mục **THỜI GIAN & MÔI TRƯỜNG**:
1) Thời gian: chu kỳ ngày/đêm, lịch và mùa, lễ hội định kỳ, thiên tượng đặc biệt; dòng thời gian trôi thế nào so với sự kiện nguyên tác.
2) Môi trường: khí hậu từng vùng, động thực vật và quái vật đặc trưng, tài nguyên ở đâu, chuỗi sinh thái ảnh hưởng lẫn nhau ra sao (săn quá tay thì sao, khai thác cạn thì sao).
3) Thế giới PHẢN ỨNG với con người thế nào: gây chuyện ai đến xử, nổi danh tin đồn lan ra sao. Dưới 800 từ.""",
    "nhan_vat": """Viết mục **NHÂN VẬT**:
1) Nhân vật chính nguyên tác: tính cách, mục tiêu, ký ức then chốt, sức mạnh, hành trình và hiện diện ở đâu theo từng giai đoạn.
2) Nhân vật phụ quan trọng (mỗi người 2–3 dòng: tính cách, mục tiêu, phe, khu vực hoạt động, quan hệ đáng chú ý, thái độ với người lạ).
3) Khả năng PHÁT TRIỂN/THAY ĐỔI của từng người nếu hoàn cảnh đổi (ai dễ ngả về phe nào, ai ôm hận gì).
4) QUY TẮC SINH NPC MỚI: cách đặt tên hợp văn phong, phân bố sức mạnh hợp lý theo khu vực, nghề nghiệp thường gặp, đa dạng tính cách — NPC mới cũng phải có mục tiêu riêng. Dưới 1000 từ.""",
    "phe_phai": """Viết mục **PHE PHÁI & CHÍNH TRỊ**: các quốc gia, tổ chức, tôn giáo, gia tộc, liên minh — với MỖI phe: lợi ích cốt lõi, kẻ đứng đầu, thực lực, đồng minh/kẻ thù, xung đột đang diễn ra. Bức tranh quyền lực: ai nắm quyền ở đâu, ngoại giao giữa các bên, luật pháp và cách thực thi, những tranh chấp có thể bùng nổ và kịch bản thay đổi chính quyền. Dưới 900 từ.""",
    "van_hoa": """Viết mục **VĂN HOÁ & KINH TẾ**:
1) Văn hoá: kiến trúc nhà cửa/thành phố, trang phục theo tầng lớp, phong tục và cấm kỵ, ngôn ngữ/cách xưng hô, ẩm thực, tín ngưỡng.
2) Kinh tế: hệ thống tiền tệ, bảng giá tham khảo (bữa ăn, một đêm trọ, vũ khí thường, vật phẩm quý…), các tuyến thương mại, nghề nghiệp phổ biến và thu nhập, yếu tố làm thị trường biến động. Dưới 800 từ.""",
    "quy_luat": """Viết mục **QUY LUẬT THẾ GIỚI** — các quy tắc vận hành nền tảng: vật lý có gì khác thường; ma pháp/năng lượng/tu luyện vận hành theo nguyên lý nào; yếu tố linh dị/siêu nhiên; luật nhân quả của thế giới; quy tắc về CÁI CHẾT — chết rồi có hồi sinh được không, điều kiện và cái giá, linh hồn đi đâu; điều gì xảy ra với kẻ phạm quy luật. Dưới 700 từ.""",
    "gioi_han": """Viết mục **GIỚI HẠN & HỆ THỐNG SỨC MẠNH**:
1) Hệ thống sức mạnh đầy đủ: các cấp bậc thấp → cao, phương thức phát triển từng con đường, ưu/nhược điểm, điều kiện đột phá, thời gian tu luyện hợp lý, CÁI GIÁ phải trả, quan hệ tương khắc giữa các hệ.
2) Trần sức mạnh của thế giới; giới hạn tài nguyên và công nghệ.
3) Những điều TUYỆT ĐỐI không thể phá vỡ, và quy tắc cân bằng để người chơi không thể mạnh lên phi lý. Dưới 800 từ.""",
    "bi_an": """Viết mục **BÍ MẬT** (tuyệt mật, chỉ quản trò biết): lịch sử bị che giấu, tổ chức bí mật, di tích và vật phẩm ẩn, thân phận thật của nhân vật, chân tướng các sự kiện. Đánh số từng bí mật; với MỖI bí mật ghi rõ:
- Ba tầng thông tin: chỉ GM biết gì / nhân vật nào trong truyện biết phần nào / manh mối nào đang lộ công khai.
- ĐIỀU KIỆN để người chơi lần ra được. Dưới 800 từ.""",
    "khu_vuc": """Viết mục **BỐ CỤC KHU VỰC & SỰ KIỆN**: chọn 4–8 khu vực quan trọng nhất, với TỪNG khu:
- Bố cục bên trong (địa danh con), NPC đặc trưng thường gặp, hoạt động người chơi làm được, tài nguyên, mối nguy hiểm.
- BẢNG SỰ KIỆN phân theo độ hiếm: [Phổ biến] gặp hằng ngày · [Không thường] thỉnh thoảng · [Hiếm] cơ duyên nhỏ / nguy hiểm thật · [Cực hiếm] biến cố đổi đời · [Độc nhất] chỉ xảy ra MỘT lần duy nhất trong cả thế giới.
- Sự kiện từ bậc [Hiếm] trở lên phải kèm ĐIỀU KIỆN KÍCH HOẠT (đến đúng lúc, đủ thực lực, cầm đúng vật, quen đúng người…).
Mỗi khu 2–5 sự kiện mỗi bậc khi đủ chất liệu. Dưới 1200 từ.""",
}


class WorldBuild:
    """Mot luot xay the gioi chay nen, hoi tien do qua to_dict()."""

    def __init__(self, url: str, folder: str, title: str, mode: str):
        self.url = url
        self.folder = folder
        self.title = title
        self.mode = mode                    # "day_du" | "nhanh"
        self.status = "dang chay"           # dang chay | xong | loi | da huy
        self.stage = "doc"
        self.done = 0                       # buoc da xong trong giai doan hien tai
        self.total = 0
        self.message = ""
        self.created = time.time()
        self.cancel = threading.Event()

    def to_dict(self) -> dict:
        stages = [k for k, _ in GIAI_DOAN]
        return {
            "url": self.url, "status": self.status, "stage": self.stage,
            "stage_index": stages.index(self.stage) if self.stage in stages else 0,
            "stages": [{"id": k, "ten": t} for k, t in GIAI_DOAN],
            "done": self.done, "total": self.total,
            "message": self.message, "mode": self.mode, "created": self.created,
        }


_builds: dict[str, WorldBuild] = {}
_builds_lock = threading.Lock()


def build_status(url: str) -> dict | None:
    b = _builds.get(url)
    return b.to_dict() if b else None


def cancel_build(url: str) -> bool:
    b = _builds.get(url)
    if not b or b.status != "dang chay":
        return False
    b.cancel.set()
    return True


def start_build(url: str, folder: str, title: str, mode: str = "day_du",
                lam_lai: bool = False) -> dict:
    """Bat dau (hoac tiep tuc) xay the gioi trong luong nen."""
    with _builds_lock:
        b = _builds.get(url)
        if b and b.status == "dang chay":
            return b.to_dict()
        if lam_lai:
            # xoa ket qua cu de phan tich lai tu dau
            import shutil
            for name in ("phan-tich", "tong-hop.json", "world.json"):
                p = _wdir(folder) / name
                try:
                    shutil.rmtree(p) if p.is_dir() else p.unlink(missing_ok=True)
                except OSError:
                    pass
        b = WorldBuild(url, folder, title, mode)
        _builds[url] = b
        threading.Thread(target=_run_build, args=(b,), daemon=True).start()
        return b.to_dict()


def _run_build(b: WorldBuild):
    try:
        cfg = store.load_settings()["ai"]
        _build(b, cfg)
        if b.cancel.is_set():
            b.status = "da huy"
            b.message = "Đã dừng. Phần đã phân tích được giữ lại — bấm Khởi tạo lần nữa sẽ chạy tiếp."
        else:
            b.status = "xong"
            b.message = "Thế giới đã sẵn sàng!"
    except ai.AiError as exc:
        b.status = "loi"
        b.message = str(exc)
    except Exception:
        b.status = "loi"
        b.message = "Lỗi không lường trước:\n" + traceback.format_exc(limit=2)


def _batches(chapters: list[dict], folder: str, chunk_chars: int, mode: str):
    """Chia danh sach chuong thanh cac lo ~chunk_chars ky tu.

    mode "nhanh": chi lay mau deu ~60 lo cho truyen qua dai (do t/g cho AI yeu).
    Tra ve list[(tu_index, den_index, [chuong_dict...])].
    """
    los, hien_tai, dem = [], [], 0
    for c in chapters:
        # uoc luong bang do dai file, khoi phai doc noi dung 2 lan
        p = Path(folder) / "chuong" / f"{c['index']:05d}.txt"
        try:
            size = p.stat().st_size
        except OSError:
            size = 4000
        hien_tai.append(c)
        dem += size
        if dem >= chunk_chars:
            los.append((hien_tai[0]["index"], hien_tai[-1]["index"], hien_tai))
            hien_tai, dem = [], 0
    if hien_tai:
        los.append((hien_tai[0]["index"], hien_tai[-1]["index"], hien_tai))
    if mode == "nhanh" and len(los) > 60:
        buoc = len(los) / 60
        los = [los[int(i * buoc)] for i in range(60)]
    return los


def _doc_lo(folder: str, chuongs: list[dict]) -> str:
    """Ghep noi dung cac chuong trong mot lo (da qua bo loc chu)."""
    phan = []
    for c in chuongs:
        d = reader.read_chapter(folder, c["index"])
        if d:
            phan.append(f"### {d['title']}\n" + "\n".join(d["lines"]))
    return "\n\n".join(phan)


def _build(b: WorldBuild, cfg: dict):
    folder = b.folder
    wdir = _wdir(folder)
    pdir = wdir / "phan-tich"
    pdir.mkdir(parents=True, exist_ok=True)

    chapters = reader.list_chapters(folder)
    if not chapters:
        raise ai.AiError("Không tìm thấy chương nào đã tải về của truyện này.")

    # ---------- giai doan 1: doc & trich xuat theo lo ----------
    b.stage = "doc"
    los = _batches(chapters, folder, int(cfg.get("chunk_chars") or 20000), b.mode)
    b.total = len(los)
    for i, (tu, den, chuongs) in enumerate(los, 1):
        if b.cancel.is_set():
            return
        f = pdir / f"lo-{i:04d}.json"
        if f.is_file():                      # da phan tich lan truoc -> bo qua
            b.done = i
            continue
        b.message = f"Đang phân tích chương {tu}–{den} ({i}/{len(los)} lô)…"
        noi_dung = _doc_lo(folder, chuongs)
        ghi_chu = ai.chat(cfg, [
            {"role": "system",
             "content": "Bạn là công cụ trích xuất dữ liệu. Chỉ trả về đúng các đề mục "
                        "được yêu cầu, không chào hỏi, không mở bài, không bình luận."},
            {"role": "user", "content": _PROMPT_TRICH.format(
                tu=tu, den=den, ten=b.title, noi_dung=noi_dung)}], temperature=0.3)
        _save_json(f, {"tu": tu, "den": den, "ghi_chu": ghi_chu, "luc": time.time()})
        b.done = i

    # ---------- giai doan 2: gop ghi chu (gop tang nhieu lop neu qua dai) ----------
    b.stage = "gop"
    b.done, b.total = 0, 1
    f_gop = wdir / "tong-hop.json"
    ghi_chus = []
    for f in sorted(pdir.glob("lo-*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            ghi_chus.append(f"[Chương {d['tu']}–{d['den']}]\n{d['ghi_chu']}")
        except Exception:
            continue
    if not ghi_chus:
        raise ai.AiError("Không có ghi chú phân tích nào — giai đoạn đọc bị lỗi?")

    cache = None
    try:
        cache = json.loads(f_gop.read_text(encoding="utf-8"))
    except Exception:
        pass
    if cache and cache.get("so_lo") == len(ghi_chus):
        tong_hop = cache["ghi_chu"]
    else:
        lop = 0
        while True:
            if b.cancel.is_set():
                return
            gop_lai = ["\n\n".join(nhom) for nhom in _chia_ngan_sach(ghi_chus)]
            if len(gop_lai) == 1 and len(gop_lai[0]) <= NGAN_SACH_GOP:
                if len(ghi_chus) == 1:
                    tong_hop = ghi_chus[0]
                    break
            lop += 1
            b.total = len(gop_lai)
            moi = []
            for i, phan in enumerate(gop_lai, 1):
                if b.cancel.is_set():
                    return
                b.done = i - 1
                b.message = f"Đang gộp ghi chú lớp {lop} ({i}/{len(gop_lai)})…"
                moi.append(ai.chat(cfg, [
                    {"role": "system",
                     "content": "Bạn là công cụ gộp ghi chú. Chỉ trả về bản ghi chú đã "
                                "gộp, không chào hỏi, không bình luận."},
                    {"role": "user", "content": _PROMPT_GOP.format(
                        ten=b.title, noi_dung=phan)}], temperature=0.3))
            ghi_chus = moi
            if len(ghi_chus) == 1:
                tong_hop = ghi_chus[0]
                break
        _save_json(f_gop, {"so_lo": len(list(pdir.glob('lo-*.json'))),
                           "ghi_chu": tong_hop, "luc": time.time()})
    b.done = b.total

    # ---------- giai doan 3..9: viet tung muc so tay ----------
    world = load_world(folder) or {
        "version": 1, "title": b.title, "url": b.url,
        "model": cfg.get("model", ""), "created": time.time(),
        "chapters_total": len(chapters), "mode": b.mode, "sections": {},
    }
    world["chapters_total"] = len(chapters)
    for khoa, huong_dan in _MUC_SO_TAY.items():
        if b.cancel.is_set():
            return
        b.stage = khoa
        b.done, b.total = 0, 1
        if world["sections"].get(khoa):     # da viet o lan chay truoc
            b.done = 1
            continue
        b.message = "Đang viết: " + dict(GIAI_DOAN)[khoa] + "…"
        # model kieu "suy nghi" (qwen, deepseek-r1) co the dot het max_tokens vao
        # phan nghi ma chua viet duoc gi -> thu lai voi tran token cao hon han
        van = ""
        for tran in (None, int(cfg.get("max_tokens") or 3000) + 4000):
            van = ai.chat(cfg, [
                {"role": "system",
                 "content": f'Bạn là quản trò (GM) đang soạn "sổ tay thế giới" cho truyện '
                            f'"{b.title}" để về sau dẫn dắt người chơi nhập vai vào thế giới đó. '
                            f'Chỉ dựa vào ghi chú được cung cấp, viết tiếng Việt thuần '
                            f'(không chèn chữ Hán), trình bày markdown gọn gàng dễ tra cứu.'},
                {"role": "user",
                 "content": "GHI CHÚ TOÀN TRUYỆN:\n" + _cap(tong_hop, NGAN_SACH_GOP)
                            + "\n\n---\nYÊU CẦU:\n" + huong_dan},
            ], temperature=0.5, max_tokens=tran)
            if van:
                break
            if b.cancel.is_set():
                return
        if not van:
            raise ai.AiError('AI trả về rỗng ở mục "%s" (model suy nghĩ quá dài mà chưa '
                             'kịp viết). Thử lại, hoặc đổi model khác.'
                             % dict(GIAI_DOAN)[khoa])
        world["sections"][khoa] = van
        world["updated"] = time.time()
        _save_json(world_path(folder), world)
        b.done = 1


def _chia_ngan_sach(items: list[str]) -> list[list[str]]:
    """Chia day ghi chu thanh cac nhom, moi nhom vua ngan sach mot lan goi AI."""
    nhoms, hien_tai, dem = [], [], 0
    for it in items:
        if hien_tai and dem + len(it) > NGAN_SACH_GOP:
            nhoms.append(hien_tai)
            hien_tai, dem = [], 0
        hien_tai.append(it)
        dem += len(it)
    if hien_tai:
        nhoms.append(hien_tai)
    return nhoms


# ================================================================ PHIEN CHOI
def _pdir(folder) -> Path:
    return _wdir(folder) / "phien"


def list_sessions(folder) -> list[dict]:
    out = []
    for f in sorted(_pdir(folder).glob("*.json")) if _pdir(folder).is_dir() else []:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            out.append({"id": d["id"], "ten": d["nhan_vat"].get("ten", "?"),
                        "so_chuong": len(d.get("chuong", [])),
                        "vi_tri": (d.get("trang_thai") or {}).get("vi_tri", ""),
                        "updated": d.get("updated", 0)})
        except Exception:
            continue
    out.sort(key=lambda x: -x["updated"])
    return out


def load_session(folder, sid: str) -> dict | None:
    p = _pdir(folder) / (re.sub(r"[^0-9a-f]", "", sid) + ".json")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_session(folder, s: dict) -> None:
    s["updated"] = time.time()
    _save_json(_pdir(folder) / (s["id"] + ".json"), s)


def delete_session(folder, sid: str) -> bool:
    p = _pdir(folder) / (re.sub(r"[^0-9a-f]", "", sid) + ".json")
    try:
        p.unlink()
        return True
    except OSError:
        return False


# quy tac van phong "chong mui AI" — dung chung cho ca viet chuong lan trau chuot
_VAN_PHONG = """VĂN PHONG (để văn đọc như người viết, không như máy):
- Thể hiện cảm xúc qua hành động, cử chỉ, lời thoại, chi tiết cảm quan (mùi, âm thanh, xúc giác, ánh sáng) — CẤM tuyên bố thẳng cảm xúc kiểu "anh cảm thấy buồn", "cô rất tức giận".
- Nhịp câu đa dạng: câu ngắn xen câu dài; cảnh căng thẳng thì câu và đoạn phải ngắn lại.
- Đối thoại tự nhiên: có ngắt lời, nói lửng, ẩn ý sau câu chữ; không ai diễn thuyết cả đoạn dài; xưng hô đúng bối cảnh và thứ bậc trong truyện.
- Động từ mạnh thay cho trạng từ; tránh "một cách + tính từ"; không rải "đột nhiên", "tuy nhiên", "bỗng" dày đặc.
- Mỗi cảnh tối đa 1–2 hình ảnh ẩn dụ đắt giá; cấm chuỗi mỹ từ nối tiếp nhau.
- CẤM các câu tổng kết sáo rỗng: "Và như thế…", "Trong khoảnh khắc đó, anh hiểu rằng…", "một cảm giác khó tả", "không thể diễn tả bằng lời", "như một lời nhắc nhở rằng…", "mọi thứ sẽ không bao giờ như trước nữa".
- Cấm mở chương bằng tả thời tiết chung chung; cấm kết chương bằng bài học/đúc kết/triết lý.
- Nhân vật hành động và nói trước, suy nghĩ sau; độc thoại nội tâm ngắn gọn, đúng giọng nhân vật.
- Chi tiết cụ thể thắng tính từ chung chung: thay "món ăn ngon", "cảnh tượng kỳ lạ" bằng chi tiết thật khiến người đọc tự cảm thấy."""

_LUAT_GM = """Bạn là quản trò (GM) của thế giới truyện "{ten}". Người chơi đã nhập vai một nhân vật MỚI sống trong thế giới này. Nhiệm vụ của bạn: viết tiếp câu chuyện của HỌ như một chương tiểu thuyết thực thụ.

LUẬT SẮT (không bao giờ vi phạm):
0. Viết bằng TIẾNG VIỆT THUẦN — tuyệt đối không chèn chữ Hán hay từ tiếng nước ngoài vào văn.
1. Văn phong bám sát truyện gốc (xem Tổng quan). Ngôi thứ ba theo góc nhìn nhân vật người chơi. Mỗi chương DÀI 1000–2000 chữ — tức khoảng 14–24 đoạn văn, đủ chỗ triển khai cảnh cho ra cảnh, KHÔNG viết tóm lược cho xong. Kết thúc ở điểm tự nhiên, KHÔNG hỏi lại người chơi trong thân chương.
2. QUY LUẬT & GIỚI HẠN là bất khả xâm phạm: sức mạnh, cấp bậc, tốc độ tiến bộ, quy tắc cái chết/hồi sinh đều theo sổ tay. Người chơi KHÔNG mạnh lên phi lý; hành động vượt khả năng thì thất bại hoặc trả giá thật.
3. NHÂN QUẢ: người chơi mô tả HÀNH ĐỘNG, KẾT QUẢ do thế giới quyết. Mỗi hành động gây hậu quả trực tiếp VÀ lâu dài — ân oán, danh tiếng, thương tật, lời hứa, món nợ đều được thế giới ghi nhớ và quay lại đòi.
4. THẾ GIỚI TỰ VẬN HÀNH: nơi người chơi không có mặt, NPC, phe phái, kinh tế, chiến sự vẫn tiến triển theo dòng thời gian nguyên tác cộng với các BIẾN ĐỘNG đã ghi. Mỗi chương hé ra một chút thế giới đang chuyển động (tin đồn, giá cả, đoàn người, tin chiến sự…).
5. NPC sống đúng tính cách, mục tiêu, ký ức của họ; NPC mới sinh ra theo "quy tắc sinh NPC" và cũng có mục tiêu riêng. Nhân vật nguyên tác vẫn sống cuộc đời của họ trừ khi BIẾN ĐỘNG ghi khác. Được phép sinh ra NPC, địa điểm nhỏ, nhiệm vụ, tin đồn mới — miễn hợp lore.
6. SỰ KIỆN rơi theo bảng độ hiếm của khu vực: đa số [Phổ biến], thỉnh thoảng [Không thường], hiếm khi [Hiếm], [Cực hiếm] phải thật xứng đáng, [Độc nhất] chỉ MỘT lần duy nhất — bậc [Hiếm] trở lên phải đúng ĐIỀU KIỆN KÍCH HOẠT.
7. BA TẦNG THÔNG TIN: phân biệt điều chỉ GM biết / điều nhân vật trong truyện biết / điều chưa ai biết. BÍ MẬT chỉ hé lộ đúng điều kiện; nhân vật người chơi không tự nhiên biết điều họ không thể biết.
8. NHẤT QUÁN: trước khi thêm bất kỳ chi tiết mới nào, đối chiếu sổ tay + BIẾN ĐỘNG đã ghi — không mâu thuẫn địa lý, lịch sử, sức mạnh, quan hệ; không bao giờ reset một thay đổi đã xảy ra.
9. ƯU TIÊN khi xung đột: lore nguyên tác + biến động đã ghi → quy luật thế giới → logic NPC → mong muốn người chơi → yếu tố ngẫu nhiên.
10. BẤT NGỜ & BIẾN SỐ: mỗi chương cài ít nhất một chi tiết sống động không đoán trước (không cần lớn — một người lạ, một tin đồn, một thay đổi nhỏ của thế giới).

{van_phong}

SỔ TAY THẾ GIỚI (nguyên tác):
{so_tay}"""

_KHUON_TRA_LOI = """
Trả lời đúng trình tự sau (giữ đúng các dòng phân cách):
===DAN_CANH===
3–5 gạch đầu dòng phác cảnh trước khi viết: chuyện gì xảy ra, cảm xúc chủ đạo, nhịp độ, chi tiết đắt sẽ cài (phần nháp — máy sẽ bỏ, người chơi không thấy)
===CHUONG===
thân chương — CHỈ văn truyện, không tiêu đề, không bình luận. Viết đủ dài: 1000–2000 chữ (14–24 đoạn), triển khai trọn cảnh chứ đừng tóm tắt.
===TRANG_THAI===
rồi một khối JSON (không giải thích gì thêm):
{"tieu_de": "tên chương ngắn gọn", "vi_tri": "đang ở đâu", "thoi_gian": "thời gian trong truyện", "suc_manh": "cấp bậc/tình trạng tu vi hiện tại", "the_trang": "sức khoẻ, trạng thái", "vat_pham": ["các vật đáng chú ý đang có"], "quan_he": ["tên NPC — quan hệ hiện tại"], "bien_dong_the_gioi": ["thay đổi LỚN với thế giới/NPC do chương này gây ra (ai chết, quan hệ phe phái đổi, bí mật bị lộ…); [] nếu không có"], "manh_moi_moi": ["việc còn treo mà thế giới sẽ đòi lại sau: lời hứa, món nợ, hẹn ước, mối đe doạ, phục bút vừa cài; [] nếu không có"], "manh_moi_xong": ["các mối treo cũ đã được giải quyết trong chương này; [] nếu không có"], "goi_y": ["3 hành động gợi ý tiếp theo, ngắn gọn"]}"""


# (khoa, tieu de trong prompt, ngan sach ky tu khi choi) — cong lai ~37KB de con
# cho cho tom tat + 2 chuong gan nhat trong cua so ngu canh cua model
_SO_TAY_CHOI = (
    ("tong_quan", "TỔNG QUAN", 3500),
    ("lich_su", "LỊCH SỬ", 2500),
    ("ban_do", "BẢN ĐỒ & KHOẢNG CÁCH", 3000),
    ("the_gioi_song", "THỜI GIAN & MÔI TRƯỜNG", 3000),
    ("nhan_vat", "NHÂN VẬT", 4500),
    ("phe_phai", "PHE PHÁI & CHÍNH TRỊ", 3500),
    ("van_hoa", "VĂN HOÁ & KINH TẾ", 2500),
    ("quy_luat", "QUY LUẬT THẾ GIỚI", 3500),
    ("gioi_han", "GIỚI HẠN & SỨC MẠNH", 3500),
    ("khu_vuc", "KHU VỰC & SỰ KIỆN", 5000),
    ("bi_an", "BÍ MẬT (tuyệt mật, chỉ GM biết)", 3500),
)


def _so_tay_cho_prompt(world: dict) -> str:
    s = world.get("sections", {})
    return "\n\n".join(f"■ {ten}\n{_cap(s[khoa], muc)}"
                       for khoa, ten, muc in _SO_TAY_CHOI if s.get(khoa))


def _ta_nhan_vat(nv: dict) -> str:
    dong = [f"Tên: {nv.get('ten', '?')}"]
    for khoa, ten in (("gioi_tinh", "Giới tính"), ("tuoi", "Tuổi"),
                      ("xuat_than", "Xuất thân"), ("tinh_cach", "Tính cách"),
                      ("muc_tieu", "Mục tiêu"), ("khoi_dau", "Điểm khởi đầu mong muốn")):
        if (nv.get(khoa) or "").strip():
            dong.append(f"{ten}: {nv[khoa].strip()}")
    return "\n".join(dong)


def _ta_trang_thai(tt: dict) -> str:
    dong = []
    for khoa, ten in (("vi_tri", "Vị trí"), ("thoi_gian", "Thời gian"),
                      ("suc_manh", "Sức mạnh"), ("the_trang", "Thể trạng")):
        if (tt.get(khoa) or "").strip():
            dong.append(f"{ten}: {tt[khoa]}")
    if tt.get("vat_pham"):
        dong.append("Vật phẩm: " + ", ".join(map(str, tt["vat_pham"][:20])))
    if tt.get("quan_he"):
        dong.append("Quan hệ: " + "; ".join(map(str, tt["quan_he"][:20])))
    return "\n".join(dong) or "(chưa có gì đáng chú ý)"


def create_session(folder: str, title: str, nhan_vat: dict) -> dict:
    """Tao phien moi + nho AI viet chuong mo dau. Goi dong bo (co the lau)."""
    world = load_world(folder)
    if not world:
        raise ai.AiError("Truyện này chưa khởi tạo thế giới.")
    cfg = store.load_settings()["ai"]
    s = {
        "id": uuid.uuid4().hex[:12],
        "created": time.time(), "updated": time.time(),
        "nhan_vat": nhan_vat,
        "trang_thai": {"vi_tri": "", "thoi_gian": "", "suc_manh": "",
                       "the_trang": "", "vat_pham": [], "quan_he": []},
        "bien_dong": [],   # thay doi cua the gioi so voi nguyen tac, khong bao gio reset
        "manh_moi": [],    # viec con treo: loi hua, mon no, hen uoc, phuc but
        "tom_tat": "",
        "chuong": [],
    }
    yeu_cau = ("NHÂN VẬT NGƯỜI CHƠI (mới toanh, vừa bước vào thế giới):\n"
               + _ta_nhan_vat(nhan_vat)
               + "\n\nHãy viết CHƯƠNG MỞ ĐẦU: giới thiệu nhân vật vào thế giới một cách "
                 "tự nhiên đúng xuất thân và điểm khởi đầu họ muốn, cho thấy khung cảnh, "
                 "không khí và một tình huống mở đầu vừa sức."
               + _KHUON_TRA_LOI)
    _sinh_chuong(cfg, world, s, yeu_cau, hanh_dong="(mở đầu)")
    _save_session(folder, s)
    return s


def act(folder: str, sid: str, hanh_dong: str) -> dict:
    """Nguoi choi hanh dong -> AI viet chuong tiep theo. Tra ve phien da cap nhat."""
    world = load_world(folder)
    if not world:
        raise ai.AiError("Truyện này chưa khởi tạo thế giới.")
    s = load_session(folder, sid)
    if not s:
        raise ai.AiError("Không tìm thấy phiên chơi này.")
    cfg = store.load_settings()["ai"]

    hanh_dong = (hanh_dong or "").strip()
    if not hanh_dong:
        raise ai.AiError("Chưa nhập hành động.")

    ganNhat = s["chuong"][-SO_CHUONG_NHO:]
    phan = ["NHÂN VẬT NGƯỜI CHƠI:\n" + _ta_nhan_vat(s["nhan_vat"]),
            "TRẠNG THÁI HIỆN TẠI:\n" + _ta_trang_thai(s.get("trang_thai") or {})]
    if s.get("bien_dong"):
        phan.append("BIẾN ĐỘNG THẾ GIỚI ĐÃ XẢY RA (ghi đè nguyên tác, KHÔNG bao giờ "
                    "reset hay mâu thuẫn với những điều này):\n"
                    + _cap("\n".join("- " + b for b in s["bien_dong"]), 5000))
    if s.get("manh_moi"):
        phan.append("VIỆC CÒN TREO (lời hứa, món nợ, hẹn ước, đe doạ, phục bút chưa "
                    "trả — thế giới nhớ và sẽ đòi lại đúng lúc; đừng quên, cũng đừng "
                    "vội giải quyết hết trong một chương):\n"
                    + _cap("\n".join("- " + m for m in s["manh_moi"]), 3000))
    if s.get("tom_tat"):
        phan.append("TÓM TẮT HÀNH TRÌNH TRƯỚC ĐÓ:\n" + _cap(s["tom_tat"], 6000))
    for c in ganNhat:
        phan.append(f"CHƯƠNG GẦN NHẤT — {c['title']}:\n" + _cap(c["text"], 7000))
    phan.append("HÀNH ĐỘNG CỦA NGƯỜI CHƠI:\n" + hanh_dong[:1000]
                + "\n\nHãy viết chương tiếp theo dựa trên hành động này (kết quả theo "
                  "logic thế giới, không nuông chiều)." + _KHUON_TRA_LOI)
    _sinh_chuong(cfg, world, s, "\n\n".join(phan), hanh_dong=hanh_dong)

    # gop bot vao tom tat cho prompt khoi phinh ra mai
    if len(s["chuong"]) % NHIP_TOM_TAT == 0:
        try:
            _cap_nhat_tom_tat(cfg, s)
        except ai.AiError:
            pass                            # tom tat hong 1 lan khong sao, lan sau bu
    # so bien dong dai qua thi nho AI don lai (giu du thong tin, gon dong)
    if len(s.get("bien_dong") or []) > 50:
        try:
            _don_bien_dong(cfg, s)
        except ai.AiError:
            pass
    _save_session(folder, s)
    return s


def _don_bien_dong(cfg: dict, s: dict):
    text = ai.chat(cfg, [{"role": "user", "content":
        "Đây là sổ ghi các thay đổi của một thế giới truyện so với nguyên tác, theo "
        "thứ tự thời gian. Hãy GỘP các dòng trùng/liên quan lại còn tối đa 25 dòng, "
        "GIỮ NGUYÊN mọi sự thật quan trọng (ai chết, phe nào đổi chủ, bí mật nào lộ, "
        "ân oán nào còn), giữ thứ tự thời gian, mỗi dòng một gạch đầu dòng. "
        "Không bình luận.\n\n" + "\n".join("- " + b for b in s["bien_dong"])}],
        temperature=0.2, max_tokens=2500)
    dong = [d.lstrip("-• ").strip() for d in text.split("\n") if d.strip()]
    if dong:
        s["bien_dong"] = dong[:30]


def _ket_thuc_tron(than: str) -> bool:
    """Chuong co ve viet xong (khong bi cat giua cau vi het token)."""
    return bool(re.search(r'[.!?…"”’\』」*)\]]\s*$', than.strip()))


def _sinh_chuong(cfg: dict, world: dict, s: dict, yeu_cau: str, hanh_dong: str):
    # Mot chuong 500-900 chu + phan model "suy nghi" + khoi JSON de vuot qua
    # max_tokens mac dinh -> bi cat giua cau, mat luon khoi trang thai. Cho rieng
    # viec sinh chuong tran cao han, va viet cut thi thu lai cao hon nua.
    mac_dinh = int(cfg.get("max_tokens") or 3000)
    than, trang_thai = "", None
    # chuong 1000-2000 tu tieng Viet ~ 2600-4500 token, cong khoi JSON
    for tran in (mac_dinh + 5000, mac_dinh + 12000):
        text = ai.chat(cfg, [
            {"role": "system", "content": _LUAT_GM.format(
                ten=world.get("title", ""), van_phong=_VAN_PHONG,
                so_tay=_so_tay_cho_prompt(world))},
            {"role": "user", "content": yeu_cau},
        ], max_tokens=tran)
        than, trang_thai = _tach_tra_loi(text)
        if than and trang_thai is not None:
            break
        if than and _ket_thuc_tron(than):
            break                       # chuong tron ven, chi thieu JSON -> hoi bu sau
    if not than:
        raise ai.AiError("AI trả về nội dung rỗng (model suy nghĩ quá dài mà chưa kịp "
                         "viết) — thử lại hoặc đổi model.")
    if cfg.get("trau_chuot"):
        # luot bien tap: viet lai cho van "nguoi" hon, giu nguyen su kien
        try:
            than = _trau_chuot(cfg, world, than)
        except ai.AiError:
            pass                        # trau chuot hong thi giu ban nhap, khong chan choi
    if trang_thai is None:
        # chuong ok nhung model quen/hong khoi JSON -> hoi bu mot cau ngan
        try:
            trang_thai = _hoi_bu_trang_thai(cfg, s, than)
        except ai.AiError:
            trang_thai = None           # chiu, giu trang thai cu, khong co goi y

    idx = len(s["chuong"]) + 1
    tieu_de = (trang_thai or {}).get("tieu_de") or f"Chương {idx}"
    goi_y = [str(g)[:120] for g in ((trang_thai or {}).get("goi_y") or [])[:4]]
    s["chuong"].append({"index": idx, "title": f"Chương {idx}: {tieu_de}"
                        if not str(tieu_de).lower().startswith("chương") else str(tieu_de),
                        "text": than, "action": hanh_dong,
                        "goi_y": goi_y, "created": time.time()})
    if trang_thai:
        tt = s.get("trang_thai") or {}
        for khoa in ("vi_tri", "thoi_gian", "suc_manh", "the_trang"):
            if str(trang_thai.get(khoa) or "").strip():
                tt[khoa] = str(trang_thai[khoa]).strip()[:200]
        for khoa in ("vat_pham", "quan_he"):
            if isinstance(trang_thai.get(khoa), list):
                tt[khoa] = [_chuoi_muc(x) for x in trang_thai[khoa][:25]]
        s["trang_thai"] = tt
        # ghi so bien dong: thay doi cua the gioi so voi nguyen tac (ai chet,
        # phe phai doi chu...) — giu vinh vien de the gioi khong bi reset
        bd = trang_thai.get("bien_dong_the_gioi")
        if isinstance(bd, list):
            so = s.setdefault("bien_dong", [])
            for x in bd:
                dong = _chuoi_muc(x)
                if dong.strip():
                    so.append(f"[Chương {idx}] {dong}")
        _cap_nhat_manh_moi(s, trang_thai, idx)


def _cap_nhat_manh_moi(s: dict, trang_thai: dict, idx: int):
    """So manh moi con treo: loi hua, mon no, hen uoc, phuc but chua tra.

    Giu de moi chuong sau con biet the gioi dang no nguoi choi nhung gi (va
    nguoc lai) — day la cho de nhan qua "lau dai" co dau ma quay lai.
    """
    treo = s.setdefault("manh_moi", [])
    for x in (trang_thai.get("manh_moi_moi") or []):
        dong = _chuoi_muc(x)
        if dong.strip() and not any(dong[:40].lower() in t.lower() for t in treo):
            treo.append(f"[Chương {idx}] {dong}")
    for x in (trang_thai.get("manh_moi_xong") or []):
        xong = _chuoi_muc(x).lower()
        if not xong.strip():
            continue
        # bo cac moi treo da duoc giai quyet (khop long theo tu khoa dau)
        s["manh_moi"] = [t for t in s["manh_moi"]
                         if not _giong_nhau(t, xong)]
        treo = s["manh_moi"]
    s["manh_moi"] = treo[-25:]          # chi giu 25 moi gan nhat cho prompt gon


# tu noi/tro tieng Viet — bo di truoc khi so, khong thi cau nao cung "giong" cau nao
_TU_RONG = {
    "và", "của", "cho", "với", "một", "các", "những", "này", "đó", "là", "có",
    "không", "đã", "sẽ", "bị", "được", "trong", "ngoài", "khi", "thì", "mà",
    "rằng", "chương", "về", "đến", "từ", "vào", "cũng", "rất", "nữa", "hay",
    "hoặc", "cùng", "đang", "vẫn", "còn", "lại", "ra", "nên", "để", "vì",
}


def _tu_khoa(text: str) -> set[str]:
    """Tu co nghia trong mot dong mo ta (tieng Viet toan tu don am nen giu ca tu 2 chu)."""
    return {w for w in re.findall(r"\w+", (text or "").lower())
            if len(w) >= 2 and not w.isdigit() and w not in _TU_RONG}


def _giong_nhau(treo: str, xong: str) -> bool:
    """Hai mo ta co noi ve cung mot moi treo khong (khop tho theo tu chung)."""
    a, b = _tu_khoa(treo), _tu_khoa(xong)
    if not a or not b:
        return False
    chung = len(a & b)
    return chung >= 2 and chung / min(len(a), len(b)) >= 0.5


def _chuoi_muc(x) -> str:
    """Muc trong danh sach vat pham/quan he: model co khi tra object thay vi chuoi."""
    if isinstance(x, dict):
        return " — ".join(str(v).strip() for v in x.values() if str(v).strip())[:120]
    return str(x)[:120]


def _hoi_bu_trang_thai(cfg: dict, s: dict, than: str) -> dict | None:
    """Chuong da co nhung thieu khoi JSON -> hoi rieng mot cau ngan de lay."""
    tt_cu = _ta_trang_thai(s.get("trang_thai") or {})
    text = ai.chat(cfg, [{"role": "user", "content":
        "Dưới đây là một chương truyện và trạng thái nhân vật TRƯỚC chương đó.\n\n"
        "TRẠNG THÁI TRƯỚC:\n" + tt_cu + "\n\nCHƯƠNG:\n" + _cap(than, 6000)
        + '\n\nChỉ trả về đúng MỘT khối JSON (không giải thích): '
          '{"tieu_de": "tên chương ngắn gọn", "vi_tri": "...", "thoi_gian": "...", '
          '"suc_manh": "...", "the_trang": "...", "vat_pham": [...], '
          '"quan_he": ["tên — quan hệ"], '
          '"bien_dong_the_gioi": ["thay đổi lớn với thế giới/NPC trong chương, [] nếu không"], '
          '"manh_moi_moi": ["việc còn treo mới: lời hứa, món nợ, hẹn ước, đe doạ, phục bút"], '
          '"manh_moi_xong": ["mối treo cũ đã giải quyết trong chương này"], '
          '"goi_y": ["3 hành động gợi ý tiếp theo cho người chơi, ngắn gọn"]}'}],
        temperature=0.2, max_tokens=1200)
    kq = ai.extract_json(text)
    return kq if isinstance(kq, dict) else None


def _trau_chuot(cfg: dict, world: dict, than: str) -> str:
    """Luot bien tap vien: nang chat van, giu nguyen 100% noi dung su kien."""
    tong_quan = (world.get("sections") or {}).get("tong_quan", "")
    text = ai.chat(cfg, [
        {"role": "system", "content":
            "Bạn là biên tập viên văn học lão luyện. Nhiệm vụ: VIẾT LẠI chương truyện "
            "dưới đây cho văn mượt và giống người viết hơn.\n"
            "BẮT BUỘC GIỮ NGUYÊN: mọi sự kiện, thông tin, chi tiết, ý lời thoại, thứ tự "
            "cảnh, ngôi kể. TUYỆT ĐỐI KHÔNG rút gọn, không lược bớt đoạn, không tóm tắt "
            "— bản viết lại phải dài BẰNG HOẶC HƠN bản gốc.\n"
            "Chỉ nâng chất lượng câu chữ theo nguyên tắc:\n" + _VAN_PHONG
            + "\nViết TIẾNG VIỆT THUẦN, không chèn chữ Hán. Bám văn phong truyện gốc:\n"
            + _cap(tong_quan, 2000)
            + "\nChỉ trả về thân chương đã viết lại — không tiêu đề, không bình luận."},
        {"role": "user", "content": than},
    ], temperature=0.7, max_tokens=int(cfg.get("max_tokens") or 3000) + 6000)
    # bien tap vien lo tay tom tat mat noi dung (hoac phinh ra vo ly) -> giu ban nhap
    if not text or len(text) < len(than) * 0.85 or len(text) > len(than) * 1.8:
        return than
    return text


def _tach_tra_loi(text: str):
    """Tach than chuong va khoi JSON trang thai (neu AI viet dung khuon)."""
    # bo phan dan canh nhap (giua ===DAN_CANH=== va ===CHUONG===) neu model viet
    m_ch = re.search(r"={2,}\s*CH[UƯ][OƠ]NG\s*={2,}", text)
    if m_ch and re.search(r"={2,}\s*D[AÀ]N[_\s]*C[AẢ]NH\s*={2,}", text[:m_ch.start()]):
        text = text[m_ch.end():]
    # model tieng Viet hay tu "sua" thanh TRẠNG_THÁI co dau -> chap nhan het
    phan = re.split(r"={2,}\s*TR[AẠ]NG[_\s]*TH[AÁ]I\s*={2,}", text, maxsplit=1)
    than = phan[0].strip()
    trang_thai = ai.extract_json(phan[1]) if len(phan) > 1 else None
    if trang_thai is None and len(phan) == 1:
        # AI quen dong phan cach nhung van co the da viet JSON cuoi bai
        m = re.search(r"\{[^{}]*\"tieu_de\"[\s\S]*\}\s*$", than)
        if m:
            trang_thai = ai.extract_json(m.group(0))
            if trang_thai:
                than = than[:m.start()].strip()
    if not isinstance(trang_thai, dict):
        trang_thai = None
    # bo tieu de "Chương N..." AI hay tu viet lai o dong dau (co the boc ** hoac #)
    than = re.sub(r"^\s*(?:[#*]+\s*)?Chương\s+\d+[^\n]*\n+", "", than, count=1)
    return than, trang_thai


def _cap_nhat_tom_tat(cfg: dict, s: dict):
    moi = s["chuong"][-NHIP_TOM_TAT:]
    noi_dung = ((("TÓM TẮT CŨ:\n" + s["tom_tat"] + "\n\n") if s.get("tom_tat") else "")
                + "CÁC CHƯƠNG MỚI:\n"
                + "\n\n".join(f"{c['title']}\n{_cap(c['text'], 4000)}" for c in moi))
    s["tom_tat"] = ai.chat(cfg, [{"role": "user", "content":
        "Gộp tóm tắt cũ (nếu có) với các chương mới thành MỘT bản tóm tắt hành trình "
        "của nhân vật: sự kiện chính, NPC đã gặp và quan hệ, vật phẩm/cơ duyên, "
        "ân oán còn dang dở. Tiếng Việt, gạch đầu dòng, dưới 500 từ, không bình luận.\n\n"
        + noi_dung}], temperature=0.3, max_tokens=1500)
