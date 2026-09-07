# Study Helper 소스 빌드·배포 상세 안내

> 이 문서는 최초 소스 패키지의 상세 제작 안내입니다. 현재 릴리스 설치는 저장소 루트 README.md를 먼저 확인하세요. 아래 동봉 FFmpeg 방식과 달리 GitHub 릴리스는 FFmpeg 실행 파일을 별도 설치합니다. 현재 검증 결과는 릴리스의 build-validation.json과 Actions 실행 결과가 우선합니다.

작성 기준: 2026-09-07 / 대상: Windows x64, 일반(GIL 사용) Python 3.14.7.

이 묶음은 개선 소스와 빌드·설치 프로그램 제작 파일입니다. 완성된 EXE나 검증 완료된 설치 프로그램은 포함하지 않습니다. C:\Vibe의 원본은 변경하지 않았습니다. 압축을 C:\Vibe\StudyHelper로 풀어 아래 절차를 진행하세요.

## 1. 변경한 내용

기존 8개 메뉴(YouTube MP3, 번역 Excel, 단순 STT Excel, PDF, 한/영 교차 TTS, 3회 반복 TTS, 단일 TTS, Anki)를 유지했습니다.

| 변경 | 효과 및 차이 |
|---|---|
| openai-whisper → faster-whisper, CPU INT8 | PyTorch를 직접 설치하지 않습니다. 모델은 STT 첫 사용 시에만 로드하며 재사용합니다. CPU 사용 스레드는 최대 4개입니다. 속도·정확도는 녹음과 장비에 따라 달라지며 이 노트북에서 벤치마크하지 않았습니다. |
| 화면 입력을 작업 시작 전에 복사, 화면 갱신을 큐로 전달 | 작업 스레드가 Tk 위젯을 직접 읽거나 갱신하지 않습니다. |
| 한 번에 한 작업 실행 | 중복 클릭에 의한 모델 동시 실행과 임시 파일 충돌을 막습니다. 작업 중에는 종료 대신 안내를 표시합니다. 강제 취소 기능은 없습니다. |
| pydub 전체 음성 누적 제거 | 조각별 FFmpeg 처리와 디스크 임시 PCM을 사용합니다. 긴 음성의 RAM 누적을 줄이는 대신 임시 디스크 공간이 필요합니다. |
| TTS 요청 재시도, 동일 문장/음성 재사용 | 같은 작업에서 같은 음성을 다시 다운로드하지 않습니다. 실패한 문장을 조용히 건너뛰지 않고 오류를 표시합니다. |
| 3회 반복을 Edge TTS로 통일 | 미국·영국·호주 남성 목소리 순서입니다. 기존 gTTS 목소리와 다릅니다. 단일 TTS는 기존 국가·성별 선택을 유지합니다. |
| 엑셀 읽기 오류 시 중단, 교체 저장 | 손상되거나 잠긴 기존 파일을 빈 파일로 취급하지 않습니다. Excel/PDF/최종 TTS MP3는 임시 파일을 완성한 뒤 교체합니다. |
| 한글 PDF | Windows의 맑은 고딕을 찾아 fpdf2에 등록합니다. 글꼴 파일 자체를 배포본에 복사하지 않습니다. |
| 문장 분리 | '바다 위로'처럼 글자 '다' 뒤의 공백을 문장 경계로 오인하지 않습니다. 문장부호 없는 긴 발화의 완벽한 문장 분리는 보장하지 않습니다. |
| Anki | 선택 덱·노트 유형 기준으로 중복 조회, 필드 검사, 100개 단위 처리, 일반 텍스트의 HTML 특수문자 이스케이프를 적용합니다. 기존 카드는 수정하지 않고 새 카드만 추가합니다. |
| 경로 관리 | 아이콘은 실행 위치와 무관하게 찾습니다. 설정·모델·쿠키·로그는 사용자별 LocalAppData에 저장합니다. |

