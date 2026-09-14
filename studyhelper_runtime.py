"""Runtime compatibility fixes for Study Helper.

This module is used both by normal Python launches (through ``sitecustomize``)
and by the PyInstaller runtime hook. It deliberately keeps the application
entry point small while hardening the unofficial translation path used by the
MP3 -> Excel workflow.
"""
from __future__ import annotations

import html
import re
import sys
import threading
import time
from pathlib import Path

_INSTALLED = False
_HTTP_LOCK = threading.Lock()
_LAST_HTTP_REQUEST = 0.0
_SESSION = None


def _version_from_file() -> str | None:
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "VERSION")
    candidates.extend([
        Path(sys.executable).resolve().parent / "VERSION",
        Path(__file__).resolve().parent / "VERSION",
        Path.cwd() / "VERSION",
    ])
    for path in candidates:
        try:
            value = path.read_text(encoding="utf-8").strip()
        except Exception:
            continue
        if re.fullmatch(r"\d+\.\d+\.\d+(?:-rc\.\d+)?", value):
            return value
    return None


def _pace(seconds: float = 1.05) -> None:
    """Keep translation HTTP traffic at roughly one request per second."""
    global _LAST_HTTP_REQUEST
    with _HTTP_LOCK:
        wait = seconds - (time.monotonic() - _LAST_HTTP_REQUEST)
        if wait > 0:
            time.sleep(wait)
        _LAST_HTTP_REQUEST = time.monotonic()


def _session():
    global _SESSION
    if _SESSION is None:
        import requests
        _SESSION = requests.Session()
        _SESSION.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) StudyHelper/2.2"
        })
    return _SESSION


def _google_direct(text: str, source: str, target: str) -> str:
    """Use Google's lightweight JSON endpoint instead of the scraped mobile page.

    The deep-translator Google adapter can be throttled aggressively because it
    scrapes a web page. This endpoint is still unofficial, so we pace requests
    conservatively and retain a second provider as a fallback.
    """
    url = "https://translate.googleapis.com/translate_a/single"
    params = {
        "client": "gtx",
        "sl": source,
        "tl": target,
        "dt": "t",
        "q": text,
    }
    last_error = None
    for attempt in range(4):
        try:
            _pace(1.05)
            response = _session().get(url, params=params, timeout=25)
            if response.status_code == 429:
                raise RuntimeError("Google direct endpoint returned HTTP 429")
            response.raise_for_status()
            payload = response.json()
            parts = payload[0] if isinstance(payload, list) and payload else []
            translated = "".join(
                str(part[0]) for part in parts
                if isinstance(part, list) and part and part[0]
            ).strip()
            if translated:
                return translated
            raise RuntimeError("Google direct endpoint returned an empty translation")
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep((2, 5, 10)[attempt])
    raise RuntimeError("Google direct translation failed") from last_error


def _mymemory_fallback(text: str, source: str, target: str) -> str:
    """Fallback provider used only when Google is unavailable or rate-limited."""
    if source == "auto":
        raise RuntimeError("Fallback translator needs an explicit source language")
    _pace(1.05)
    response = _session().get(
        "https://api.mymemory.translated.net/get",
        params={"q": text, "langpair": f"{source}|{target}"},
        timeout=25,
    )
    response.raise_for_status()
    payload = response.json()
    translated = html.unescape(str(payload.get("responseData", {}).get("translatedText", ""))).strip()
    warning = str(payload.get("responseDetails", "") or "").lower()
    if not translated or "warning" in translated.lower() or "quota" in warning or "limit" in warning:
        raise RuntimeError("Fallback translation quota is unavailable")
    return translated


def _install_translation_patch() -> None:
    try:
        import study_helper_core as core
        # The application-level throttle remains in place as an extra guard.
        core.DEFAULT_CONFIG["translation_min_interval"] = 1.05
    except Exception:
        pass

    try:
        from deep_translator import GoogleTranslator
    except Exception:
        return

    if getattr(GoogleTranslator, "_study_helper_patched", False):
        return

    original_translate = GoogleTranslator.translate

    def robust_translate(self, text, *args, **kwargs):
        value = str(text or "").strip()
        if not value:
            return ""
        source = str(getattr(self, "_source", "auto") or "auto")
        target = str(getattr(self, "_target", "en") or "en")
        primary_error = None
        try:
            return _google_direct(value, source, target)
        except Exception as exc:
            primary_error = exc
        try:
            return _mymemory_fallback(value, source, target)
        except Exception as fallback_error:
            # One final attempt through the library adapter helps when the direct
            # JSON endpoint is temporarily unavailable for reasons other than
            # throttling. Do not loop here; the caller already has retry logic.
            try:
                _pace(1.25)
                return original_translate(self, text, *args, **kwargs)
            except Exception as original_error:
                raise RuntimeError(
                    "번역 서비스 연결에 실패했습니다. Google 직접 번역과 예비 번역 서비스를 모두 시도했지만 응답을 받지 못했습니다. "
                    "인터넷 연결을 확인한 뒤 다시 시도해 주세요."
                ) from original_error

    GoogleTranslator._study_helper_original_translate = original_translate
    GoogleTranslator.translate = robust_translate
    GoogleTranslator._study_helper_patched = True


def _install_version_display_patch() -> None:
    version = _version_from_file()
    if not version:
        return
    try:
        import customtkinter as ctk
    except Exception:
        return

    pattern = re.compile(r"\d+\.\d+\.\d+(?:-rc\.\d+)?")

    if not getattr(ctk.CTk, "_study_helper_title_patched", False):
        original_title = ctk.CTk.title

        def patched_title(self, text=None):
            if isinstance(text, str) and "Study Helper" in text:
                text = pattern.sub(version, text)
            return original_title(self, text)

        ctk.CTk.title = patched_title
        ctk.CTk._study_helper_title_patched = True

    if not getattr(ctk.CTkLabel, "_study_helper_label_patched", False):
        original_init = ctk.CTkLabel.__init__

        def patched_label_init(self, *args, **kwargs):
            text = kwargs.get("text")
            if isinstance(text, str) and ("Audio study suite" in text or "Study Helper" in text):
                kwargs["text"] = pattern.sub(version, text)
            return original_init(self, *args, **kwargs)

        ctk.CTkLabel.__init__ = patched_label_init
        ctk.CTkLabel._study_helper_label_patched = True


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    _install_translation_patch()
    _install_version_display_patch()


if __name__ == "__main__":
    install()
