# 📧 EmailNotifier

**Outlook 없이도 IMAP 메일 알림을 받을 수 있는 Windows 트레이 앱**

> IMAP 프로토콜로 메일함을 주기적으로 폴링하여, 새 메일 도착 시 Windows 토스트 알림을 표시합니다.

---

## ✨ 주요 기능

- **IMAP 기반 메일 수신 감지** – Outlook 없이 모든 IMAP 지원 메일함과 호환
- **Windows 트레이 아이콘** – 백그라운드 실행, 트레이 아이콘 우클릭으로 제어
- **Windows 토스트 알림** – 보낸사람 / 제목 / 내용 미리보기 표시
- **웹메일 딥링크** – 알림 클릭 시 웹메일로 바로 이동 (mailplug 포함)
- **재알림 기능** – 읽지 않은 메일에 대해 설정 주기마다 반복 알림
- **비밀번호 안전 저장** – Windows DPAPI 암호화 저장 (평문 저장 없음)
- **중복 실행 방지** – 잠금 파일 기반 단일 인스턴스 보장
- **로그 실시간 조회** – 트레이 메뉴 → View Logs

---

## 🖥️ 시스템 요구사항

- **OS**: Windows 10 / 11 (x64)
- **필요 사항**: 인터넷 연결, IMAP 지원 메일 계정

> ℹ️ 설치 프로그램 방식이므로 Python 환경이 없어도 바로 실행 가능합니다.

---

## 🚀 설치 및 실행

### 1. 설치 프로그램 다운로드

[**Releases 페이지**](https://github.com/1991ZINU/EmailNotifier/releases)에서 최신 버전의 `EmailNotifier_Installer.exe`를 다운로드합니다.

### 2. 설치 실행

`EmailNotifier_Installer.exe`를 실행하면 설치가 완료됩니다.  
설치 완료 후 자동으로 Email Notifier가 시작됩니다.

### 3. 최초 설정

프로그램 최초 실행 시 아래 정보를 입력하는 설정 창이 나타납니다:

| 항목 | 예시 |
|------|------|
| IMAP 서버 주소 | `imap.gmail.com` |
| IMAP 포트 | `993` |
| IMAP 아이디 | `yourname@gmail.com` |
| IMAP 비밀번호 | 앱 비밀번호 권장 |
| SSL 사용 | `Y` |
| 폴더 | `INBOX` |
| 폴링 주기(초) | `60` |
| 재알림 주기(초) | `1800` |
| 웹메일 주소 | `https://mail.google.com` |

**연결 테스트** 버튼으로 IMAP 접속 확인 후 **저장**을 누르면 알림이 시작됩니다.

---

## ⚙️ 설정 변경

트레이 아이콘 우클릭 → **Settings** 메뉴에서 언제든지 설정을 변경할 수 있습니다.

---

## 📁 프로젝트 구조

```
EmailNotifier/
├── src/
│   ├── main.py              # 진입점 – 트레이 아이콘, 설정 UI
│   └── notifier.py          # IMAP 폴링 및 토스트 알림 핵심 로직
├── installer/
│   └── email_notifier_installer.iss  # Inno Setup 스크립트
├── build_installer.bat      # 빌드 자동화 스크립트 (PyInstaller + Inno Setup)
├── requirements.txt         # Python 패키지 의존성
└── README.md
```

---

## 🔧 개발 환경 설정 (소스 빌드)

```bash
# 1. 가상환경 생성 및 활성화
python -m venv venv
venv\Scripts\activate

# 2. 의존성 설치
pip install -r requirements.txt
pip install pyinstaller pystray pillow pywin32 winotify

# 3. 개발 모드 실행
python src/main.py

# 4. 설치 프로그램 빌드 (Inno Setup 6 필요)
build_installer.bat
```

---

## 🔒 보안

- 비밀번호는 **Windows DPAPI**로 암호화하여 `config.yaml`에 저장됩니다.
- 동일 Windows 사용자 계정에서만 복호화 가능합니다.
- `config.yaml`은 `.gitignore`에 의해 저장소에 포함되지 않습니다.

---

## 📝 릴리스 노트 (Changelog)

### v1.1.1
- **빌드 시스템 개선**: `build_installer.bat` 스크립트에서 불필요한 로그 출력을 간소화하고 Inno Setup(ISCC) 경로 탐색 로직 최적화
- **설치 프로그램 설정 최적화**: `email_notifier_installer.iss` 내 불필요한 주석 제거 및 언인스톨 로직 간소화

---

## 📜 라이선스

MIT License

---

## 🙋 문의

이슈나 기능 요청은 [GitHub Issues](https://github.com/1991ZINU/EmailNotifier/issues)를 이용해 주세요.
