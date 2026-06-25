# 이 프로그램은 Outlook이 설치되지 않은 환경에서도 IMAP을 통해 메일 알림을 제공하는
# Email Notifier 응용 프로그램입니다.
# 설정 화면에서 IMAP 서버 정보를 입력하고, 트레이 아이콘을 통해 설정을 수정할 수 있습니다.
# 최초 실행 시 환영 알림을 표시하고, 중복 실행 방지를 구현합니다.
# import pathlib, sys, getpass, subprocess, yaml, logging, threading, tkinter as tk, os, tempfile, atexit
import pathlib, sys, getpass, subprocess, yaml, logging, threading, tkinter as tk, os, tempfile, atexit, time
from datetime import datetime
from tkinter import messagebox
from imapclient import IMAPClient
import pystray
from pystray import MenuItem as Item
from PIL import Image, ImageDraw

if getattr(sys, 'frozen', False):
    # When frozen, executable resides in src/dist
    BASE_PATH = pathlib.Path(sys.executable).parent
else:
    BASE_PATH = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = BASE_PATH.parent
SRC_PATH = PROJECT_ROOT / "src"
sys.path.append(str(SRC_PATH))

import notifier as notifier_mod
EmailNotifier = notifier_mod.EmailNotifier
encrypt_password = notifier_mod.encrypt_password
decrypt_password = notifier_mod.decrypt_password

# Determine base directory depending on execution mode (frozen executable or source)
if getattr(sys, 'frozen', False):
    BASE_PATH = pathlib.Path(sys.executable).parent
else:
    BASE_PATH = pathlib.Path(__file__).resolve().parent

# ---- Duplicate instance prevention ----
lock_path = pathlib.Path(os.getenv('APPDATA') or tempfile.gettempdir()) / 'EmailNotifier.lock'
# Remove stale lock file if it exists (e.g., from previous crash)
if lock_path.exists():
    try:
        lock_path.unlink()
    except Exception:
        pass
_lock_file = None

def acquire_instance_lock() -> bool:
    global _lock_file
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
        _lock_file = os.fdopen(fd, 'w')
        _lock_file.write(str(os.getpid()))
        _lock_file.flush()
        atexit.register(release_instance_lock)
        return True
    except FileExistsError:
        return False

def release_instance_lock():
    global _lock_file
    try:
        if _lock_file:
            _lock_file.close()
        if lock_path.exists():
            lock_path.unlink()
    except Exception:
        pass

    # Determine BASE_PATH based on execution mode
    if getattr(sys, 'frozen', False):
        # When frozen, executable resides in src/dist, so PROJECT_ROOT should be src
        BASE_PATH = pathlib.Path(sys.executable).parent
        PROJECT_ROOT = BASE_PATH.parent  # src directory
        SRC_PATH = PROJECT_ROOT  # src already contains modules
    else:
        BASE_PATH = pathlib.Path(__file__).resolve().parent
        PROJECT_ROOT = BASE_PATH.parent
        SRC_PATH = PROJECT_ROOT / "src"
    # Add source directory to sys.path
    sys.path.append(str(SRC_PATH))

# Setup logger for main script
log_dir = BASE_PATH / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / "email_notifier_main.log"
logger = logging.getLogger("EmailNotifierMain")

# Read config to determine initial log level
init_level_str = "INFO"
cfg_path = BASE_PATH / "config.yaml"
if cfg_path.is_file():
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
            init_level_str = cfg.get("log_level", "INFO")
    except Exception:
        pass

init_level = getattr(logging, init_level_str, logging.INFO)
logger.setLevel(init_level)

handler = logging.FileHandler(log_file, encoding="utf-8")
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(handler)
logger.info("Main script started with log level: %s", init_level_str)



def _write_config(full_cfg: dict) -> None:
    """Update or create config.yaml with provided full settings."""
    cfg_path = BASE_PATH / "config.yaml"
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except FileNotFoundError:
        cfg = {}
        
    # 보안: 비밀번호는 config.yaml에 평문으로 저장하지 않고 Windows DPAPI로 암호화하여 저장한다.
    # 같은 Windows 사용자 계정에서만 복호화 가능하므로, 재실행 시 자동으로 복호화되어 사용된다.
    imap_cfg_to_save = dict(full_cfg.get("imap", {}))
    plain_password = imap_cfg_to_save.pop("password", "")
    if plain_password:
        try:
            imap_cfg_to_save["password_encrypted"] = encrypt_password(plain_password)
        except Exception as e:
            logger.error("비밀번호 암호화 실패: %s", e, exc_info=True)
            print(f"[Error] 비밀번호 암호화 실패: {e}")
            sys.exit(1)
    cfg["imap"] = imap_cfg_to_save
    cfg["poll_interval_seconds"] = full_cfg.get("poll_interval_seconds", 300)
    cfg["remind_interval_seconds"] = full_cfg.get("remind_interval_seconds", 1800)
    cfg["webmail_url"] = full_cfg.get("webmail_url", "")
    cfg["log_level"] = full_cfg.get("log_level", "INFO")
    
    try:                
        # install_date는 EmailNotifier.__init__에서만 기록한다 (단일 책임).
        # 여기서 먼저 기록하면 _is_first_run 판단이 어긋나므로 손대지 않는다.
        with open(cfg_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f, default_flow_style=False, allow_unicode=True)
        print(f"[Info] 설정 파일이 저장되었습니다: {cfg_path}")
        logger.info("Config saved to %s", cfg_path)
    except Exception as e:
        logger.error("Failed to write config file %s", cfg_path, exc_info=True)
        print(f"[Error] 설정 파일 저장 실패: {e}")
        sys.exit(1)

