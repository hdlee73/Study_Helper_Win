$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
function Check-Exit { if ($LASTEXITCODE -ne 0) { throw 'Command failed. See the error above.' } }
py -3.14 -c "import sys,struct; assert sys.version_info[:3] == (3,14,7), sys.version; assert struct.calcsize('P') == 8; assert not hasattr(sys,'_is_gil_enabled') or sys._is_gil_enabled()"
Check-Exit
py -3.14 -m venv .venv
Check-Exit
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
Check-Exit
& .\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements-build.txt
Check-Exit
& .\.venv\Scripts\python.exe -m pip check
Check-Exit
& .\.venv\Scripts\python.exe -c "import tkinter, customtkinter, pandas, openpyxl, requests, deep_translator, yt_dlp, faster_whisper, ctranslate2, edge_tts, fpdf; print('Imports OK')"
Check-Exit
& .\.venv\Scripts\python.exe -m pip freeze | Set-Content -Encoding utf8 requirements-lock.txt
Write-Host 'Setup complete. Run: .\.venv\Scripts\python.exe study_helper.py'
