# -*- coding: utf-8 -*-
"""Dong goi nguon VBook -> mobile/nguon-vbook.js cho DCReader.

Doc plugin.zip trong kho Darkrai9x/vbook-extensions (GPL-3), chon cac nguon
da kiem chung chay duoc, chuyen ma tu dong:
  - inline load('x.js')
  - function execute -> async function execute
  - fetch( -> await fetch(   |   sleep( -> await sleep(
roi ghi thanh mot file JS chua ca ma nguon lan metadata.

Chay:  python tools/dong_goi_nguon.py
"""
from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path

KHO = Path(r"D:\Code\vbook-extensions")
RA = Path(__file__).resolve().parent.parent / "mobile" / "nguon-vbook.js"

# toc.js goc cua truyenfull parse JSON tu URL truyen — mirror .live tra HTML
# nen hong. Va lai bang endpoint chapter_option (tra <select> du moi chuong).
TOC_TRUYENFULL = """load('config.js');
function execute(url) {
    let doc = fetch(url).html();
    let id = doc.select("#truyen-id").attr("value");
    if (!id) return Response.error("khong thay id truyen");
    let sel = fetch(BASE_URL + "/ajax.php?type=chapter_option&data=" + id).html();
    let base = url.replace(/\\/+$/, '');
    let list = sel.select("option").map(function (e) {
        return { name: e.text(), url: base + "/" + e.attr("value") + "/" };
    });
    if (!list.length) return Response.error("muc luc rong");
    return Response.success(list);
}
"""

# id -> (ten hien thi, patch script)
# bachngocsach (site thanh trang thong bao) va thichdoctruyen (domain parked)
# da chet ngoai doi — extension goc gio vo dung nen khong dong goi.
# webtruyen (dtruyen->truyencom doi giao dien) va truyenhayvn (redirect ve
# trang chu) cung da loi thoi ngoai doi — bo.
# medoctruyenchu: site doi cau truc JSON (__NEXT_DATA__) -> extension loi thoi, bo.
# truyennet: site khong con tra JSON muc luc nhu extension mong doi — loi thoi, bo.
CHON = {
    "truyenfull": ("TruyenFull", {"src/toc.js": TOC_TRUYENFULL}),
    "isach": ("iSach", {}),
}

NGUY_HIEM = ("Engine.", "WebSocket(", "Graphics.", "Qt.")


def doc_zip(ext_id: str) -> tuple[dict, dict]:
    z = zipfile.ZipFile(KHO / ext_id / "plugin.zip")
    plugin = json.loads(z.read("plugin.json").decode("utf-8"))
    files = {n.split("/")[-1]: z.read(n).decode("utf-8", "replace")
             for n in z.namelist() if n.endswith(".js")}
    return plugin, files


def inline_load(code: str, files: dict, da_vao=None) -> str:
    da_vao = da_vao or set()

    def thay(m):
        ten = m.group(1).split("/")[-1]
        if ten in da_vao:
            return ""
        da_vao.add(ten)
        return "\n" + inline_load(files.get(ten, ""), files, da_vao) + "\n"

    return re.sub(r"load\(\s*['\"]([^'\"]+)['\"]\s*\)\s*;?", thay, code)


def _boc_await(code: str, ten: str) -> str:
    """fetch(...) -> (await fetch(...)) — boc dung dau ngoac dong, de goi chain
    kieu fetch(url).html() thanh (await fetch(url)).html() chu khong phai
    await fetch(url).html() (await ap len ca chain -> goi .html tren Promise)."""
    ra = []
    i = 0
    mau = re.compile(r"\b" + ten + r"\s*\(")
    while True:
        m = mau.search(code, i)
        if not m:
            ra.append(code[i:])
            break
        ra.append(code[i:m.start()])
        # tim ngoac dong khop, bo qua noi dung chuoi
        j = m.end()
        sau = 1
        trong = ""            # ky tu mo chuoi dang o trong, "" = ngoai chuoi
        while j < len(code) and sau:
            c = code[j]
            if trong:
                if c == "\\":
                    j += 1
                elif c == trong:
                    trong = ""
            elif c in "'\"`":
                trong = c
            elif c == "(":
                sau += 1
            elif c == ")":
                sau -= 1
            j += 1
        ra.append("(await " + code[m.start():j] + ")")
        i = j
    return "".join(ra)


def chuyen_async(code: str) -> str:
    code = re.sub(r"\bfunction\s+execute\b", "async function execute", code)
    code = _boc_await(code, "fetch")
    code = _boc_await(code, "sleep")
    code = _boc_await(code, r"Http\s*\.\s*get")     # API doi cu cua VBook
    code = _boc_await(code, r"Http\s*\.\s*post")
    return code


def main():
    ra = []
    for ext_id, (ten, patch) in CHON.items():
        plugin, files = doc_zip(ext_id)
        files.update({k.split("/")[-1]: v for k, v in patch.items()})
        meta = plugin.get("metadata", {})
        script_map = plugin.get("script", {})
        cau_hinh = {k: v.get("default", "") for k, v in (plugin.get("config") or {}).items()}

        scripts = {}
        for vai_tro, fname in script_map.items():
            fname = fname.split("/")[-1]
            if fname not in files:
                continue
            code = chuyen_async(inline_load(files[fname], files))
            for xau in NGUY_HIEM:
                if xau in code:
                    raise SystemExit(f"{ext_id}/{fname} dung API chua ho tro: {xau}")
            scripts[fname] = code
        # cac script phu duoc home/genre tro toi (gen.js, hot.js, tab.js...)
        for fname, raw in files.items():
            if fname not in scripts and fname != "config.js":
                scripts[fname] = chuyen_async(inline_load(raw, files))

        ra.append({
            "id": ext_id,
            "ten": ten,
            "nguon": meta.get("source", ""),
            "regexp": meta.get("regexp", ""),
            "map": {k: v.split("/")[-1] for k, v in script_map.items()},
            "config": cau_hinh,
            "scripts": scripts,
        })
        print(f"  + {ext_id}: {len(scripts)} script")

    js = ("// SINH TU DONG boi tools/dong_goi_nguon.py — dung sua tay.\n"
          "// Ma nguon goc: https://github.com/Darkrai9x/vbook-extensions (GPL-3.0)\n"
          "// DCReader chi dong goi lai cac extension nay de chay qua lop gia lap vbook.js.\n"
          "window.NGUON_VBOOK = " + json.dumps(ra, ensure_ascii=False) + ";\n")
    RA.write_text(js, encoding="utf-8")
    print(f"Da ghi {RA} ({len(js)//1024} KB)")


if __name__ == "__main__":
    main()
