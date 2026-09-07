# Study Helper for Windows

음성 파일·Excel·Anki를 연결하는 한국어 학습 도구입니다. Windows x64와 **Python 3.14.7**을 기준으로 제작합니다.

## 다운로드 및 설치

**[Releases에서 다운로드](https://github.com/hdlee73/Study_Helper_Win/releases)**

현재 배포 `v2.1.0-rc.1`은 속도 및 Anki 연결 개선 시험판입니다. 자동 빌드·기본 점검 결과와 실제 기기에서의 기능 검증은 구분해 주세요. 코드 서명이 적용되지 않았습니다.

1. Releases의 **Assets**에서 `StudyHelper-Setup-2.1.0-rc.1.exe`를 다운로드하여 실행합니다. `Source code` ZIP은 설치 프로그램이 아닙니다.
2. 설치 마법사를 마치고 시작 메뉴에서 **Study Helper**를 실행합니다. 사용자 계정에 설치하므로 관리자 권한은 필요하지 않습니다.
3. 아래 FFmpeg를 설치한 뒤 프로그램을 다시 실행합니다. YouTube 기능에는 Deno도 준비합니다.
4. 설치 없이 사용하려면 `StudyHelper-Windows-x64-2.1.0-rc.1.zip`을 풀고 `StudyHelper.exe`를 실행합니다. **`_internal`을 포함한 전체 폴더를 유지**하세요.

EXE 사용자는 Python과 pip 라이브러리를 별도로 설치할 필요가 없습니다. 모델 파일은 최초 음성 인식 시 다운로드하며, 설치 파일에 포함하지 않습니다.

### FFmpeg: MP3 생성·변환에 필요

이 릴리스에는 FFmpeg 실행 파일을 동봉하지 않습니다.

1. [FFmpeg 공식 다운로드 안내](https://ffmpeg.org/download.html)에서 Windows용 64비트 빌드를 받습니다.
2. `ffmpeg.exe`와 `ffprobe.exe`를 같은 폴더에 넣습니다. 예: `C:\ffmpeg\bin`.
3. Windows의 **사용자 환경 변수 → Path**에 해당 폴더를 추가하고 프로그램을 다시 실행합니다.
4. 새 PowerShell에서 다음 두 명령이 실행되는지 확인합니다.

```powershell
ffmpeg -version
ffprobe -version
```

PATH를 바꾸지 않으려면 프로그램의 `StudyHelper.exe` 옆에 `ffmpeg` 폴더를 만들고 두 실행 파일을 넣어도 됩니다. MP3 인코딩을 지원하는 빌드를 사용하세요.

### 기능별 추가 준비

| 기능 | 추가 준비 |
|---|---|
| MP3 → Excel/PDF | 최초 모델 다운로드에 인터넷 필요. 이후 모델 캐시가 있으면 로컬 음성 인식 가능 |
| 번역 Excel | Google 번역 서비스 접속 필요 |
| Excel → MP3 | FFmpeg와 인터넷 필요. Microsoft Edge 음성 서비스를 사용 |
| YouTube → MP3 | FFmpeg 및 [Deno](https://docs.deno.com/runtime/getting_started/installation/) 설치·PATH 등록. 사이트 상황에 따라 로그인 필요 |
| Excel → Anki | [Anki](https://apps.ankiweb.net/)와 [AnkiConnect](https://ankiweb.net/shared/info/2055492159) 설치 후 Anki 실행 |

Anki에는 `English` 노트 유형과 `Front`, `Back`, `Example` 필드를 준비하세요. 기존 카드는 수정하지 않고 중복을 제외한 새 카드만 추가합니다. 연결은 로컬 `127.0.0.1:8765`를 사용합니다.

Anki가 사용자 지정 위치에 설치된 경우 `%LOCALAPPDATA%\StudyHelper\config.json`에 `"anki_executable": "D:\\경로\\Anki.exe"`처럼 전체 경로를 지정할 수 있습니다. 프로그램은 현재 일반 설치 경로와 `C:\Anki\Anki.exe`를 자동으로 찾고, 실행 후 최대 45초 동안 AnkiConnect 시작을 기다립니다.

## 지원 기능

- YouTube → MP3
- MP3 → 한/영 번역 Excel
- MP3 → 단순 음성 인식 Excel
- MP3 → 한글 PDF
- Excel → 한/영 교차 MP3
- Excel → 미국·영국·호주 발음 3회 반복 MP3
- Excel → 국가·성별 선택 MP3
- Excel → Anki 카드 추가

Excel은 **제목 행 없이** 사용합니다. 번역/Anki는 A열=앞면, B열=뒷면, C열=출처/예문이며 단일·3회 반복 TTS는 A열을 읽습니다. 3회 반복은 Edge TTS의 미국·영국·호주 남성 목소리를 사용합니다.

## 소스에서 실행하기

[Python 공식 설치 관리자](https://www.python.org/downloads/release/python-3147/)로 일반(GIL 사용) Python 3.14.7 x64를 설치합니다. 저장소를 다운로드하거나 clone한 폴더에서:

```powershell
py install 3.14.7
py -3.14 --version
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
.\.venv\Scripts\python.exe .\test_core.py
.\.venv\Scripts\python.exe .\study_helper.py
```

`setup.ps1`은 `.venv` 가상 환경에 필요한 라이브러리를 설치합니다. 목록은 [requirements.txt](requirements.txt), 빌드 도구는 [requirements-build.txt](requirements-build.txt)를 참고하세요. `fpdf`가 아닌 `fpdf2`를 사용하며 PyTorch/pydub/gTTS는 직접 설치하지 않습니다.

## 직접 빌드하기

FFmpeg를 별도 설치하도록 배포하는 방식:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1 -ExternalFFmpeg
```

프로젝트의 `ffmpeg\ffmpeg.exe`와 `ffmpeg\ffprobe.exe`를 함께 묶어 개인용으로 빌드하려면 질문하신 명령을 그대로 사용하면 됩니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

이 명령은 `dist\StudyHelper\StudyHelper.exe`와 필요한 내부 폴더를 생성합니다. 다른 PC에 설치할 단일 설치 파일은 이어서 Inno Setup에서 `installer.iss`를 Compile해야 합니다.

`dist\StudyHelper\StudyHelper.exe`가 생성됩니다. [Inno Setup](https://jrsoftware.org/isinfo.php)에서 `installer.iss`를 열어 Compile하면 설치 파일이 만들어집니다. FFmpeg를 동봉하려면 해당 파일과 라이선스/대응 소스 고지를 준비하고 `-ExternalFFmpeg` 없이 빌드하세요.

[다른 PC에 쉽게 설치하기](INSTALL_KO.md) · [자세한 설치·빌드·배포 안내](docs/BUILD_KO.md) · [시험판 변경사항](RELEASE_NOTES.md)

GitHub Actions의 `Windows release`는 Windows에서 Python 3.14.7로 테스트, EXE 기본 점검, 설치 파일 생성 후 릴리스를 게시합니다. `VERSION`에 새 버전을 적어 main에 반영하면 해당 버전만 새로 게시합니다. 같은 태그의 기존 릴리스 파일을 자동 교체하지 않습니다.

## 설정 및 문제 해결

- 설정·로그·모델: `%LOCALAPPDATA%\StudyHelper`
- 기본 음성 인식 모델: `base`, CPU INT8, 최대 4스레드. 모델 변경은 앱 종료 후 `config.json`의 `whisper_model` 값을 `tiny`/`base`/`small`로 수정합니다.
- 속도 설정: 기본 STT 탐색 폭은 `whisper_beam_size: 1`, 동시 TTS 요청은 `tts_concurrency: 4`입니다. 품질을 더 중시하면 beam을 3~5로 올릴 수 있지만 처리 시간이 늘어납니다.
- 한글 PDF: Windows 맑은 고딕(`malgun.ttf`)이 필요합니다.
- DLL 오류: [Microsoft Visual C++ x64 재배포 패키지](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)를 확인하세요.
- `Could not find platform independent libraries <prefix>`가 표시되면 Python 실행 파일과 `Lib` 폴더가 서로 다른 위치에 있는 불완전한 설치입니다. Python 파일을 수동으로 이동하지 말고 공식 설치 관리자로 3.14.7을 복구 설치하세요. `setup.ps1`은 이 상태를 라이브러리 설치 전에 검사합니다.
- 작업 중에는 중복 실행과 일반 종료를 막습니다. 강제 취소 기능은 없으며 온라인 서비스 응답이 지연될 수 있습니다.
- 같은 출력 이름을 사용하면 기존 결과가 교체될 수 있습니다. 필요한 원본과 Anki 덱을 먼저 백업하세요.
- 앱 제거 후에도 사용자 설정과 모델 폴더는 남습니다. 필요하지 않으면 사용자가 별도로 삭제할 수 있습니다.

## 개인정보 및 배포 주의사항

음성 인식은 로컬에서 수행하지만 **번역 문장은 Google, 음성 합성 문장은 Microsoft 서비스로 전송**됩니다. 민감한 자료의 처리 여부는 서비스 조건을 확인하고 판단하세요. 외부 서비스 변경·요청 제한으로 기능이 중단될 수 있습니다.

본인에게 처리 권한이 있는 콘텐츠만 사용하세요. 쿠키가 필요한 경우 `%LOCALAPPDATA%\StudyHelper\cookies.txt`에 개인적으로 저장하며, 쿠키·로그·개인 데이터는 저장소나 배포 파일에 올리지 마세요.

배포 파일에 포함되는 의존성 고지는 `_internal\THIRD_PARTY_NOTICES`에서 확인할 수 있습니다. FFmpeg 실행 파일은 별도 설치하며, PyAV 등에 포함된 네이티브 라이브러리의 고지는 별개입니다. 이 저장소 자체의 오픈소스 라이선스는 아직 지정하지 않았습니다. 공개 열람 가능 여부와 재배포 허락은 별개입니다.
