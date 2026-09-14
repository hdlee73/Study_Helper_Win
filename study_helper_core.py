import asyncio
import json
import re
import subprocess
import threading
import time
import shutil
import os
import tempfile
from pathlib import Path
from typing import List, Tuple
from concurrent.futures import ThreadPoolExecutor

import customtkinter as ctk
import requests
import tkinter as tk
from tkinter import filedialog, messagebox
import multiprocessing

import sys
import queue
import logging
import html
from functools import lru_cache

RESOURCE_DIR = Path(__file__).resolve().parent
APP_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "StudyHelper"
APP_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = APP_DIR / "config.json"
logging.basicConfig(filename=APP_DIR / "study_helper.log", level=logging.WARNING,
                    format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")

DEFAULT_CONFIG = {
    "last_mp3_dir": str(Path.home() / "Downloads"),
    "last_excel_path": str(Path.home() / "Documents" / "audio_cards.xlsx"),
    "last_tts_excel_path": str(Path.home() / "Documents" / "audio_cards.xlsx"),
    "last_tts_output_dir": str(Path.home() / "Downloads"),
    "last_anki_deck": "",
    "anki_note_type": "English",
    "tts_voice_en": "en-US-AndrewMultilingualNeural",
    "tts_voice_ko": "ko-KR-SunHiNeural",
    "whisper_model": "base",
    "whisper_beam_size": 1,
    "tts_concurrency": 4,
    "anki_wait_seconds": 45
}

VOICE_MAP = {
    "미국식": {"남성": "en-US-GuyNeural", "여성": "en-US-AriaNeural"},
    "영국식": {"남성": "en-GB-RyanNeural", "여성": "en-GB-SoniaNeural"},
    "호주식": {"남성": "en-AU-WilliamNeural", "여성": "en-AU-NatashaNeural"}
}

CONFIG = None
WHISPER_MODEL = None
PANDAS = None
ANKI_SESSION = requests.Session()

def pandas_module():
    global PANDAS
    if PANDAS is None:
        import pandas
        PANDAS = pandas
    return PANDAS

def get_ffmpeg_path():
    for root in (RESOURCE_DIR, Path(sys.executable).parent):
        candidate = root / "ffmpeg" / "ffmpeg.exe"
        if candidate.is_file(): return str(candidate)
    return shutil.which("ffmpeg")

def load_config():
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            cfg = DEFAULT_CONFIG.copy()
            cfg.update(data)
            return cfg
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    atomic_write(CONFIG_PATH, lambda p: p.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"))

def get_whisper_model():
    global WHISPER_MODEL
    if WHISPER_MODEL is None:
        from faster_whisper import WhisperModel
        WHISPER_MODEL = WhisperModel(CONFIG.get("whisper_model", "base"),
            device="cpu", compute_type="int8", cpu_threads=min(4, os.cpu_count() or 2),
            download_root=str(APP_DIR / "models"))
    return WHISPER_MODEL

def transcribe_audio(path):
    segments, info = get_whisper_model().transcribe(
        str(Path(path).resolve()),
        beam_size=max(1, int(CONFIG.get("whisper_beam_size", 1))),
        vad_filter=True,
        condition_on_previous_text=False,
    )
    texts = [s.text.strip() for s in segments if s.text.strip()]
    if not texts: raise RuntimeError("음성 인식 결과가 비어 있습니다.")
    return {"text": " ".join(texts), "segments": [{"text": s} for s in texts]}

def atomic_write(target, writer):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".study_", suffix=target.suffix, dir=target.parent)
    os.close(fd)
    try:
        writer(Path(tmp))
        os.replace(tmp, target)
    finally:
        Path(tmp).unlink(missing_ok=True)

def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', '_', str(name)).strip().rstrip('. ')
    if re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', name, re.I): name = '_' + name
    return name[:150].rstrip('. ') or "audio"

def detect_lang(text: str) -> str:
    if re.search(r'[가-힣]', text):
        return "ko"
    return "en"

def split_sentences(segments: List[str]) -> List[str]:
    out = []
    for seg in segments:
        text = re.sub(r'\s+', ' ', seg).strip()
        if not text: continue
        parts = re.split(r'(?<=[.!?。！？])\s+', text)
        for p in parts:
            p = p.strip(' -')
            if len(p) >= 2: out.append(p)
    return out

@lru_cache(maxsize=2048)
def translate_pair(sentence: str, lang: str) -> Tuple[str, str]:
    from deep_translator import GoogleTranslator
    if lang == "ko":
        en = GoogleTranslator(source='ko', target='en').translate(sentence)
        return sentence, en
    ko = GoogleTranslator(source='en', target='ko').translate(sentence)
    return ko, sentence

def dedupe_df(df):
    df = df.fillna("")
    for _ in range(3 - len(df.columns)): df[len(df.columns)] = ""
    df = df.iloc[:, :3].copy()
    df.columns = [0, 1, 2]
    df[0] = df[0].astype(str).str.strip()
    df[1] = df[1].astype(str).str.strip()
    df[2] = df[2].astype(str).str.strip()
    return df.drop_duplicates(subset=[0, 1, 2], keep='first').reset_index(drop=True)

def fetch_title(url: str) -> str:
    import yt_dlp
    # 쿠키를 가져올 브라우저 지정 (예: 'chrome', 'edge', 'firefox' 등)
    ydl_opts = {
        'quiet': True, 
        'no_warnings': True,
        **cookie_options()
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get("title") or "audio"

def download_youtube_mp3(url: str, output_dir: str, file_name: str):
    import yt_dlp
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    final_name = sanitize_filename(file_name)
    outtmpl = str(output_dir_path / f"{final_name}.%(ext)s")
    
    ffmpeg_loc = require_ffmpeg()
    ydl_opts = {
        'format': 'bestaudio/best', 'outtmpl': outtmpl, 'noplaylist': True,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        'quiet': True, 'no_warnings': True,
        **cookie_options()  # 이 부분을 변경해 주세요.
    }
    if ffmpeg_loc:
        ydl_opts['ffmpeg_location'] = ffmpeg_loc

    if (output_dir_path / f"{final_name}.mp3").exists():
        raise FileExistsError(f"이미 존재하는 MP3입니다: {final_name}. 다른 이름을 사용하세요.")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    return str(output_dir_path / f"{final_name}.mp3")

def transcribe_mp3_to_rows(mp3_path: str):
    result = transcribe_audio(mp3_path)

    segments = result.get("segments", []) if isinstance(result, dict) else []
    texts = [seg.get("text", "") for seg in segments if isinstance(seg, dict) and seg.get("text", "").strip()]
    if not texts:
        full_text = result.get("text", "") if isinstance(result, dict) else ""
        if isinstance(full_text, str) and full_text.strip(): texts = [full_text]

    if not texts: raise RuntimeError("음성 인식 결과가 비어 있습니다.")

    sentences = split_sentences(texts)
    jobs = [(sent, detect_lang(sent)) for sent in sentences]
    worker_count = min(4, len(jobs))
    with ThreadPoolExecutor(max_workers=max(1, worker_count)) as pool:
        pairs = list(pool.map(lambda job: translate_pair(*job), jobs))
    rows = []
    stem = Path(mp3_path).stem
    for (sent, _), (front, back) in zip(jobs, pairs):
        rows.append([front, back, stem])
    return rows

def save_rows_to_excel(rows, excel_path: str):
    pd = pandas_module()
    target = Path(excel_path)
    new_df = pd.DataFrame(rows)
    old_df = pd.read_excel(target, header=None) if target.exists() else pd.DataFrame(columns=[0,1,2])
    combined = dedupe_df(pd.concat([old_df, new_df], ignore_index=True))
    atomic_write(target, lambda p: combined.to_excel(p, header=False, index=False, engine="openpyxl"))
    return str(target), len(combined)

def anki_request(action, request_timeout=5, **params):
    payload = {"action": action, "version": 6, "params": params}
    r = ANKI_SESSION.post("http://127.0.0.1:8765", json=payload, timeout=request_timeout)
    r.raise_for_status()
    data = r.json()
    if data.get("error"):
        raise RuntimeError(data.get("error"))
    return data.get("result")

def find_anki_executable():
    configured = str(CONFIG.get("anki_executable", "")).strip()
    candidates = [
        configured,
        shutil.which("anki") or "",
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Anki/anki.exe"),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Anki/anki.exe"),
        "C:/Anki/Anki.exe",
        "C:/Program Files/Anki/anki.exe",
        "C:/Program Files (x86)/Anki/anki.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    return None

def import_excel_to_anki(excel_path: str, custom_deck_name: str = ""):
    pd = pandas_module()
    df = dedupe_df(pd.read_excel(excel_path, header=None))
    try:
        anki_request("version", request_timeout=2)
    except requests.RequestException as first_error:
        executable = find_anki_executable()
        if executable is None:
            raise RuntimeError(
                "Anki가 실행 중이 아니며 실행 파일도 찾지 못했습니다. Anki를 직접 연 뒤 다시 시도하세요. "
                "사용자 지정 설치라면 config.json의 anki_executable에 전체 경로를 적을 수 있습니다."
            ) from first_error
        subprocess.Popen([str(executable)], close_fds=True)
        deadline = time.monotonic() + max(10, int(CONFIG.get("anki_wait_seconds", 45)))
        last_error = first_error
        while time.monotonic() < deadline:
            time.sleep(0.75)
            try:
                anki_request("version", request_timeout=2)
                break
            except requests.RequestException as error:
                last_error = error
        else:
            raise RuntimeError(
                f"Anki는 {executable}에서 열었지만 AnkiConnect(127.0.0.1:8765)가 응답하지 않습니다. "
                "Anki의 도구 → 추가 기능에서 AnkiConnect가 활성화됐는지 확인하고 Anki를 재시작하세요."
            ) from last_error
    model = CONFIG["anki_note_type"]
    if model not in anki_request("modelNames"):
        raise RuntimeError(f'Anki에 "{model}" 노트 유형을 만들고 Front, Back, Example 필드를 추가하세요.')
    fields = anki_request("modelFieldNames", modelName=model)
    if not {"Front", "Back", "Example"}.issubset(fields):
        raise RuntimeError("노트 유형에 Front, Back, Example 필드가 모두 필요합니다.")
    deck = custom_deck_name.strip() or Path(excel_path).stem
    anki_request("createDeck", deck=deck)
    def quoted(value):
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'
    ids = anki_request("findNotes", query=f"deck:{quoted(deck)} note:{quoted(model)}")
    existing = set()
    for start in range(0, len(ids), 100):
        for item in anki_request("notesInfo", notes=ids[start:start+100]):
            existing.add(html.unescape(str(item["fields"]["Front"]["value"])).strip())
    notes, skipped, invalid, seen = [], 0, 0, set()
    for front, back, example in df.itertuples(index=False, name=None):
        if not front or not back:
            invalid += 1
            continue
        if front in existing or front in seen:
            skipped += 1
            continue
        seen.add(front)
        notes.append({"deckName":deck, "modelName":model,
            "fields": {"Front":html.escape(front), "Back":html.escape(back), "Example":html.escape(example)},
            "options":{"allowDuplicate":False, "duplicateScope":"deck"}, "tags":["audio_workflow"]})
    added = 0
    for start in range(0, len(notes), 100):
        result = anki_request("addNotes", notes=notes[start:start+100]) or []
        added += sum(x is not None for x in result)
    if added != len(notes):
        raise RuntimeError(f"일부 카드만 추가되었습니다: {added}/{len(notes)}. Anki에서 확인 후 다시 실행하세요.")
    return deck, added, skipped, len(df)

async def save_tts_line(text: str, voice: str, output_path: str):
    import edge_tts
    for attempt in range(3):
        try:
            await asyncio.wait_for(edge_tts.Communicate(text=text, voice=voice).save(output_path), timeout=90)
            return
        except Exception:
            Path(output_path).unlink(missing_ok=True)
            if attempt == 2: raise
            await asyncio.sleep(2 ** attempt)

def make_silence_mp3(seconds: float, output_path: str):
    run_ffmpeg(["-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", str(seconds),
                "-ar", "24000", "-ac", "1", "-b:a", "48k", output_path])

def concat_mp3_files(input_files: List[str], output_file: str):
    target = Path(output_file)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="study_", dir=target.parent) as tmp:
        list_file = Path(tmp) / "parts.txt"
        entries = []
        for part in input_files:
            escaped = Path(part).resolve().as_posix().replace("'", "'\\''")
            entries.append(f"file '{escaped}'")
        list_file.write_text("\n".join(entries), encoding="utf-8")
        try:
            atomic_write(target, lambda p: run_ffmpeg([
                "-f", "concat", "-safe", "0", "-i", str(list_file),
                "-vn", "-ar", "24000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "128k", str(p)
            ]))
        except RuntimeError:
            logging.warning("Fast MP3 concat failed; using compatibility path", exc_info=True)
            concat_mp3_files_compat(input_files, target)

def concat_mp3_files_compat(input_files, target):
    with tempfile.TemporaryDirectory(prefix="study_pcm_", dir=Path(target).parent) as tmp:
        pcm = Path(tmp) / "all.pcm"
        with pcm.open("wb") as stream:
            for part in input_files:
                command = [require_ffmpeg(), "-nostdin", "-v", "error", "-i", str(part),
                           "-f", "s16le", "-ar", "24000", "-ac", "1", "pipe:1"]
                result = subprocess.run(command, stdout=stream, stderr=subprocess.PIPE,
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                if result.returncode:
                    raise RuntimeError(result.stderr.decode("utf-8", "replace")[-2000:])
        atomic_write(target, lambda p: run_ffmpeg([
            "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", str(pcm),
            "-c:a", "libmp3lame", "-b:a", "128k", str(p)
        ]))

def require_ffmpeg():
    path = get_ffmpeg_path()
    if not path: raise RuntimeError("FFmpeg가 없습니다. ffmpeg 폴더에 ffmpeg.exe와 ffprobe.exe를 넣으세요.")
    return path

def run_ffmpeg(args):
    result = subprocess.run([require_ffmpeg(), "-nostdin", "-y", "-v", "error", *args],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode: raise RuntimeError(result.stderr.decode('utf-8', 'replace')[-2000:])

def cookie_options():
    path = APP_DIR / "cookies.txt"
    return {"cookiefile": str(path)} if path.is_file() else {}

def speech_pdf(text, target):
    from fpdf import FPDF
    font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "malgun.ttf"
    if not font.is_file(): raise RuntimeError("한글 PDF에 필요한 Windows 맑은 고딕 글꼴이 없습니다.")
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font("Korean", fname=str(font))
    pdf.add_page()
    pdf.set_font("Korean", size=12)
    pdf.multi_cell(0, 7, text)
    atomic_write(target, lambda p: pdf.output(str(p)))

def calculate_pause_seconds(text: str) -> float:
    return max(2.5, min(7.0, len(text.split()) * 0.4 + 1.5))

def excel_to_mp3_files(excel_path: str, output_dir: str, split_limit: int = 500):
    pd = pandas_module()
    if split_limit < 1: raise ValueError("split_limit must be positive")
    df = dedupe_df(pd.read_excel(excel_path, header=None))
    rows = [tuple(row) for row in df.itertuples(index=False, name=None) if row[0]]
    if not rows: raise RuntimeError("읽을 수 있는 데이터가 없습니다.")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    outputs = []
    for start in range(0, len(rows), split_limit):
        plan = []
        for front, back, _ in rows[start:start+split_limit]:
            plan.append((front, CONFIG["tts_voice_ko"] if detect_lang(front)=="ko" else CONFIG["tts_voice_en"]))
            if detect_lang(front)=="ko" and back and "_" not in back:
                plan.extend([(calculate_pause_seconds(back), None), (back, CONFIG["tts_voice_en"])])
            plan.append((0.8, None))
        suffix = "" if len(rows)<=split_limit else f"_{start+1:03d}-{min(start+split_limit,len(rows)):03d}"
        target = output / (sanitize_filename(Path(excel_path).stem) + suffix + ".mp3")
        render_audio_plan(plan, target)
        outputs.append(str(target))
    return outputs

def render_audio_plan(plan, target):
    require_ffmpeg()
    with tempfile.TemporaryDirectory(prefix="study_tts_") as tmp:
        parts, cache = [], {}
        unique_jobs = []
        for item, voice in plan:
            key = (item, voice)
            if key not in cache:
                cache[key] = str(Path(tmp) / f"{len(cache):06d}.mp3")
                unique_jobs.append((key, cache[key]))
            parts.append(cache[key])
        async def generate():
            semaphore = asyncio.Semaphore(max(1, min(6, int(CONFIG.get("tts_concurrency", 4)))))
            async def create_one(key, path):
                item, voice = key
                async with semaphore:
                    if voice is None:
                        await asyncio.to_thread(make_silence_mp3, float(item), path)
                    else:
                        await save_tts_line(str(item), voice, path)
            await asyncio.gather(*(create_one(key, path) for key, path in unique_jobs))
        asyncio.run(generate())
        if not parts: raise RuntimeError("유효한 문장이 없습니다.")
        concat_mp3_files(parts, str(target))

def cleanup_temp_files():
    # TemporaryDirectory owns and removes only this application's job files.
    pass

class ModernButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        super().__init__(master, corner_radius=16, height=46, font=ctk.CTkFont(size=14, weight="bold"),
                         fg_color="#0f766e", hover_color="#115e59", text_color="#ffffff", border_width=0, **kwargs)

class SecondaryButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        super().__init__(master, corner_radius=16, height=42, font=ctk.CTkFont(size=13, weight="bold"),
                         fg_color="#eef6f5", hover_color="#d9efec", text_color="#0f766e", border_width=1, border_color="#cfe5e2", **kwargs)

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Study Helper Unified")
        
        # --- 윈도우 창 좌측 상단 아이콘 적용 ---
        try:
            self.iconbitmap(str(RESOURCE_DIR / "icon.ico"))
        except:
            pass
        # --------------------------------------
        
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        global CONFIG
        CONFIG = load_config()
        self.config_data = CONFIG
        self.last_paste_target = None
        self.after(0, self._set_fullscreen)
        self._build_ui()
        self.show_panel("youtube")
        self.install_paste_bindings()
        self._events = queue.Queue()
        self._busy = False
        self.after(80, self._drain_events)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _set_fullscreen(self):
        try:
            self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
            self.state('zoomed')
        except: self.geometry("1660x1020")

    def _build_ui(self):
        self.configure(fg_color="#eaf1ef")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color="#f7fbfa")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(2, weight=1) 

        brand = ctk.CTkFrame(self.sidebar, corner_radius=28, fg_color="#ffffff", border_width=1, border_color="#dde9e6")
        brand.grid(row=0, column=0, padx=18, pady=(24, 14), sticky="ew")
        ctk.CTkLabel(brand, text="Study Helper", font=ctk.CTkFont(size=28, weight="bold"), text_color="#102a2a").pack(anchor="w", padx=18, pady=(16, 4))
        ctk.CTkLabel(brand, text="Windows 통합 오디오 워크플로우", font=ctk.CTkFont(size=12), text_color="#6b7d7b").pack(anchor="w", padx=18, pady=(0, 16))

        self.nav_scroll = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.nav_scroll.grid(row=1, column=0, rowspan=2, sticky="nsew", padx=10, pady=0)

        self.nav_buttons = {}
        self._nav_btn("YouTube → MP3", "youtube")
        self._nav_btn("MP3 → Excel (번역/분리)", "excel_trans")
        self._nav_btn("MP3 → Excel (단순 STT)", "excel_raw")
        self._nav_btn("MP3 → PDF (연설문)", "pdf")
        self._nav_btn("Excel → MP3 (한/영 교차)", "tts_bilingual")
        self._nav_btn("Excel → MP3 (3회 반복)", "tts_3times")
        self._nav_btn("Excel → MP3 (단일 선택)", "tts_single")
        self._nav_btn("Excel → Anki", "anki")

        self.main = ctk.CTkFrame(self, corner_radius=0, fg_color="#eaf1ef")
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_rowconfigure(1, weight=1)
        self.main.grid_columnconfigure(0, weight=1)

        self.header = ctk.CTkFrame(self.main, height=94, corner_radius=30, fg_color="#ffffff", border_width=1, border_color="#dde9e6")
        self.header.grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 10))
        self.header.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(self.header, text="", font=ctk.CTkFont(size=26, weight="bold"), text_color="#102a2a")
        self.title_label.grid(row=0, column=0, padx=24, pady=(18, 2), sticky="w")
        self.desc_label = ctk.CTkLabel(self.header, text="Study1 & Study2 통합 유틸리티", font=ctk.CTkFont(size=13), text_color="#6b7d7b")
        self.desc_label.grid(row=1, column=0, padx=24, pady=(0, 18), sticky="w")
        self.status_badge = ctk.CTkLabel(self.header, text="준비", corner_radius=999, fg_color="#ecfdf5", text_color="#0f766e", font=ctk.CTkFont(size=13, weight="bold"), padx=16, pady=8)
        self.status_badge.grid(row=0, column=1, rowspan=2, padx=22, pady=18, sticky="e")

        self.body = ctk.CTkScrollableFrame(self.main, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew", padx=22, pady=(0, 20))
        self.body.grid_columnconfigure(0, weight=1)

        self.paste_widgets = []
        self.panel_builders = {
            "youtube": self._youtube_panel,
            "excel_trans": self._excel_panel_trans,
            "excel_raw": self._excel_panel_raw,
            "pdf": self._pdf_panel,
            "tts_bilingual": self._tts_panel_bilingual,
            "tts_3times": self._tts_panel_3times,
            "tts_single": self._tts_panel_single,
            "anki": self._anki_panel,
        }
        self.panels = {}

    def _nav_btn(self, text, panel):
        btn = ctk.CTkButton(self.nav_scroll, text=text, command=lambda p=panel: self.show_panel(p),
                            corner_radius=18, height=44, anchor="w", fg_color="#f7fbfa", hover_color="#ebf5f3",
                            text_color="#102a2a", font=ctk.CTkFont(size=14, weight="bold"))
        btn.pack(fill="x", pady=2)
        self.nav_buttons[panel] = btn

    def _panel_card(self, title, desc):
        frame = ctk.CTkFrame(self.body, corner_radius=32, fg_color="#ffffff", border_width=1, border_color="#dde9e6")
        ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=22, weight="bold"), text_color="#102a2a").pack(anchor="w", padx=28, pady=(24, 6))
        ctk.CTkLabel(frame, text=desc, justify="left", wraplength=1180, text_color="#6b7d7b", font=ctk.CTkFont(size=14)).pack(anchor="w", padx=28, pady=(0, 18))
        return frame

    def section_label(self, parent, text): return ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=14, weight="bold"), text_color="#102a2a")
    def input_box(self, parent): return ctk.CTkEntry(parent, height=46, corner_radius=14, border_color="#cfe0dc", fg_color="#f9fcfb", text_color="#102a2a")
    def text_box(self, parent, height=220): return ctk.CTkTextbox(parent, height=height, corner_radius=18, border_width=1, border_color="#cfe0dc", fg_color="#f9fcfb", text_color="#102a2a")

    def show_panel(self, name):
        titles = {
            "youtube": "YouTube 링크를 MP3로 저장", "excel_trans": "MP3를 Excel 카드로 변환 (번역/분리)",
            "excel_raw": "MP3를 Excel로 변환 (단순 STT)", 
            "pdf": "MP3를 PDF 문서로 변환 (연설문)", "tts_bilingual": "Excel을 Edge TTS MP3로 저장 (한/영 교차)",
            "tts_3times": "Excel을 MP3로 저장 (3회 반복)", "tts_single": "Excel을 MP3로 저장 (단일 음성)",
            "anki": "Excel을 Anki Deck에 추가"
        }
        self.title_label.configure(text=titles[name])
        if name not in self.panels:
            self.panels[name] = self.panel_builders[name]()
        for key, btn in self.nav_buttons.items():
            btn.configure(fg_color="#dff4ef" if key == name else "transparent", text_color="#0f766e" if key == name else "#102a2a")
        for panel in self.panels.values(): panel.grid_forget()
        self.panels[name].grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))

    def set_status(self, text, mode="normal"):
        def _update():
            self.status_badge.configure(text=text)
            if mode == "error": self.status_badge.configure(fg_color="#fef2f2", text_color="#b91c1c")
            elif mode == "success": self.status_badge.configure(fg_color="#ecfdf5", text_color="#0f766e")
            else: self.status_badge.configure(fg_color="#ecfdf5", text_color="#0f766e")
        self.post_ui(_update)

    def post_ui(self, callback):
        self._events.put(callback)

    def _drain_events(self):
        for _ in range(100):
            try: callback = self._events.get_nowait()
            except queue.Empty: break
            try: callback()
            except Exception: logging.exception("UI callback failed")
        self.after(80, self._drain_events)

    def _close(self):
        if self._busy:
            messagebox.showinfo("작업 중", "파일 보호를 위해 작업이 끝난 뒤 종료해 주세요.")
            return
        self.destroy()

    def run_in_thread(self, fn):
        if self._busy:
            messagebox.showinfo("작업 중", "현재 작업이 끝난 뒤 실행해 주세요.")
            return
        self._busy = True
        def wrapped():
            try: fn()
            except Exception:
                logging.exception("Worker failed")
                self.set_status("오류", "error")
            finally: self.post_ui(lambda: setattr(self, "_busy", False))
        threading.Thread(target=wrapped, daemon=True).start()
    def is_text_widget(self, w): return hasattr(w, "insert")

    def install_paste_bindings(self):
        self.bind_all("<Button-2>", self.show_context_menu, add="+")
        self.bind_all("<Button-3>", self.show_context_menu, add="+")

    def bind_paste_target(self, widget):
        self.paste_widgets.append(widget)
        def remember(_event=None): self.last_paste_target = widget
        widget.bind("<FocusIn>", remember, add="+")
        widget.bind("<Button-1>", remember, add="+")
        for key in ["<Control-v>", "<Command-v>", "<<Paste>>"]: widget.bind(key, self.handle_paste, add="+")
        widget.bind("<Button-2>", self.show_context_menu, add="+"); widget.bind("<Button-3>", self.show_context_menu, add="+")

    def handle_paste(self, event=None):
        widget = self.focus_get() if self.is_text_widget(self.focus_get()) else self.last_paste_target
        try: text = self.clipboard_get()
        except: return "break"
        if widget and self.is_text_widget(widget):
            try: widget.focus_force(); widget.insert("insert", text); self.last_paste_target = widget
            except: pass
        return "break"

    def show_context_menu(self, event):
        widget = event.widget
        if widget not in self.paste_widgets or not self.is_text_widget(widget): return
        self.last_paste_target = widget
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="붙여넣기", command=lambda: self.paste_button_action(widget))
        menu.tk_popup(event.x_root, event.y_root)

    def paste_button_action(self, widget):
        try: text = self.clipboard_get()
        except: return messagebox.showerror("오류", "클립보드 내용을 읽지 못했습니다.")
        try: widget.focus_force(); widget.insert("insert", text); self.last_paste_target = widget
        except: pass

    def pick_file_for(self, entry, filetypes):
        path = filedialog.askopenfilename(filetypes=filetypes)
        if path: entry.delete(0, 'end'); entry.insert(0, path)

    def pick_dir_for(self, entry):
        path = filedialog.askdirectory(initialdir=entry.get() or str(Path.home()))
        if path: entry.delete(0, 'end'); entry.insert(0, path)

    def get_filename(self, source_path, custom_name, ext):
        name = sanitize_filename(custom_name.strip() or Path(source_path).stem)
        return name if name.lower().endswith(ext) else name + ext

    def _youtube_panel(self):
        frame = self._panel_card("YouTube → MP3", "유튜브 링크를 입력하면 음성만 추출해 MP3로 저장합니다.")
        form = ctk.CTkFrame(frame, fg_color="transparent"); form.pack(fill="both", expand=True, padx=28, pady=(0, 28))
        form.grid_columnconfigure(0, weight=3); form.grid_columnconfigure(1, weight=2)
        self.section_label(form, "YouTube 링크").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.section_label(form, "저장 파일명").grid(row=0, column=1, sticky="w", padx=(16, 0), pady=(0, 8))
        self.url_box = self.text_box(form, 200); self.url_box.grid(row=1, column=0, sticky="nsew")
        self.name_box = self.text_box(form, 200); self.name_box.grid(row=1, column=1, sticky="nsew", padx=(16, 0))
        self.bind_paste_target(self.url_box); self.bind_paste_target(self.name_box)
        self.section_label(form, "저장 폴더").grid(row=3, column=0, sticky="w", pady=(16, 8))
        self.output_dir_entry = self.input_box(form); self.output_dir_entry.insert(0, self.config_data["last_mp3_dir"]); self.output_dir_entry.grid(row=4, column=0, sticky="ew")
        SecondaryButton(form, text="찾기", width=100, command=lambda: self.pick_dir_for(self.output_dir_entry)).grid(row=4, column=1, sticky="w", padx=(16, 0))
        btn_row = ctk.CTkFrame(form, fg_color="transparent"); btn_row.grid(row=5, column=0, columnspan=2, sticky="w", pady=(18, 0))
        ModernButton(btn_row, text="일괄 MP3 저장", width=172, command=self.run_batch_download).pack(side="left")
        return frame

    def _excel_panel_trans(self):
        frame = self._panel_card("MP3 → Excel (번역/분리)", "MP3를 문장 단위로 전사하고, 영어/한국어를 정리해 Excel 파일에 저장합니다.")
        form = ctk.CTkFrame(frame, fg_color="transparent"); form.pack(fill="both", expand=True, padx=28, pady=(0, 28))
        form.grid_columnconfigure(0, weight=3); form.grid_columnconfigure(1, weight=2)
        self.section_label(form, "MP3 파일 경로 (여러 줄 입력)").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.section_label(form, "Excel 파일명").grid(row=0, column=1, sticky="w", padx=(16, 0), pady=(0, 8))
        self.mp3_box = self.text_box(form, 180); self.mp3_box.grid(row=1, column=0, sticky="nsew")
        self.excel_name_box = self.text_box(form, 180); self.excel_name_box.grid(row=1, column=1, sticky="nsew", padx=(16, 0))
        self.bind_paste_target(self.mp3_box); self.bind_paste_target(self.excel_name_box)
        helper_row = ctk.CTkFrame(form, fg_color="transparent"); helper_row.grid(row=2, column=0, columnspan=2, sticky="w", pady=(12, 8))
        SecondaryButton(helper_row, text="여러 MP3 선택", width=134, command=self.pick_multiple_mp3).pack(side="left")
        self.section_label(form, "저장 폴더").grid(row=3, column=0, sticky="w", pady=(16, 8))
        self.excel_dir_entry = self.input_box(form); self.excel_dir_entry.insert(0, str(Path(self.config_data["last_excel_path"]).parent)); self.excel_dir_entry.grid(row=4, column=0, sticky="ew")
        SecondaryButton(form, text="찾기", width=100, command=lambda: self.pick_dir_for(self.excel_dir_entry)).grid(row=4, column=1, sticky="w", padx=(16, 0))
        ModernButton(form, text="Excel로 변환", width=206, command=self.run_multi_transcribe).grid(row=6, column=0, columnspan=2, sticky="w", pady=(18, 0))
        return frame

    def _excel_panel_raw(self):
        frame = self._panel_card("MP3 → Excel (단순 STT)", "음성을 그대로 인식하여 엑셀 A열에 중복 없이 문장 단위로 저장합니다.")
        form = ctk.CTkFrame(frame, fg_color="transparent"); form.pack(fill="both", expand=True, padx=28, pady=(0, 28)); form.grid_columnconfigure(0, weight=1)
        self.section_label(form, "음성 파일 (MP3, WAV)").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.stt_raw_audio = self.input_box(form); self.stt_raw_audio.grid(row=1, column=0, sticky="ew")
        SecondaryButton(form, text="파일 찾기", width=100, command=lambda: self.pick_file_for(self.stt_raw_audio, [("Audio", "*.mp3 *.wav *.m4a")])).grid(row=1, column=1, padx=(12, 0), sticky="w")
        self.section_label(form, "저장 폴더").grid(row=2, column=0, sticky="w", pady=(16, 8))
        self.stt_raw_dir = self.input_box(form); self.stt_raw_dir.insert(0, str(Path.home() / "Documents")); self.stt_raw_dir.grid(row=3, column=0, sticky="ew")
        SecondaryButton(form, text="폴더 변경", width=100, command=lambda: self.pick_dir_for(self.stt_raw_dir)).grid(row=3, column=1, padx=(12, 0), sticky="w")
        self.section_label(form, "저장 파일명 (미입력시 원본파일명)").grid(row=4, column=0, sticky="w", pady=(16, 8))
        self.stt_raw_fn = self.input_box(form); self.stt_raw_fn.grid(row=5, column=0, sticky="ew")
        ModernButton(form, text="음성 추출 및 엑셀 저장", width=200, command=self.run_stt_raw).grid(row=6, column=0, columnspan=2, sticky="w", pady=(24, 0))
        return frame

    def _pdf_panel(self):
        frame = self._panel_card("MP3 → PDF (A4 연설문)", "음성을 인식하여 A4 사이즈의 PDF 문서로 결합해 저장합니다.")
        form = ctk.CTkFrame(frame, fg_color="transparent"); form.pack(fill="both", expand=True, padx=28, pady=(0, 28)); form.grid_columnconfigure(0, weight=1)
        self.section_label(form, "음성 파일").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.stt_pdf_audio = self.input_box(form); self.stt_pdf_audio.grid(row=1, column=0, sticky="ew")
        SecondaryButton(form, text="파일 찾기", width=100, command=lambda: self.pick_file_for(self.stt_pdf_audio, [("Audio", "*.mp3 *.wav *.m4a")])).grid(row=1, column=1, padx=(12, 0), sticky="w")
        self.section_label(form, "저장 폴더").grid(row=2, column=0, sticky="w", pady=(16, 8))
        self.stt_pdf_dir = self.input_box(form); self.stt_pdf_dir.insert(0, str(Path.home() / "Documents")); self.stt_pdf_dir.grid(row=3, column=0, sticky="ew")
        SecondaryButton(form, text="폴더 변경", width=100, command=lambda: self.pick_dir_for(self.stt_pdf_dir)).grid(row=3, column=1, padx=(12, 0), sticky="w")
        self.section_label(form, "저장 파일명 (미입력시 원본파일명)").grid(row=4, column=0, sticky="w", pady=(16, 8))
        self.stt_pdf_fn = self.input_box(form); self.stt_pdf_fn.grid(row=5, column=0, sticky="ew")
        ModernButton(form, text="PDF 문서로 저장", width=200, command=self.run_stt_pdf).grid(row=6, column=0, columnspan=2, sticky="w", pady=(24, 0))
        return frame

    def _tts_panel_bilingual(self):
        frame = self._panel_card("Excel → MP3 (한/영 교차)", "한국어 시작 문장의 경우 지능적으로 공백 시간을 삽입하여 MP3를 생성합니다. (3열 제외)")
        form = ctk.CTkFrame(frame, fg_color="transparent"); form.pack(fill="both", expand=True, padx=28, pady=(0, 28)); form.grid_columnconfigure(0, weight=1)
        self.section_label(form, "Excel 파일").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.tts_excel_entry = self.input_box(form); self.tts_excel_entry.insert(0, self.config_data["last_tts_excel_path"]); self.tts_excel_entry.grid(row=1, column=0, sticky="ew")
        SecondaryButton(form, text="찾기", width=100, command=lambda: self.pick_file_for(self.tts_excel_entry, [("Excel", "*.xlsx")])).grid(row=1, column=1, padx=(12, 0), sticky="w")
        self.section_label(form, "저장 폴더").grid(row=2, column=0, sticky="w", pady=(16, 8))
        self.tts_output_entry = self.input_box(form); self.tts_output_entry.insert(0, self.config_data["last_tts_output_dir"]); self.tts_output_entry.grid(row=3, column=0, sticky="ew")
        SecondaryButton(form, text="찾기", width=100, command=lambda: self.pick_dir_for(self.tts_output_entry)).grid(row=3, column=1, padx=(12, 0), sticky="w")
        ModernButton(form, text="Excel을 MP3로 저장", width=196, command=self.run_excel_tts_bilingual).grid(row=5, column=0, columnspan=2, sticky="w", pady=(24, 0))
        return frame

    def _tts_panel_3times(self):
        frame = self._panel_card("Excel → MP3 (3회 반복)", "엑셀 A열의 문장들을 다국적 발음(미/영/호주)으로 3회 반복하여 생성합니다.")
        form = ctk.CTkFrame(frame, fg_color="transparent"); form.pack(fill="both", expand=True, padx=28, pady=(0, 28)); form.grid_columnconfigure(0, weight=1)
        self.section_label(form, "Excel 파일").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.tts3_excel = self.input_box(form); self.tts3_excel.grid(row=1, column=0, sticky="ew")
        SecondaryButton(form, text="파일 찾기", width=100, command=lambda: self.pick_file_for(self.tts3_excel, [("Excel", "*.xlsx")])).grid(row=1, column=1, padx=(12, 0), sticky="w")
        self.section_label(form, "저장 폴더").grid(row=2, column=0, sticky="w", pady=(16, 8))
        self.tts3_dir = self.input_box(form); self.tts3_dir.insert(0, str(Path.home() / "Documents")); self.tts3_dir.grid(row=3, column=0, sticky="ew")
        SecondaryButton(form, text="폴더 변경", width=100, command=lambda: self.pick_dir_for(self.tts3_dir)).grid(row=3, column=1, padx=(12, 0), sticky="w")
        self.section_label(form, "저장 파일명 (미입력시 원본파일명)").grid(row=4, column=0, sticky="w", pady=(16, 8))
        self.tts3_fn = self.input_box(form); self.tts3_fn.grid(row=5, column=0, sticky="ew")
        
        gap_row = ctk.CTkFrame(form, fg_color="transparent"); gap_row.grid(row=6, column=0, sticky="w", pady=(16, 0))
        self.lbl_acc_gap = ctk.CTkLabel(gap_row, text="발음 간 간격: 1초", text_color="#555"); self.lbl_acc_gap.pack(anchor="w")
        self.sld_acc_gap = ctk.CTkSlider(gap_row, from_=1, to=10, number_of_steps=9, width=200, command=lambda v: self.lbl_acc_gap.configure(text=f"발음 간 간격: {int(v)}초")); self.sld_acc_gap.set(1); self.sld_acc_gap.pack(anchor="w", pady=(0, 10))
        self.lbl_sen_gap = ctk.CTkLabel(gap_row, text="문장 간 간격: 3초", text_color="#555"); self.lbl_sen_gap.pack(anchor="w")
        self.sld_sen_gap = ctk.CTkSlider(gap_row, from_=1, to=10, number_of_steps=9, width=200, command=lambda v: self.lbl_sen_gap.configure(text=f"문장 간 간격: {int(v)}초")); self.sld_sen_gap.set(3); self.sld_sen_gap.pack(anchor="w")

        ModernButton(form, text="일괄 MP3 저장", width=200, command=self.run_tts_3times).grid(row=7, column=0, columnspan=2, sticky="w", pady=(24, 0))
        return frame

    def _tts_panel_single(self):
        frame = self._panel_card("Excel → MP3 (단일 선택)", "엑셀 문장들을 원하는 국가의 발음과 성별로 변환합니다.")
        form = ctk.CTkFrame(frame, fg_color="transparent"); form.pack(fill="both", expand=True, padx=28, pady=(0, 28)); form.grid_columnconfigure(0, weight=1)
        
        v_row = ctk.CTkFrame(form, fg_color="transparent"); v_row.grid(row=0, column=0, sticky="w", pady=(0, 16))
        ctk.CTkLabel(v_row, text="발음:", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.cb_acc_s = ctk.CTkOptionMenu(v_row, values=["미국식", "영국식", "호주식"], fg_color="#fff", text_color="#333", button_color="#eef6f5"); self.cb_acc_s.pack(side="left", padx=(8, 20))
        ctk.CTkLabel(v_row, text="성별:", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.cb_gen_s = ctk.CTkOptionMenu(v_row, values=["남성", "여성"], fg_color="#fff", text_color="#333", button_color="#eef6f5"); self.cb_gen_s.pack(side="left", padx=(8, 0))

        self.section_label(form, "Excel 파일").grid(row=1, column=0, sticky="w", pady=(0, 8))
        self.tts1_excel = self.input_box(form); self.tts1_excel.grid(row=2, column=0, sticky="ew")
        SecondaryButton(form, text="파일 찾기", width=100, command=lambda: self.pick_file_for(self.tts1_excel, [("Excel", "*.xlsx")])).grid(row=2, column=1, padx=(12, 0), sticky="w")
        self.section_label(form, "저장 폴더").grid(row=3, column=0, sticky="w", pady=(16, 8))
        self.tts1_dir = self.input_box(form); self.tts1_dir.insert(0, str(Path.home() / "Documents")); self.tts1_dir.grid(row=4, column=0, sticky="ew")
        SecondaryButton(form, text="폴더 변경", width=100, command=lambda: self.pick_dir_for(self.tts1_dir)).grid(row=4, column=1, padx=(12, 0), sticky="w")
        self.section_label(form, "저장 파일명 (미입력시 원본파일명)").grid(row=5, column=0, sticky="w", pady=(16, 8))
        self.tts1_fn = self.input_box(form); self.tts1_fn.grid(row=6, column=0, sticky="ew")

        gap_row = ctk.CTkFrame(form, fg_color="transparent"); gap_row.grid(row=7, column=0, sticky="w", pady=(16, 0))
        self.lbl_sen_gap1 = ctk.CTkLabel(gap_row, text="문장 간 간격: 3초", text_color="#555"); self.lbl_sen_gap1.pack(anchor="w")
        self.sld_sen_gap1 = ctk.CTkSlider(gap_row, from_=1, to=10, number_of_steps=9, width=200, command=lambda v: self.lbl_sen_gap1.configure(text=f"문장 간 간격: {int(v)}초")); self.sld_sen_gap1.set(3); self.sld_sen_gap1.pack(anchor="w")

        ModernButton(form, text="단일 음성 MP3 저장", width=200, command=self.run_tts_single).grid(row=8, column=0, columnspan=2, sticky="w", pady=(24, 0))
        return frame

    def _anki_panel(self):
        frame = self._panel_card("Excel → Anki", "동일한 앞면은 건너뛰고 새 카드를 추가합니다. 기존 카드는 수정하지 않습니다.")
        form = ctk.CTkFrame(frame, fg_color="transparent"); form.pack(fill="both", expand=True, padx=28, pady=(0, 28)); form.grid_columnconfigure(0, weight=1)
        self.section_label(form, "Excel 파일").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.anki_excel_entry = self.input_box(form); self.anki_excel_entry.insert(0, self.config_data["last_excel_path"]); self.anki_excel_entry.grid(row=1, column=0, sticky="ew")
        SecondaryButton(form, text="찾기", width=100, command=lambda: self.pick_file_for(self.anki_excel_entry, [("Excel", "*.xlsx")])).grid(row=1, column=1, padx=(12, 0), sticky="w")
        self.section_label(form, "저장할 덱 이름 (선택)").grid(row=2, column=0, sticky="w", pady=(16, 8))
        self.anki_deck_entry = self.input_box(form); self.anki_deck_entry.insert(0, self.config_data.get("last_anki_deck", "")); self.anki_deck_entry.grid(row=3, column=0, sticky="ew")
        ModernButton(form, text="Anki 카드 추가", width=196, command=self.run_anki_import).grid(row=5, column=0, columnspan=2, sticky="w", pady=(24, 0))
        return frame

    def pick_multiple_mp3(self):
        paths = filedialog.askopenfilenames(filetypes=[("MP3 Files", "*.mp3")])
        if paths:
            self.mp3_box.delete("1.0", "end"); self.mp3_box.insert("1.0", "\n".join(paths))
            existing = self.excel_name_box.get("1.0", "end").strip().splitlines()
            while len(existing) < len(paths): existing.append("")
            self.excel_name_box.delete("1.0", "end"); self.excel_name_box.insert("1.0", "\n".join(existing[:len(paths)]))

    def run_batch_download(self):
        _input_0 = self.url_box.get("1.0", "end")
        _input_1 = self.name_box.get("1.0", "end")
        _input_2 = self.output_dir_entry.get()
        def task():
            try:
                self.set_status("MP3 저장 중...")
                urls = [x.strip() for x in _input_0.splitlines() if x.strip()]
                names = [x.strip() for x in _input_1.splitlines()]
                output_dir = _input_2.strip()
                items = [(url, names[i] if i < len(names) and names[i] else fetch_title(url)) for i, url in enumerate(urls)]
                if not items: raise RuntimeError("유튜브 링크를 입력하세요.")
                saved = [Path(download_youtube_mp3(u, output_dir, n)).name for u, n in items]
                self.config_data["last_mp3_dir"] = output_dir; save_config(self.config_data)
                self.set_status(f"완료: {len(saved)}개", "success")
                self.post_ui(lambda: messagebox.showinfo("완료", "저장 완료\n" + "\n".join(saved[:20])))
            except Exception as e:
                logging.exception("작업 실패")
                self.set_status("오류", "error"); self.post_ui(lambda e=e: messagebox.showerror("오류", str(e)))
        self.run_in_thread(task)

    def run_multi_transcribe(self):
        _input_0 = self.mp3_box.get("1.0", "end")
        _input_1 = self.excel_name_box.get("1.0", "end")
        _input_2 = self.excel_dir_entry.get()
        def task():
            try:
                self.set_status("Excel 변환 중...")
                mp3_paths = [x.strip() for x in _input_0.splitlines() if x.strip()]
                excel_names = [x.strip() for x in _input_1.splitlines()]
                excel_dir = _input_2.strip()
                if not mp3_paths: raise RuntimeError("MP3 파일을 선택하세요.")
                results, errors = [], []
                for i, mp3_path in enumerate(mp3_paths):
                    try:
                        self.set_status(f"변환 중: {Path(mp3_path).name}")
                        excel_name = excel_names[i] if i < len(excel_names) and excel_names[i] else Path(mp3_path).stem
                        if not excel_name.lower().endswith('.xlsx'): excel_name += '.xlsx'
                        excel_path = str(Path(excel_dir) / sanitize_filename(excel_name))
                        _, total_rows = save_rows_to_excel(transcribe_mp3_to_rows(mp3_path), excel_path)
                        results.append(f"✅ {Path(mp3_path).name} ({total_rows}행)")
                    except Exception as e: errors.append(f"❌ {Path(mp3_path).name}: {str(e)}")
                self.set_status(f"완료", "success")
                self.post_ui(lambda: messagebox.showinfo("완료", "[결과]\n" + "\n".join(results) + ("\n[오류]\n" + "\n".join(errors) if errors else "")))
            except Exception as e:
                logging.exception("작업 실패")
                self.set_status("오류", "error"); self.post_ui(lambda e=e: messagebox.showerror("오류", str(e)))
        self.run_in_thread(task)

    def run_stt_raw(self):
        _input_0 = self.stt_raw_audio.get()
        _input_1 = self.stt_raw_dir.get()
        _input_2 = self.stt_raw_fn.get()
        def task():
            try:
                self.set_status("음성 인식 중...")
                mp3_path = _input_0.strip()
                save_path = os.path.join(_input_1.strip(), self.get_filename(mp3_path, _input_2.strip(), ".xlsx"))
                if not mp3_path: raise RuntimeError("음성 파일을 선택해주세요.")
                
                result = transcribe_audio(mp3_path)
                sentences = [segment['text'].strip() for segment in result['segments']]
                unique_sentences = []
                seen = set()
                for s in sentences:
                    if s and s not in seen: seen.add(s); unique_sentences.append(s)
                        
                self.set_status("엑셀 저장 중...")
                pd = pandas_module()
                atomic_write(save_path, lambda p: pd.DataFrame(unique_sentences).to_excel(p, index=False, header=False))
                self.set_status("완료", "success")
                self.post_ui(lambda: messagebox.showinfo("완료", f"저장 완료:\n{save_path}"))
            except Exception as e:
                logging.exception("작업 실패")
                self.set_status("오류", "error"); self.post_ui(lambda e=e: messagebox.showerror("오류", str(e)))
        self.run_in_thread(task)

    def run_stt_pdf(self):
        _input_0 = self.stt_pdf_audio.get()
        _input_1 = self.stt_pdf_dir.get()
        _input_2 = self.stt_pdf_fn.get()
        def task():
            try:
                self.set_status("PDF 생성 중...")
                mp3_path = _input_0.strip()
                if not mp3_path: raise RuntimeError("음성 파일을 선택해주세요.")
                save_path = os.path.join(_input_1.strip(), self.get_filename(mp3_path, _input_2.strip(), ".pdf"))
                
                result = transcribe_audio(mp3_path)
                full_text = result['text'].strip()
                
                speech_pdf(full_text, save_path)

                self.set_status("완료", "success")
                self.post_ui(lambda: messagebox.showinfo("완료", f"저장 완료:\n{save_path}"))
            except Exception as e:
                logging.exception("작업 실패")
                self.set_status("오류", "error"); self.post_ui(lambda e=e: messagebox.showerror("오류", str(e)))
        self.run_in_thread(task)

    def run_excel_tts_bilingual(self):
        _input_0 = self.tts_excel_entry.get()
        _input_1 = self.tts_output_entry.get()
        def task():
            try:
                self.set_status("MP3 생성 중...")
                ex = _input_0.strip(); out = _input_1.strip()
                outputs = excel_to_mp3_files(ex, out, split_limit=500)
                self.config_data["last_tts_excel_path"] = ex; self.config_data["last_tts_output_dir"] = out; save_config(self.config_data)
                self.set_status("완료", "success"); self.post_ui(lambda: messagebox.showinfo("완료", "MP3 생성 완료\n" + "\n".join(outputs[:20])))
            except Exception as e:
                logging.exception("작업 실패")
                self.set_status("오류", "error"); self.post_ui(lambda e=e: messagebox.showerror("오류", str(e)))
        self.run_in_thread(task)

    def run_tts_3times(self):
        self._run_voice_job(True)

    def run_tts_single(self):
        self._run_voice_job(False)

    def _run_voice_job(self, triple):
        # Snapshot all widgets on the Tk main thread.
        ex = (self.tts3_excel if triple else self.tts1_excel).get().strip()
        directory = (self.tts3_dir if triple else self.tts1_dir).get().strip()
        filename = (self.tts3_fn if triple else self.tts1_fn).get().strip()
        gap = int((self.sld_sen_gap if triple else self.sld_sen_gap1).get())
        accent_gap = int(self.sld_acc_gap.get()) if triple else 0
        voices = [VOICE_MAP[a]["남성"] for a in ("미국식", "영국식", "호주식")] if triple else [VOICE_MAP[self.cb_acc_s.get()][self.cb_gen_s.get()]]
        def task():
            try:
                if not ex: raise RuntimeError("Excel 파일을 선택하세요.")
                pd = pandas_module()
                sentences = [str(s).strip() for s in pd.read_excel(ex, header=None).iloc[:,0].dropna() if str(s).strip()]
                plan = []
                for sentence in sentences:
                    for i, voice in enumerate(voices):
                        plan.append((sentence, voice))
                        if i < len(voices)-1: plan.append((accent_gap, None))
                    plan.append((gap, None))
                target = Path(directory) / self.get_filename(ex, filename, ".mp3")
                self.set_status(f"음성 생성 중: {len(sentences)}문장")
                render_audio_plan(plan, target)
                self.set_status("완료", "success")
                self.post_ui(lambda: messagebox.showinfo("완료", f"저장 완료:\n{target}"))
            except Exception as e:
                logging.exception("작업 실패")
                self.set_status("오류", "error")
                self.post_ui(lambda e=e: messagebox.showerror("오류", str(e)))
        self.run_in_thread(task)

    def run_anki_import(self):
        _input_0 = self.anki_excel_entry.get()
        _input_1 = self.anki_deck_entry.get()
        def task():
            try:
                self.set_status("Anki 카드 추가 중...")
                ex, deck = _input_0.strip(), _input_1.strip()
                d_name, added, skipped, total = import_excel_to_anki(ex, deck)
                self.config_data["last_excel_path"] = ex; self.config_data["last_anki_deck"] = deck; save_config(self.config_data)
                self.set_status("완료", "success")
                self.post_ui(lambda: messagebox.showinfo("완료", f"덱: {d_name}\n추가: {added}\n중복: {skipped}\n빈 필드 제외: {total-added-skipped}\n전체: {total}"))
            except Exception as e:
                logging.exception("작업 실패")
                self.set_status("오류", "error"); self.post_ui(lambda e=e: messagebox.showerror("오류", str(e)))
        self.run_in_thread(task)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        from smoke_test import run
        try:
            run(sys.modules[__name__], sys.argv[2])
        except Exception:
            exit_code = 1
        else:
            exit_code = 0
        # Some native GUI/audio libraries keep helper threads alive in a frozen
        # executable. The validation result is already written at this point.
        if getattr(sys, "frozen", False):
            os._exit(exit_code)
        raise SystemExit(exit_code)
    app = App()
    app.mainloop()

