from pathlib import Path
import os
from PyInstaller.utils.hooks import collect_all, copy_metadata

root = Path(SPECPATH)
datas = [(str(root / 'icon.ico'), '.')]
binaries = [] if os.environ.get('STUDY_EXTERNAL_FFMPEG') == '1' else [(str(root / 'ffmpeg' / name), 'ffmpeg') for name in ('ffmpeg.exe', 'ffprobe.exe')]
hiddenimports = ['openpyxl', 'faster_whisper', 'yt_dlp_ejs', 'smoke_test']
for package in ('customtkinter', 'faster_whisper', 'ctranslate2', 'av', 'onnxruntime', 'tokenizers', 'yt_dlp', 'yt_dlp_ejs'):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h
for name in ('faster-whisper', 'edge-tts', 'fpdf2', 'yt-dlp', 'ctranslate2'):
    datas += copy_metadata(name)
if (root / 'THIRD_PARTY_NOTICES').is_dir():
    datas.append((str(root / 'THIRD_PARTY_NOTICES'), 'THIRD_PARTY_NOTICES'))
a = Analysis([str(root / 'study_helper.py')], pathex=[str(root)], binaries=binaries,
             datas=datas, hiddenimports=hiddenimports, excludes=['torch', 'whisper', 'pydub', 'gtts'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='StudyHelper',
          debug=False, strip=False, upx=False, console=False, icon=str(root / 'icon.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='StudyHelper')
