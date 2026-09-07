# 다른 Windows 컴퓨터에 설치하는 가장 쉬운 방법

## 설치 프로그램 사용

1. [GitHub Releases](https://github.com/hdlee73/Study_Helper_Win/releases)에서 가장 최신 버전을 엽니다.
2. Assets에서 `StudyHelper-Setup-2.1.0-rc.1.exe`를 내려받습니다. `Source code.zip`은 설치 파일이 아닙니다.
3. 내려받은 설치 파일을 실행하고 **다음 → 설치**를 누릅니다. 관리자 권한과 Python 설치는 필요하지 않습니다.
4. 시작 메뉴에서 **Study Helper**를 실행합니다.
5. MP3 기능을 사용하려면 [FFmpeg 공식 안내](https://ffmpeg.org/download.html)에서 Windows x64 빌드를 받아 `ffmpeg.exe`, `ffprobe.exe`가 있는 폴더를 사용자 `Path`에 추가합니다. 프로그램을 다시 실행합니다.

YouTube 기능은 [Deno](https://docs.deno.com/runtime/getting_started/installation/)가 추가로 필요할 수 있습니다. Anki 기능은 Anki와 AnkiConnect를 설치하고 Anki를 한 번 재시작하세요.

## 설치 없이 실행

Releases에서 `StudyHelper-Windows-x64-2.1.0-rc.1.zip`을 받아 압축을 완전히 푼 뒤 `StudyHelper.exe`를 실행합니다. `_internal` 폴더를 옮기거나 지우면 안 됩니다.

## 직접 만든 설치 파일을 다른 PC에 전달

프로젝트 폴더에서 다음 명령으로 프로그램을 빌드합니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

이 명령의 결과인 `dist\StudyHelper` 전체를 전달할 수 있습니다. 설치 파일 하나로 전달하려면 Inno Setup에서 `installer.iss`를 열어 Compile하고, `installer_output`에 생성된 Setup EXE를 전달합니다.

다른 PC에서 먼저 시험할 항목은 프로그램 실행, FFmpeg 인식, 최초 음성 모델 다운로드, 한글 PDF, TTS, AnkiConnect 연결입니다. 코드 서명이 없는 시험판은 Windows SmartScreen 안내가 나타날 수 있습니다.
