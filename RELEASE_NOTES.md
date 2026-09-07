## Study Helper 2.1.0-rc.1

Windows x64 / Python 3.14.7 기반 속도·Anki 연결 개선 시험판입니다.

### 다운로드

- **StudyHelper-Setup-2.1.0-rc.1.exe**: 설치 마법사. 일반 사용자에게 권장합니다.
- **StudyHelper-Windows-x64-2.1.0-rc.1.zip**: 압축 해제 후 StudyHelper.exe 실행. 전체 폴더를 유지하세요.
- **SHA256SUMS.txt**: 다운로드 파일 무결성 확인용 해시.
- **build-validation.json / requirements-lock.txt**: 자동 검증 결과와 빌드 의존성 목록.

### 설치 전 확인

- EXE 사용 시 Python 설치는 필요 없습니다.
- **FFmpeg 실행 파일은 미포함**입니다. README의 FFmpeg 준비 절차를 따라야 MP3 생성·변환을 사용할 수 있습니다.
- YouTube에는 Deno, Anki 가져오기에는 Anki와 AnkiConnect가 추가로 필요합니다.
- 음성 인식 모델은 최초 사용 시 다운로드합니다.
- 코드 서명이 없는 시험판이며, 실제 갤럭시북 플렉스에서 전체 기능을 수동 검증한 정식판은 아닙니다.

### 변경사항

무거운 라이브러리와 화면 패널을 필요할 때 불러오도록 바꿨습니다. 측정 환경에서 시작 모듈 로딩은 평균 18.8초에서 1.5초로 줄었습니다. TTS는 최대 4개를 동시에 생성하며 MP3 조각을 FFmpeg 한 번으로 결합합니다. 24조각 비교에서 결합 시간이 4.11초에서 0.26초로 줄었습니다.

ONNX Runtime의 개발·변환 도구는 배포 파일에서 제외해 빌드 시간과 배포 용량을 줄였습니다. 실제 음성 인식에 필요한 실행 모듈은 그대로 포함합니다.

Anki 26.8.1의 `C:\Anki\Anki.exe` 설치 경로를 지원하고, Anki를 연 뒤 AnkiConnect가 시작될 때까지 최대 45초 대기합니다. 실행 파일을 못 찾는 경우와 AnkiConnect가 응답하지 않는 경우를 구분해서 안내합니다. STT는 빠른 `beam_size=1`, 무음 구간 필터를 기본으로 사용합니다.

온라인 번역/TTS/YouTube 및 실제 Anki 서버와의 연동은 자동 기본 점검에 포함하지 않습니다. 자세한 설치와 개인정보 안내는 README를 참고하세요.
