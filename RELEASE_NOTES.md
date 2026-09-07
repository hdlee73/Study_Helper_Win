## Study Helper 2.0.0-rc.1

Windows x64 / Python 3.14.7 기반 첫 시험판입니다.

### 다운로드

- **StudyHelper-Setup-2.0.0-rc.1.exe**: 설치 마법사. 일반 사용자에게 권장합니다.
- **StudyHelper-Windows-x64-2.0.0-rc.1.zip**: 압축 해제 후 StudyHelper.exe 실행. 전체 폴더를 유지하세요.
- **SHA256SUMS.txt**: 다운로드 파일 무결성 확인용 해시.
- **build-validation.json / requirements-lock.txt**: 자동 검증 결과와 빌드 의존성 목록.

### 설치 전 확인

- EXE 사용 시 Python 설치는 필요 없습니다.
- **FFmpeg 실행 파일은 미포함**입니다. README의 FFmpeg 준비 절차를 따라야 MP3 생성·변환을 사용할 수 있습니다.
- YouTube에는 Deno, Anki 가져오기에는 Anki와 AnkiConnect가 추가로 필요합니다.
- 음성 인식 모델은 최초 사용 시 다운로드합니다.
- 코드 서명이 없는 시험판이며, 실제 갤럭시북 플렉스에서 전체 기능을 수동 검증한 정식판은 아닙니다.

### 변경사항

CPU INT8 음성 인식, 화면/작업 스레드 분리, 중복 작업 방지, 긴 TTS 메모리 사용 개선, 엑셀 저장 보호, 한글 PDF, Anki 필드 검사와 중복 처리를 적용했습니다. 3회 반복 음성은 Edge TTS의 미국·영국·호주 남성 음성으로 통일했습니다.

온라인 번역/TTS/YouTube 및 실제 Anki 서버와의 연동은 자동 기본 점검에 포함하지 않습니다. 자세한 설치와 개인정보 안내는 README를 참고하세요.