def _show_settings_dialog(notifier: EmailNotifier | None = None, first_run: bool = False) -> bool:
    """Display a Tkinter window to configure IMAP settings.
    Returns True when the configuration is saved.
    """
    cfg_path = BASE_PATH / "config.yaml"
    current_cfg = {}
    if cfg_path.is_file():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                current_cfg = yaml.safe_load(f) or {}
        except Exception:
            current_cfg = {}
    imap_cfg = current_cfg.get("imap", {})

    root = tk.Tk()
    root.title("Email Notifier 설정")
    root.geometry("400x410")

    labels = ["IMAP 서버 주소", "IMAP 포트 (기본 993)", "IMAP 아이디", "IMAP 비밀번호", "SSL 사용 (Y/N)", "폴더 (INBOX 등)", "폴링 주기(초)", "재알림 주기(초)", "웹메일 주소 (URL)", "로그 레벨"]
    entries = {}
    row = 0
    from tkinter import ttk

    WEBMAIL_PLACEHOLDER = "예: https://mail.example.com"
    
    for label in labels:
        tk.Label(root, text=label).grid(row=row, column=0, sticky="e", padx=5, pady=5)
        if label == "로그 레벨":
            combo = ttk.Combobox(root, values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], state="readonly", width=27)
            combo.grid(row=row, column=1, padx=5, pady=5)
            entries[label] = combo
        else:
            e = tk.Entry(root, width=30, show="*" if "비밀번호" in label else None)
            e.grid(row=row, column=1, padx=5, pady=5)
            entries[label] = e
        row += 1

    # 웹메일 주소 입력창에 placeholder(예시 텍스트) 동작 적용.
    # https:// 또는 http://를 빠뜨리는 실수를 방지하기 위한 안내 표시.
    webmail_entry = entries["웹메일 주소 (URL)"]

    def _set_webmail_placeholder():
        if not webmail_entry.get():
            webmail_entry.insert(0, WEBMAIL_PLACEHOLDER)
            webmail_entry.config(fg="gray")

    def _clear_webmail_placeholder(event=None):
        if webmail_entry.get() == WEBMAIL_PLACEHOLDER:
            webmail_entry.delete(0, tk.END)
            webmail_entry.config(fg="black")

    def _restore_webmail_placeholder(event=None):
        if not webmail_entry.get():
            _set_webmail_placeholder()

    webmail_entry.bind("<FocusIn>", _clear_webmail_placeholder)
    webmail_entry.bind("<FocusOut>", _restore_webmail_placeholder)       

    # Pre‑fill values if they exist
    entries["IMAP 서버 주소"].insert(0, imap_cfg.get("host", ""))
    entries["IMAP 포트 (기본 993)"].insert(0, str(imap_cfg.get("port", 993)))
    entries["IMAP 아이디"].insert(0, imap_cfg.get("username", ""))
    # 저장된 암호화 비밀번호가 있으면 복호화해서 미리 채워줌 (DPAPI, 같은 Windows 계정에서만 성공)
    encrypted_pw = imap_cfg.get("password_encrypted")
    if encrypted_pw:
        try:
            entries["IMAP 비밀번호"].insert(0, decrypt_password(encrypted_pw))
        except Exception as e:
            logger.warning("저장된 비밀번호 복호화 실패: %s", e)
            entries["IMAP 비밀번호"].insert(0, "")
    else:
        entries["IMAP 비밀번호"].insert(0, "")
    entries["SSL 사용 (Y/N)"].insert(0, "Y" if imap_cfg.get("ssl", True) else "N")
    entries["폴더 (INBOX 등)"].insert(0, imap_cfg.get("folder", "INBOX"))
    entries["폴링 주기(초)"].insert(0, str(current_cfg.get("poll_interval_seconds", 10)))
    entries["재알림 주기(초)"].insert(0, str(current_cfg.get("remind_interval_seconds", 30)))
    saved_webmail_url = current_cfg.get("webmail_url", "")
    if saved_webmail_url:
        webmail_entry.insert(0, saved_webmail_url)
        webmail_entry.config(fg="black")
    else:
        _set_webmail_placeholder()
    
    # Pre-select log level combobox
    saved_level = current_cfg.get("log_level", "INFO")
    if saved_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        saved_level = "INFO"
    entries["로그 레벨"].set(saved_level)

    test_btn = tk.Button(root, text="연결 테스트", width=15)
    test_btn.grid(row=row, column=0, padx=5, pady=10)
    save_btn = tk.Button(root, text="저장", state="disabled", width=15)
    save_btn.grid(row=row, column=1, padx=5, pady=10)
    row += 1

    def test_connection():
        host = entries["IMAP 서버 주소"].get().strip()
        try:
            port = int(entries["IMAP 포트 (기본 993)"].get().strip() or 993)
        except ValueError:
            messagebox.showerror("오류", "포트는 숫자여야 합니다.")
            return
        username = entries["IMAP 아이디"].get().strip()
        password = entries["IMAP 비밀번호"].get().strip()
        ssl = entries["SSL 사용 (Y/N)"].get().strip().lower().startswith('y')
        folder = entries["폴더 (INBOX 등)"].get().strip() or "INBOX"
        try:
            client = IMAPClient(host, port=port, ssl=ssl)
            client.login(username, password)
            client.select_folder(folder)
            client.logout()
            messagebox.showinfo("성공", "IMAP 연결에 성공했습니다.")
            save_btn.config(state="normal")
        except Exception as e:
            logger.error("IMAP 연결 테스트 실패", exc_info=True)
            messagebox.showerror("연결 실패", f"{e}")

    test_btn.config(command=test_connection)

    def save_config():
        password_value = entries["IMAP 비밀번호"].get().strip()
        if not password_value:
            messagebox.showerror("오류", "IMAP 비밀번호를 입력해주세요.")
            return
        
        webmail_url_value = entries["웹메일 주소 (URL)"].get().strip()
        if webmail_url_value == WEBMAIL_PLACEHOLDER:
            webmail_url_value = ""

        full_cfg = {
            "imap": {
                "host": entries["IMAP 서버 주소"].get().strip(),
                "port": int(entries["IMAP 포트 (기본 993)"].get().strip() or 993),
                "username": entries["IMAP 아이디"].get().strip(),
                "password": password_value,
                "ssl": entries["SSL 사용 (Y/N)"].get().strip().lower().startswith('y'),
                "folder": entries["폴더 (INBOX 등)"].get().strip() or "INBOX",
            },
            "poll_interval_seconds": int(entries["폴링 주기(초)"].get().strip() or 300),
            "remind_interval_seconds": int(entries["재알림 주기(초)"].get().strip() or 1800),
            "webmail_url": webmail_url_value,
            "log_level": entries["로그 레벨"].get(),
        }
        _write_config(full_cfg)
        
        # Apply updated log level to main logger
        new_level_str = full_cfg["log_level"]
        new_level = getattr(logging, new_level_str, logging.INFO)
        logger.setLevel(new_level)

        if first_run:
            # Show welcome toast
            success = notifier_mod.show_simple_toast(
                "설치 완료", "환영합니다! 메일 알림을 시작합니다.", logger=logger
            )
            if not success:
                logger.warning("설치 완료 환영 알림 표시 실패")

        if notifier:
            # Reload config in running notifier
            notifier.config = notifier._load_config(BASE_PATH / "config.yaml")
            # 파일에는 password_encrypted만 저장되므로, 방금 입력받은 평문 비밀번호를 메모리에 채워준다.
            notifier.config.setdefault('imap', {})
            notifier.config['imap']['password'] = password_value
            notifier._install_date_dt = __import__('datetime').datetime.fromisoformat(notifier.config.get('install_date'))
            # Apply updated log level to notifier logger
            notifier.logger.setLevel(new_level)
            logger.info("Notifier configuration and log level reloaded via settings dialog")
        root.destroy()

    save_btn.config(command=save_config)
    root.protocol("WM_DELETE_WINDOW", lambda: root.destroy())
    root.mainloop()
    return True

