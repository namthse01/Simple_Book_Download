"""Goi may chu AI theo chuan OpenAI (chat/completions).

Dung duoc voi Ollama chay tren may (mac dinh, khong can key), hoac bat ky
dich vu nao noi chuan OpenAI: OpenAI, DeepSeek, Groq, Gemini (duong dan
/v1beta/openai cua Google)... chi can doi base_url + api_key + model
trong Cai dat.
"""
from __future__ import annotations

import atexit
import json
import os
import re
import shutil
import subprocess
import time
from urllib.parse import urlparse

import requests


class AiError(RuntimeError):
    """Loi goi AI — chuoi loi da viet de hien thang cho nguoi dung."""


def _base(cfg: dict) -> str:
    b = (cfg.get("base_url") or "").strip().rstrip("/")
    if not b:
        raise AiError("Chưa điền địa chỉ máy chủ AI trong Cài đặt.")
    return b


def _headers(cfg: dict) -> dict:
    h = {"Content-Type": "application/json"}
    if (cfg.get("api_key") or "").strip():
        h["Authorization"] = "Bearer " + cfg["api_key"].strip()
    return h


def list_models(cfg: dict) -> list[str]:
    """Danh sach model may chu dang co (de nguoi dung chon cho dung ten)."""
    _goc_ollama(cfg)        # tien the: Ollama local chua chay thi tu bat luon
    try:
        r = requests.get(_base(cfg) + "/models", headers=_headers(cfg), timeout=15)
        r.raise_for_status()
        data = r.json()
    except requests.ConnectionError:
        raise AiError("Không kết nối được máy chủ AI. Nếu dùng Ollama, kiểm tra "
                      "Ollama đã chạy chưa (lệnh: ollama serve).")
    except Exception as exc:
        raise AiError(f"Không đọc được danh sách model: {exc}")
    items = data.get("data") or []
    return [m.get("id", "") for m in items if m.get("id")]


def chat(cfg: dict, messages: list[dict], temperature: float | None = None,
         max_tokens: int | None = None) -> str:
    """Mot luot hoi AI, tra ve chuoi tra loi (da bo phan <think> neu co).

    Model kieu "suy nghi" (qwen, deepseek-r1...) co the dot sach max_tokens vao
    khoi <think> ma chua viet duoc chu nao -> cau tra loi rong voi
    finish_reason="length". Gap vay thi tu nang tran token len roi hoi lai,
    toi da 3 lan, de nguoi dung khong phai biet gi ve chuyen nay.
    """
    tran = int(max_tokens or cfg.get("max_tokens") or 3000)
    tot_nhat = ""
    for _ in range(3):
        text, finish = _mot_luot(cfg, messages, temperature, tran)
        if len(text) > len(tot_nhat):
            tot_nhat = text
        if finish != "length":
            return text or tot_nhat
        tran = tran * 2 + 2000          # bi cat -> nang tran roi viet lai
    return tot_nhat


# base_url nao la Ollama (de goi API rieng cua no); (goc, model) nao khong nhan think
_ollama: dict[str, bool] = {}
_khong_think: set[tuple[str, str]] = set()
# tien trinh "ollama serve" do CHINH APP bat len (de con tat luc dong app).
# Ollama nguoi dung tu chay thi khong dung toi -> khong bao gio tat nham.
_ollama_cua_ta = None
_job_ollama = None   # handle job object (giu song suot doi app)


def _goc_ollama(cfg: dict) -> str | None:
    """Neu may chu la Ollama thi tra ve dia chi goc (khong co /v1), khong thi None.

    Ollama tren chinh may nay ma chua chay thi TU BAT giup nguoi dung —
    khoi phai nho mo "ollama serve" truoc khi choi.
    """
    b = _base(cfg)
    if not b.endswith("/v1"):
        return None
    goc = b[:-3].rstrip("/")
    if _ollama.get(goc):                    # da tung thay song -> tin luon
        return goc
    if _ping(goc) or _tu_bat_ollama(goc):
        _ollama[goc] = True
        return goc
    return None


