# Study Helper for Windows

Windows에서 MP3, Excel, Word(DOCX), TTS, Anki를 한 흐름으로 연결하는 개인 학습 도구입니다. 배포 기준은 **Windows x64 / Python 3.14.7**입니다.

## 최신 배포

현재 시험판: **v2.2.0-rc.1**

[GitHub Releases에서 다운로드](https://github.com/hdlee73/Study_Helper_Win/releases)

일반 사용자는 `StudyHelper-Setup-2.2.0-rc.1.exe`를 권장합니다. 설치 없이 사용하려면 `StudyHelper-Windows-x64-2.2.0-rc.1.zip`을 풀고 `StudyHelper.exe`를 실행하세요. ZIP 버전은 `_internal` 폴더를 포함한 전체 폴더를 그대로 유지해야 합니다.

## 주요 기능

- YouTube → MP3
- MP3 → Excel (문장 분리 + 한/영 번역)
- MP3 → Excel (단순 STT)
- **MP3 → DOCX (선택형 타임라인)**
- Excel → MP3 (한/영 교차)
- Excel → MP3 (미국·영국·호주 발음 3회 반복)
- Excel → MP3 (국가·성별 선택)
- Excel → Anki

### MP3 → DOCX 타임라인

DOCX 변환 화면에서 **타임라인 포함** 여부를 선택할 수 있습니다. 타임라인을 포함하면 문서가 `시간 | 내용` 2열 표로 생성되고, 타임라인은 첫 번째 열에만 들어갑니다. Word에서 첫 번째 열 전체를 선택한 뒤 **열 삭제**를 하면 본문을 건드리지 않고 타임라인만 한 번에 지울 수 있습니다.

원하면 **타임라인 없는 사본도 함께 저장**할 수 있습니다.

### MP3 → Excel 번역 제한 대응

번역 요청은 Google 번역의 초당 요청 제한을 넘지 않도록 순차 처리하고 요청 간격을 둡니다. 429/Too Many Requests 계열 오류에는 자동 재시도와 백오프를 적용합니다. 다만 외부 서비스의 일일 한도 자체가 소진된 경우에는 잠시 후 다시 시도해야 합니다.

## 추가 준비

| 기능 | 추가 준비 |
|---|---|
| MP3 → Excel / DOCX | 최초 Whisper 모델 다운로드에 인터넷 필요. 모델 캐시 후 STT는 로컬 수행 |
| 번역 Excel | Google 번역 서비스 접속 필요 |
| Excel → MP3 | FFmpeg + 인터넷 필요. Microsoft Edge 음성 서비스 사용 |
| YouTube → MP3 | FFmpeg + Deno. 사이트 상황에 따라 로그인/쿠키 필요 |
| Excel → Anki | Anki + AnkiConnect |

### FFmpeg

배포본에는 FFmpeg 실행 파일을 포함하지 않습니다. Windows용 64비트 FFmpeg를 설치하고 `ffmpeg.exe`, `ffprobe.exe`가 있는 폴더를 사용자 `Path`에 추가하세요. 또는 `StudyHelper.exe` 옆에 `ffmpeg` 폴더를 만들고 두 실행 파일을 넣어도 됩니다.

새 PowerShell에서 다음이 실행되는지 확인하세요.

```powershell
ffmpeg -version
ffprobe -version
```

## Excel / Anki 형식

번역 및 Anki용 Excel은 제목 행 없이 사용합니다.

- A열: 앞면
- B열: 뒷면
- C열: 출처/예문

Anki에는 `English` 노트 유형과 `Front`, `Back`, `Example` 필드를 준비하세요. 연결은 로컬 `127.0.0.1:8765`를 사용합니다.

## 소스에서 실행

```powershell
py install 3.14.7
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
.\.venv\Scripts\python.exe .\test_core.py
.\.venv\Scripts\python.exe .\study_helper.py
```

`study_helper.py`는 현재 앱 진입점이고, 검증된 기존 백엔드는 `study_helper_core.py`에 분리되어 있습니다. 새 진입점에서 번역 속도 제한, DOCX 생성, 새 UI를 적용합니다.

## 직접 빌드

FFmpeg를 외부 설치 방식으로 빌드:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1 -ExternalFFmpeg
```

GitHub Actions의 `Windows release` 워크플로는 테스트, PyInstaller 빌드, frozen smoke test, Inno Setup 설치 파일 생성, Release 게시를 자동으로 수행합니다. `VERSION`을 새 버전으로 올리고 `main`에 반영하면 새 릴리스가 생성됩니다.

## 설정 / 로그 / 모델

사용자 데이터 위치:

```text
%LOCALAPPDATA%\StudyHelper
```

기본 음성 인식은 faster-whisper `base`, CPU INT8, `beam_size=1`, VAD 사용입니다. 번역 요청 간격 기본값은 약 0.30초로 두어 초당 요청 제한에 여유를 둡니다.

## 개인정보

- 음성 인식(STT): 로컬 수행
- 번역: Google 서비스로 문장 전송
- TTS: Microsoft 서비스로 문장 전송
- Anki: 로컬 `127.0.0.1:8765` 연결

민감한 자료를 처리할 때는 외부 서비스 전송 범위를 확인하세요. 본인에게 처리 권한이 있는 콘텐츠만 사용하세요.

자세한 빌드 안내: [docs/BUILD_KO.md](docs/BUILD_KO.md)  
다른 PC 설치 안내: [INSTALL_KO.md](INSTALL_KO.md)  
이번 버전 변경사항: [RELEASE_NOTES.md](RELEASE_NOTES.md)