def _run_notifier(cfg_path: pathlib.Path) -> tuple[EmailNotifier, threading.Thread]:
    """Start EmailNotifier in a background thread."""
    notifier = EmailNotifier(cfg_path)
    thread = threading.Thread(target=notifier.run, daemon=True)
    thread.start()
    return notifier, thread

# def _create_image():
#     """Create a simple square icon for the tray."""
def _create_image(bg_color=(30, 144, 255)):    
    """Create a simple square icon for the tray.
    bg_color: 정상 시 DodgerBlue(파란색), 연결 끊김 시 빨간색 등으로 전달."""
    size = (64, 64)
    # image = Image.new('RGB', size, (30, 144, 255))  # DodgerBlue
    image = Image.new('RGB', size, bg_color)
    draw = ImageDraw.Draw(image)
    draw.rectangle([16, 20, 48, 44], outline="white", width=2)
    draw.line([16, 20, 32, 34], fill="white", width=2)
    draw.line([48, 20, 32, 34], fill="white", width=2)
    return image

def _open_settings(notifier: EmailNotifier):
    """Open settings dialog from tray menu."""
    try:
        logger.info("Opening settings dialog from tray")
        _show_settings_dialog(notifier=notifier, first_run=False)
    except Exception as e:
        logger.error("Error in settings dialog", exc_info=True)
        print(f"[Error] Settings update failed: {e}")