def _ping(goc: str) -> bool:
    try:
        return requests.get(goc + "/api/version", timeout=3).status_code == 200
    except Exception:
        return False


def _tu_bat_ollama(goc: str) -> bool:
    """Bat "ollama serve" chay nen (chi lam voi dia chi localhost)."""
    host = urlparse(goc).hostname or ""
    if host not in ("127.0.0.1", "localhost", "::1"):
        return False
    exe = shutil.which("ollama")
    if not exe:
        duong = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
        exe = duong if os.path.isfile(duong) else None
    if not exe:
        return False
    try:
        # DETACHED_PROCESS | CREATE_NO_WINDOW: song doc lap, khong hien cua so den
        co = 0x00000008 | 0x08000000 if os.name == "nt" else 0
        global _ollama_cua_ta
        _ollama_cua_ta = subprocess.Popen(
            [exe, "serve"], stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=co)
        # luoi an toan: app thoat kieu bat thuong thi van don duoc
        atexit.register(dong_ollama)
        _buoc_chet_theo_app(_ollama_cua_ta)
    except OSError:
        return False
    for _ in range(30):                     # cho toi da ~15 giay cho no day
        time.sleep(0.5)
        if _ping(goc):
            return True
    return False


def _buoc_chet_theo_app(tien_trinh) -> None:
    """Windows: nhot Ollama vao "job object" cua app de no chet theo app.

    dong_ollama() chi chay khi app thoat tu te. Neu bi tat cung (Task Manager,
    dong cua so lenh, app crash) thi khong code nao chay kip, va Ollama se o lai
    an RAM. Job object la co che cua chinh Windows: the nao app chet, moi tien
    trinh trong job cung bi don theo — khong phu thuoc app kip lam gi hay khong.
    """
    if os.name != "nt":
        return
    global _job_ollama
    try:
        import ctypes
        from ctypes import wintypes

        class GIOI_HAN(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                        ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t),
                        ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class DEM_IO(ctypes.Structure):
            _fields_ = [(t, ctypes.c_uint64) for t in
                        ("ReadOperationCount", "WriteOperationCount",
                         "OtherOperationCount", "ReadTransferCount",
                         "WriteTransferCount", "OtherTransferCount")]

        class GIOI_HAN_MO_RONG(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", GIOI_HAN),
                        ("IoInfo", DEM_IO),
                        ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        job = k32.CreateJobObjectW(None, None)
        if not job:
            return
        tt = GIOI_HAN_MO_RONG()
        tt.BasicLimitInformation.LimitFlags = 0x2000   # KILL_ON_JOB_CLOSE
        if not k32.SetInformationJobObject(job, 9, ctypes.byref(tt), ctypes.sizeof(tt)):
            return
        if k32.AssignProcessToJobObject(job, int(tien_trinh._handle)):
            _job_ollama = job          # phai giu handle song, dong handle = giet job
    except Exception:
        pass                           # khong lap duoc thi thoi, van con dong_ollama()


def dong_ollama() -> bool:
    """Tat Ollama neu chinh app da bat no len (goi luc dong app).

    Ollama giu model trong RAM/VRAM hang GB, ma tien trinh chay tach roi nen
    dong app xong no van song. Chi tat dung tien trinh minh de ra: Ollama do
    nguoi dung tu mo (hoac app khac dung) phai duoc yen.
    """
    global _ollama_cua_ta
    tt, _ollama_cua_ta = _ollama_cua_ta, None
    if tt is None or tt.poll() is not None:
        return False
    try:
        tt.terminate()
        tt.wait(timeout=8)
    except Exception:
        try:
            tt.kill()
        except Exception:
            return False
    _ollama.clear()          # lan sau hoi lai tu dau xem no con song khong
    return True


def _mot_luot(cfg: dict, messages: list[dict], temperature: float | None,
              max_tokens: int) -> tuple[str, str]:
    """Mot lan goi that su. Tra ve (noi dung, finish_reason)."""
    model = (cfg.get("model") or "").strip()
    if not model:
        raise AiError("Chưa chọn model AI trong Cài đặt (mục Nhập vai AI).")
    nhiet = cfg.get("temperature", 0.8) if temperature is None else temperature
    goc = _goc_ollama(cfg)

    if goc:
        # API rieng cua Ollama de TAT che do "suy nghi" (think): model kieu qwen
        # nghi ca vạn chu truoc khi viet, dot sach max_tokens ma noi dung van rong.
        # (Duong /v1 chuan OpenAI cua Ollama khong co cach tat.)
        body = {"model": model, "messages": messages, "stream": False,
                "options": {"temperature": nhiet, "num_predict": int(max_tokens),
                            # cua so ngu canh: mac dinh cua Ollama thuong qua ngan,
                            # se cat mat so tay the gioi trong prompt dai
                            "num_ctx": int(cfg.get("num_ctx") or 24576)}}
        if (goc, model) not in _khong_think:
            body["think"] = False
        r = _post(cfg, goc + "/api/chat", body)
        if r.status_code >= 400:
            loi = _loi_cua(r)
            if "think" in loi.lower() and (goc, model) not in _khong_think:
                _khong_think.add((goc, model))      # model khong ho tro tham so nay
                return _mot_luot(cfg, messages, temperature, max_tokens)
            raise AiError(f"Máy chủ AI báo lỗi {r.status_code}: {loi}")
        try:
            data = r.json()
            text = (data.get("message") or {}).get("content") or ""
            finish = data.get("done_reason") or ""
        except Exception:
            raise AiError("Ollama trả về dữ liệu không đúng dạng.")
    else:
        body = {"model": model, "messages": messages, "temperature": nhiet,
                "max_tokens": int(max_tokens), "stream": False}
        r = _post(cfg, _base(cfg) + "/chat/completions", body)
        if r.status_code >= 400:
            raise AiError(f"Máy chủ AI báo lỗi {r.status_code}: {_loi_cua(r)}")
        try:
            chon = r.json()["choices"][0]
            text = chon["message"]["content"] or ""
            finish = chon.get("finish_reason") or ""
        except Exception:
            raise AiError("Máy chủ AI trả về dữ liệu không đúng dạng chuẩn OpenAI.")

    # phong khi model van tu chen doan suy nghi <think>...</think> vao noi dung
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    text = re.sub(r"<think>.*$", "", text, flags=re.S)   # khoi think bi cat, khong dong
    return text.strip(), finish


def _post(cfg: dict, url: str, body: dict):
    try:
        return requests.post(url, headers=_headers(cfg), json=body,
                             timeout=int(cfg.get("timeout") or 600))
    except requests.ConnectionError:
        raise AiError("Không kết nối được máy chủ AI. Nếu dùng Ollama, kiểm tra "
                      "Ollama đã chạy chưa (lệnh: ollama serve).")
    except requests.Timeout:
        raise AiError("Máy chủ AI trả lời quá lâu (quá thời gian chờ). Model lớn "
                      "chạy máy yếu hay bị vậy — thử model nhỏ hơn hoặc tăng "
                      "thời gian chờ trong Cài đặt.")


def _loi_cua(r) -> str:
    try:
        loi = r.json().get("error")
        if isinstance(loi, dict):
            loi = loi.get("message", "")
        return str(loi or "")[:300]
    except Exception:
        return r.text[:300]


def extract_json(text: str):
    """Nhat khoi JSON dau tien trong cau tra loi cua AI (co the boc ```json).

    AI nho hay viet them loi dan truoc/sau JSON nen khong parse thang duoc;
    tra ve None neu chiu khong tim thay — nguoi goi tu xoay xo tiep.
    """
    if not text:
        return None
    m = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # tim { ... } can bang ngoac dau tien
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            c = text[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except Exception:
                        break
        start = text.find("{", start + 1)
    return None
