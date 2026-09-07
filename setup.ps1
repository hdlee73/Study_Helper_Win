$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
function Check-Exit { if ($LASTEXITCODE -ne 0) { throw 'Command failed. See the error above.' } }
$PythonExe = $null
try {
    $managedPath = (& py -3.14 -I -c "import sys; print(sys.executable)" 2>$null | Select-Object -Last 1)
    if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $managedPath)) { $PythonExe = $managedPath }
} catch {}
if (-not $PythonExe) {
    foreach ($candidate in @('C:\Python314\python.exe', "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe")) {
        if (Test-Path -LiteralPath $candidate) { $PythonExe = $candidate; break }
    }
}
if (-not $PythonExe) { throw 'Python 3.14.7 x64 was not found. Install it with the official Python Install Manager.' }
& $PythonExe -I -c "import sys,struct,encodings,tkinter; from pathlib import Path; assert sys.version_info[:3] == (3,14,7), sys.version; assert struct.calcsize('P') == 8; assert not hasattr(sys,'_is_gil_enabled') or sys._is_gil_enabled(); base=Path(sys.base_prefix).resolve(); stdlib=Path(encodings.__file__).resolve(); assert base in stdlib.parents, f'Python standard library is outside the installation: {stdlib} (base: {base})'"
Check-Exit
& $PythonExe -m venv .venv
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
