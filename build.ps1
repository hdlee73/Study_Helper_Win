param([switch]$ExternalFFmpeg)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$requiredFiles = @('.venv\Scripts\python.exe','icon.ico')
if (-not $ExternalFFmpeg) { $requiredFiles += @('ffmpeg\ffmpeg.exe','ffmpeg\ffprobe.exe') }
foreach ($file in $requiredFiles) {
    if (-not (Test-Path -LiteralPath $file)) { throw "Missing: $file. Read README_KO.md first." }
}
& .\.venv\Scripts\python.exe -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependency check failed' }
& .\.venv\Scripts\python.exe scripts\collect_notices.py
if ($LASTEXITCODE -ne 0) { throw 'Notice collection failed' }
$env:STUDY_EXTERNAL_FFMPEG = if ($ExternalFFmpeg) { '1' } else { '0' }
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean StudyHelper.spec
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
Write-Host 'Built: dist\StudyHelper\StudyHelper.exe. Test the complete folder before packaging.'