설정은 `%LOCALAPPDATA%\StudyHelper\config.json`입니다. 최초 실행 후 만들어지며 `whisper_model` 기본값은 `base`입니다. 느리면 앱 종료 후 `tiny`로, 인식 품질이 더 필요하면 `small`로 바꿀 수 있습니다. 모델을 바꾸면 최초 다운로드가 다시 필요합니다. 예전 `.windows_audio_anki\config.json` 설정은 자동 이전하지 않으며 필요한 값만 수동 복사하세요.

원본처럼 한/영 교차 모드의 B열에 `_`가 있으면 영어 읽기를 건너뜁니다. 단일/3회 반복은 A열을 사용합니다. 엑셀에는 제목 행 없이 데이터를 넣으세요. Anki/번역 Excel은 A=앞면(한글), B=뒷면(영문), C=출처/예문입니다.

## 2. 필요한 프로그램과 라이브러리

Python 3.14.7은 2026-08-05 공식 출시되었습니다. Python 공식 페이지에서 Windows용 Python 설치 관리자를 받고 **일반 64비트 Python 3.14.7**을 설치하세요. 실험적인 별도 환경이나 free-threaded 빌드는 이 묶음의 대상이 아닙니다.

공식 설치 관리자 사용 시 PowerShell에서:

```powershell
py install 3.14.7
py -3.14 --version
```

`py install`을 알아듣지 못하면 구형 Python Launcher가 선택된 것일 수 있습니다. 공식 Python 설치 관리자를 먼저 설치하고 터미널을 다시 여세요. `py -3.14 --version`이 정확히 3.14.7인지 확인하세요.

| 설치 이름 | 용도 |
|---|---|
| customtkinter | 프로그램 화면 |
| pandas, openpyxl | .xlsx 읽기·쓰기 |
| requests, deep-translator | AnkiConnect 호출, 한/영 번역 |
| yt-dlp[default] | YouTube 음원 다운로드와 EJS 지원 패키지 |
| faster-whisper, ctranslate2 | 로컬 CPU 음성 인식 |
| edge-tts | 온라인 음성 합성 |
| fpdf2 | 한글 지원 PDF |
| pyinstaller, pyinstaller-hooks-contrib | EXE 빌드 |

tkinter, asyncio, threading 등은 Python 표준 라이브러리입니다. tkinter는 pip로 설치하지 않습니다. `fpdf`와 `fpdf2`를 함께 설치하지 마세요. 원본의 `whisper`, `torch`, `gtts`, `pydub`, `python-docx`는 개선판에 직접 필요하지 않습니다. NumPy/PyAV/ONNX Runtime/tokenizers 등은 의존성으로 자동 설치됩니다.