def _view_logs():
    """Open a PowerShell window to view the logs in real-time."""
    log_path = BASE_PATH / "logs" / "email_notifier.log"
    if not log_path.exists():
        messagebox.showinfo("알림", "아직 로그 파일이 생성되지 않았습니다.")
        return
    try:
        # PowerShell에서 UTF-8 로그 파일을 깨짐 없이 출력하도록 인코딩 설정 추가
        cmd = f"powershell -NoProfile -Command \"[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; Get-Content -Path '{log_path}' -Wait -Tail 20 -Encoding utf8\""
        subprocess.Popen(f"start {cmd}", shell=True)
    except Exception as e:
        logger.error("Failed to open logs", exc_info=True)

def _open_webmail():
    cfg_path = BASE_PATH / "config.yaml"
    url = ""
    if cfg_path.is_file():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
                url = cfg.get("webmail_url", "").strip()
        except Exception:
            pass
    if url:
        import webbrowser
        webbrowser.open(url)
    else:
        messagebox.showinfo("알림", "Settings 메뉴에서 '웹메일 주소 (URL)'를 먼저 입력해주세요.")

# def _run_tray(notifier: EmailNotifier):
def _run_tray(notifier: EmailNotifier, notifier_thread: threading.Thread):
    """Run system tray icon with Settings and Exit menu items."""

    def _on_exit(icon):
         icon.stop()
         notifier.stop()
         # 진행 중인 IMAP 작업이 안전하게 마무리되도록 최대 10초간 대기 (graceful shutdown)
         notifier_thread.join(timeout=10)
         if notifier_thread.is_alive():
            logger.warning("Notifier thread가 10초 내에 종료되지 않았습니다. 강제 종료합니다.")

    menu = pystray.Menu(
        Item('Settings', lambda _: _open_settings(notifier)),
        Item('View Logs', lambda _: _view_logs()),
        Item('웹메일 열기 (Open Webmail)', lambda _: _open_webmail()),
        # Item('Exit', lambda icon: (icon.stop(), notifier.stop()))
        Item('Exit', lambda icon: _on_exit(icon))
    )
    icon = pystray.Icon('EmailNotifier', _create_image(), 'Email Notifier', menu)
    notifier.tray_icon = icon

    def _watch_connection_health():
        """연결 상태(notifier.is_connection_healthy)를 주기적으로 확인하여
        끊김 시 빨간색, 정상 시 파란색으로 트레이 아이콘을 갱신."""
        last_state = True
        while notifier_thread.is_alive():
            try:
                current_state = notifier.is_connection_healthy
                if current_state != last_state:
                    icon.icon = _create_image((220, 53, 69) if not current_state else (30, 144, 255))
                    last_state = current_state
            except Exception:
                pass
            time.sleep(5)
 
    health_watch_thread = threading.Thread(target=_watch_connection_health, daemon=True)
    health_watch_thread.start()

    # icon.run()
    icon.run()  # (3번에서 이 줄 앞에 watch thread 추가됨, 아래 참고)



def main() -> None:
    """프로그램 진입점 – 최초 실행 시 설정 파일이 없으면 설정 창을 표시하고, 이후 알림을 실행한다."""
    try:
        # Prevent multiple instances
        if not acquire_instance_lock():
            print('[Error] 이미 실행 중인 인스턴스가 있습니다. 프로그램을 종료합니다.')
            sys.exit(1)
            
        cfg_path = BASE_PATH / "config.yaml"
        is_first_run = not cfg_path.is_file()
        
        if is_first_run:
            _show_settings_dialog(first_run=True)
            
        if not cfg_path.is_file():
            print('[Info] 설정이 저장되지 않았습니다. 프로그램을 종료합니다.')
            sys.exit(0)
            
        # Run notifier with the (new or existing) config
        # notifier, _ = _run_notifier(cfg_path)
        # _run_tray(notifier)
        notifier, notifier_thread = _run_notifier(cfg_path)
        _run_tray(notifier, notifier_thread)
    except Exception as e:
        logger.error("Fatal error in main: %s", e, exc_info=True)
        print(f"[Error] {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