**FFmpeg는 pip 라이브러리와 별도로 준비해야 합니다.** [FFmpeg 공식 다운로드 안내](https://ffmpeg.org/download.html)의 Windows 빌드 링크에서 64비트 빌드를 구해 다음 두 파일을 넣으세요. 직접 빌드한다면 libmp3lame 인코더가 필요합니다.

```text
C:\Vibe\StudyHelper\
  study_helper.py
  icon.ico
  setup.ps1
  build.ps1
  StudyHelper.spec
  installer.iss
  requirements.txt
  requirements-build.txt
  ffmpeg\
    ffmpeg.exe
    ffprobe.exe
```

FFmpeg가 PATH에 있으면 소스 실행 때 사용할 수 있지만, 동봉 빌드는 위 폴더의 두 파일을 요구합니다. STT 자체는 PyAV로 읽지만 MP3 변환·합성에는 FFmpeg 실행 파일이 필요합니다.

YouTube는 최신 yt-dlp에서 JavaScript 실행 환경이 필요할 수 있습니다. [yt-dlp 공식 안내](https://github.com/yt-dlp/yt-dlp#dependencies)에 맞는 **Deno**를 설치하고 PATH에 등록하세요. 새 PowerShell에서 `deno --version`으로 확인하세요. 이 묶음은 Deno를 자동 설치하거나 동봉하지 않습니다. 배포받는 PC에서도 YouTube 기능 사용 시 별도 설치가 필요할 수 있습니다.

## 3. 라이브러리 설치와 소스 실행

PowerShell에서 아래를 실행합니다. 스크립트는 정확한 Python 버전과 64비트 여부를 검사하고, 프로젝트 전용 `.venv`에 설치합니다. 전역 Python 환경은 건드리지 않습니다.

```powershell
Set-Location C:\Vibe\StudyHelper
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
.\.venv\Scripts\python.exe .\test_core.py
.\.venv\Scripts\python.exe .\study_helper.py
```

`ExecutionPolicy Bypass`는 해당 실행에만 적용합니다. 회사의 보안 정책을 변경하는 절차가 아닙니다. 스크립트를 실행할 수 없다면 다음과 같이 직접 설치하세요.

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements-build.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe study_helper.py
```

`--only-binary=:all:`은 Windows용 미리 빌드된 패키지만 사용합니다. 설치 실패 시 해당 오류를 먼저 해결해야 하며, 무조건 옵션을 지워서 대형 C++ 라이브러리를 소스 빌드하지 마세요. 현재 확인한 버전 조합은 `constraints-resolved.txt`에 있습니다. 같은 조합을 재현하려면 설치 명령에 `-c constraints-resolved.txt`를 추가합니다. 이는 설치 실행 검증을 마친 lock 파일과는 다릅니다. 실제 설치 성공 후 생성된 `requirements-lock.txt`를 배포 버전별로 보관하세요.

`Could not find platform independent libraries <prefix>`가 반복되면 Python 실행 파일과 표준 `Lib` 폴더가 분리된 상태입니다. 공식 Python 설치 관리자로 3.14.7을 복구 설치하고 Python 설치 폴더의 파일을 수동 이동하지 마세요. 개선된 `setup.ps1`은 `encodings`와 tkinter를 포함한 표준 라이브러리 위치를 먼저 검사합니다.

처음 STT를 실행하면 Hugging Face에서 모델을 다운로드합니다. 이후 모델이 캐시에 있으면 STT는 오프라인 사용이 가능합니다. 번역·TTS·YouTube는 인터넷이 필요합니다. CPU 모드이므로 CUDA는 설치하지 않아도 됩니다. DLL 오류가 나면 [Microsoft의 Visual C++ 재배포 패키지 안내](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)에서 x64 런타임을 확인하세요.

## 4. Anki 준비

1. [Anki 공식 사이트](https://apps.ankiweb.net/)에서 Anki를 설치합니다.
2. Anki의 도구 → 추가 기능 → 추가 기능 가져오기에서 [AnkiConnect](https://ankiweb.net/shared/info/2055492159)를 설치하고 Anki를 재시작합니다.
3. `English`라는 노트 유형을 만들고 필드 이름을 정확히 `Front`, `Back`, `Example`로 맞춥니다. 이미 다른 노트 유형이 있으면 앱 설정의 `anki_note_type`을 그 이름으로 바꿀 수 있습니다.
4. 카드 앞면 템플릿에 `{{Front}}`, 뒷면에는 `{{FrontSide}}<hr id=answer>{{Back}}<br>{{Example}}` 등을 넣습니다.
5. Anki를 열어 둔 상태에서 가져옵니다. 연결은 `127.0.0.1:8765`만 사용합니다. 외부 공개 포트나 공유기 포트 포워딩은 필요 없습니다.

카드 추가는 전체 작업을 한 번에 되돌리는 트랜잭션이 아닙니다. 도중 실패하면 일부 카드가 추가될 수 있어 앱이 이를 알립니다. 덱 백업 후 사용하고, 재실행 전 추가된 카드를 확인하세요. 기본 Anki 검색의 덱 범위에는 하위 덱이 포함될 수 있습니다.

## 5. 아이콘을 적용한 EXE 빌드

소스 실행에서 8개 메뉴를 먼저 확인한 뒤 같은 PowerShell에서 실행합니다.

```powershell
Set-Location C:\Vibe\StudyHelper
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
.\dist\StudyHelper\StudyHelper.exe
```

결과는 `dist\StudyHelper\StudyHelper.exe`입니다. **옆의 `_internal` 폴더를 포함하여 `dist\StudyHelper` 전체가 프로그램**입니다. EXE만 복사하면 실행되지 않습니다. 첨부한 icon.ico가 EXE 아이콘과 창 아이콘에 모두 적용됩니다. `StudyHelper.spec`에 CustomTkinter 리소스, 음성 인식 라이브러리, FFmpeg, 패키지 메타데이터 수집을 설정했습니다.

대형 음성 인식 의존성 때문에 `--onefile`보다 이 폴더형 구성을 권합니다. 실행마다 큰 파일을 풀 필요가 없고 DLL·리소스 누락을 확인하기 쉽습니다. Windows EXE는 Windows에서 빌드하세요. 사용자가 받는 EXE에는 Python 런타임이 포함되므로 상대 PC에 Python이나 pip 라이브러리를 따로 설치할 필요는 없습니다. 단, Anki·Deno·모델 다운로드 같은 외부 준비는 별개입니다.

빌드 오류는 콘솔 내용을 확인하고, 실행 중 작업 오류 로그는 `%LOCALAPPDATA%\StudyHelper\study_helper.log`를 확인하세요. 화면 자체가 열리지 않으면 spec의 `console=False`를 임시로 `True`로 바꾸고 재빌드하여 시작 오류를 확인합니다. 최초 실행 시 모델 다운로드가 끝날 때까지 시간이 걸릴 수 있습니다.

## 6. 배포용 설치 프로그램 만들기

1. [Inno Setup 공식 사이트](https://jrsoftware.org/isinfo.php)에서 Inno Setup 6 이상을 설치합니다.
2. `installer.iss`를 열고 Compile을 누릅니다. 소스 폴더와 같은 위치에서 열어야 합니다.
3. `installer_output\StudyHelper-Setup-2.0.0.exe`가 만들어집니다.
4. Python이 없는 별도 PC/가상 머신에서 설치·실행·제거를 확인한 뒤 배포합니다.

설치 파일은 사용자 계정의 `%LOCALAPPDATA%\Programs\StudyHelper`에 설치하며 관리자 권한을 요구하지 않습니다. 시작 메뉴, 선택적인 바탕화면 바로가기, 제거 기능을 제공합니다. 앱을 업데이트할 때 `AppVersion`을 올리고 `AppId`는 유지하세요. 제거 시 `%LOCALAPPDATA%\StudyHelper`의 사용자 설정·모델은 보존됩니다. 완전 삭제는 사용자가 그 폴더를 별도로 삭제하면 됩니다.

설치 파일이 필요 없는 사용자에게는 `dist\StudyHelper` 전체를 ZIP으로 전달할 수 있습니다. 여기 제공된 `StudyHelper-source.zip`은 그 실행용 ZIP이 아니라 **소스 및 제작 도구 묶음**입니다.

## 7. 배포할 때 확인할 사항

- **실제 검증 범위:** 이 작업에서는 Python 3.12.14의 보조 환경에서 문법과 8개 오프라인 회귀 테스트를 통과했습니다. PyPI에 Windows x64/Python 3.14용 전체 의존성을 설치할 수 있는 조합이 있는지도 pip dry-run으로 확인했습니다. 실제 Python 3.14.7에서 GUI 실행, 모델 인식, 네트워크 서비스, EXE/설치 파일 빌드는 아직 검증하지 않았습니다. `VALIDATION.md` 참조.
- **배포 전 시험:** Python 없는 PC에서 한글·공백 사용자 경로, 125~200% 화면 배율, 작은 화면, 한글 PDF 페이지 넘김, 500행 이상 TTS, 숫자 셀, Excel이 열려 있는 경우, 네트워크 단절, Anki 미실행/필드 누락/중복 카드, 설치·업데이트·제거를 확인하세요.
- **용량·발열:** base 모델부터 시작하고 전원 어댑터 사용을 권합니다. 처리 시간을 실측하세요. 24kHz·16bit·모노 임시 PCM만도 생성 음성 1시간에 약 173MB이며 MP3 조각·모델·설치 공간이 추가됩니다. 긴 작업에는 여유 디스크와 절전 설정 확인이 필요합니다.
- **개인정보:** 번역 문장은 Google 번역 서비스로, TTS 문장은 Microsoft Edge 음성 서비스로 전송됩니다. STT 음성 인식은 로컬에서 처리하되 모델 최초 다운로드는 외부 접속입니다. 배포 안내에 이 차이를 명시하세요. 민감한 내용을 입력하기 전에 해당 서비스 이용 조건을 확인해야 합니다.
- **쿠키:** 로그인용 cookies.txt는 필요할 때만 `%LOCALAPPDATA%\StudyHelper\cookies.txt`에 둡니다. 원본의 작업 폴더 쿠키 자동 사용을 없앴습니다. 계정 쿠키, 개인 설정, 로그, 실제 음성·엑셀, `.venv`, 모델 캐시를 배포 ZIP에 섞지 마세요.
- **외부 서비스 변경:** yt-dlp와 Edge TTS/Google 번역은 외부 서비스 변경·요청 제한으로 동작이 달라질 수 있습니다. 실패 시 라이브러리를 검증된 버전으로 업데이트하고 EXE를 다시 빌드해야 합니다. 이 앱에는 자동 업데이트 기능이 없습니다. 배포 규모가 커지면 사용 조건과 SLA가 명시된 공식 API 도입을 검토하세요.
- **콘텐츠 권리:** 본인 소유 또는 다운로드·변환 권한이 있는 콘텐츠만 처리하고 YouTube 등 서비스의 이용 조건을 따르세요. 이 프로그램 자체가 콘텐츠 사용 허락을 주지는 않습니다.
- **라이선스:** 무료 배포도 사용 패키지와 FFmpeg/PyAV 내 코덱 라이선스 검토가 필요합니다. 실제 사용한 FFmpeg 빌드의 `-version`/`-buildconf`, LGPL/GPL/nonfree 설정, 대응 소스 제공 조건을 확인하세요. 라이선스 원문·저작권 고지·소스 제공 안내를 `THIRD_PARTY_NOTICES` 폴더에 준비한 뒤 재빌드하면 동봉됩니다. 해당 폴더는 현재 완성되지 않았으므로 이 묶음을 라이선스 검토 완료 배포본으로 취급하지 마세요.
- **글꼴·아이콘:** 맑은 고딕 파일 자체는 동봉하지 않습니다. PDF 임베딩 조건과 사용자 제공 icon.ico의 배포 권한도 확인하세요. 추가 언어·이모지는 글꼴 지원 범위에 따라 누락될 수 있습니다.
- **서명:** 공개 배포 시 Windows 코드 서명 인증서로 앱 EXE와 최종 설치 파일에 서명하고 타임스탬프를 넣는 것이 좋습니다. 서명이 있어도 SmartScreen 경고가 반드시 없어지는 것은 아닙니다. 백신 비활성화를 요구하지 말고 실제 탐지 원인을 확인하세요. SHA-256 해시와 버전·변경사항도 함께 제공하세요.
- **출력 교체:** YouTube 다운로드는 동일 이름 MP3가 있으면 중단합니다. 다른 생성 기능은 같은 출력 이름을 사용하면 기존 결과를 교체할 수 있으므로 필요한 결과를 백업하거나 다른 파일명을 사용하세요. 서로 다른 앱 인스턴스 간의 동일 출력 파일 동시 편집까지 잠그지는 않습니다.

## 8. 확인한 공식 자료

- [Python 3.14.7 릴리스](https://www.python.org/downloads/release/python-3147/)
- [Python Windows 설치 관리자](https://docs.python.org/3.14/using/windows.html)
- [faster-whisper CPU INT8 사용과 의존성](https://github.com/SYSTRAN/faster-whisper)
- [CTranslate2 Windows wheel 및 지원 버전](https://pypi.org/project/ctranslate2/)
- [PyInstaller 공식 안내](https://pyinstaller.org/en/stable/)
- [PyInstaller 리소스 경로](https://pyinstaller.org/en/stable/runtime-information.html)
- [yt-dlp 의존성](https://github.com/yt-dlp/yt-dlp#dependencies)
- [Inno Setup 사용자 권한 설치](https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm)
- [FFmpeg 라이선스와 배포 안내](https://ffmpeg.org/legal.html)
- [Microsoft SmartScreen 안내](https://learn.microsoft.com/en-us/windows/security/operating-system-security/virus-and-threat-protection/microsoft-defender-smartscreen/)

