import json
import getpass
import time
import logging
import os
import tempfile
from pathlib import Path
import pathlib
import sys

import yaml
from imapclient import IMAPClient
try:
    from bs4 import BeautifulSoup
except Exception:
    class BeautifulSoup:
        def __init__(self, html, parser=None):
            self.html = html
        def get_text(self, separator=" "):
            # Simple fallback: return raw html stripped of tags (very naive)
            import re
            text = re.sub(r'<[^>]+>', '', self.html)
            return text
try:
    from winotify import Notification
    _WINOTIFY_AVAILABLE = True
except Exception:
    _WINOTIFY_AVAILABLE = False

try:
    from PIL import Image, ImageDraw
    _PIL_AVAILABLE = True
except Exception:
    _PIL_AVAILABLE = False


def _get_or_create_toast_icon_path() -> str:
    """winotify 알림에 사용할 앱 아이콘 PNG를 생성(최초 1회)하고 절대경로를 반환.
    main.py의 트레이 아이콘과 동일한 디자인(파란 사각형 + 체크 모양)을 사용한다."""
    if not _PIL_AVAILABLE:
        return ""
    icon_path = Path(tempfile.gettempdir()) / "email_notifier_toast_icon.png"
    if not icon_path.is_file():
        try:
            size = (256, 256)
            image = Image.new('RGB', size, (30, 144, 255))  # DodgerBlue
            draw = ImageDraw.Draw(image)
            draw.rectangle([64, 80, 192, 176], outline="white", width=8)
            draw.line([64, 80, 128, 136], fill="white", width=8)
            draw.line([192, 80, 128, 136], fill="white", width=8)
            image.save(icon_path, "PNG")
        except Exception:
            return ""
    return str(icon_path)

def show_simple_toast(title: str, msg: str, logger=None) -> bool:
    """EmailNotifier 인스턴스 없이도 호출 가능한 범용 winotify 알림 함수.
    설치 완료 환영 메시지 등 단발성 알림에 사용. 성공 시 True 반환."""
    if not _WINOTIFY_AVAILABLE:
        if logger:
            logger.warning("winotify를 사용할 수 없어 알림을 표시하지 못했습니다: %s", title)
        return False
    try:
        icon_path = _get_or_create_toast_icon_path()
        toast = Notification(
            app_id="Email Notifier",
            title=title,
            msg=msg,
            duration="short",
            icon=icon_path,
        )
        toast.show()
        return True
    except Exception as e:
        if logger:
            logger.error("Toast notification failed: %s", e)
        return False    

from email import policy, message_from_bytes

import base64
try:
    import win32crypt
    _DPAPI_AVAILABLE = True
except Exception:
    _DPAPI_AVAILABLE = False


def encrypt_password(plain_text: str) -> str:
    """Windows DPAPI로 비밀번호를 암호화하여 base64 문자열로 반환.
    같은 Windows 사용자 계정에서만 복호화 가능하다."""
    if not plain_text:
        return ""
    if not _DPAPI_AVAILABLE:
        # DPAPI를 사용할 수 없는 환경(비Windows)에서는 암호화 없이 그대로 반환하지 않고
        # 예외를 발생시켜 호출 측에서 인지하도록 한다.
        raise RuntimeError("win32crypt 모듈을 사용할 수 없어 비밀번호를 암호화할 수 없습니다.")
    encrypted_bytes = win32crypt.CryptProtectData(
        plain_text.encode("utf-8"), None, None, None, None, 0
    )
    return base64.b64encode(encrypted_bytes).decode("ascii")


def decrypt_password(encrypted_b64: str) -> str:
    """encrypt_password로 암호화된 base64 문자열을 복호화하여 평문 반환."""
    if not encrypted_b64:
        return ""
    if not _DPAPI_AVAILABLE:
        raise RuntimeError("win32crypt 모듈을 사용할 수 없어 비밀번호를 복호화할 수 없습니다.")
    encrypted_bytes = base64.b64decode(encrypted_b64)
    _, decrypted_bytes = win32crypt.CryptUnprotectData(
        encrypted_bytes, None, None, None, 0
    )
    return decrypted_bytes.decode("utf-8")


from email.header import decode_header

def safe_decode_header(header_value) -> str:
    if not header_value:
        return ""
    try:
        decoded_parts = decode_header(header_value)
        result_parts = []
        for text, charset in decoded_parts:
            if isinstance(text, bytes):
                if charset:
                    try:
                        result_parts.append(text.decode(charset, errors="replace"))
                    except Exception:
                        result_parts.append(text.decode("utf-8", errors="replace"))
                else:
                    result_parts.append(text.decode("utf-8", errors="replace"))
            else:
                result_parts.append(str(text))
        return "".join(result_parts)
    except Exception:
        return str(header_value)

class EmailNotifier:
    def __init__(self, config_path: Path):
        # Setup logger (writes to project logs directory)
        self.logger = logging.getLogger("EmailNotifier")
        
        if getattr(sys, 'frozen', False):
            base_path = Path(sys.executable).parent
        else:
            base_path = Path(__file__).resolve().parent
            
        log_dir = base_path / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "email_notifier.log"
        handler = logging.FileHandler(log_file, encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        if not self.logger.handlers:
            self.logger.addHandler(handler)
        
        self.config = self._load_config(config_path)
        
        # Apply configured log level
        level_str = self.config.get("log_level", "INFO")
        level = getattr(logging, level_str, logging.INFO)
        self.logger.setLevel(level)
        
        self.logger.info("Initializing EmailNotifier with config %s (log level: %s)", config_path, level_str)
        self.config.setdefault('imap', {})

        # 비밀번호 처리: DPAPI로 암호화된 값이 있으면 복호화하여 사용
        encrypted_pw = self.config['imap'].get('password_encrypted')
        plain_pw = self.config['imap'].get('password')  # 과거 버전의 평문 저장값 (있다면 호환용)
        need_resave = False

        if encrypted_pw:
            try:
                self.config['imap']['password'] = decrypt_password(encrypted_pw)
                self.logger.info("IMAP password decrypted via Windows DPAPI")
            except Exception as e:
                self.logger.error("저장된 비밀번호 복호화 실패 (다른 PC/계정에서 복사된 설정일 수 있음): %s", e)
                self.config['imap']['password'] = None
        elif plain_pw:
            # 과거 버전에서 평문으로 저장된 비밀번호가 남아있는 경우: 그대로 사용하고 암호화 형태로 재저장
            self.logger.warning("config.yaml에 평문 비밀번호가 발견됨. 암호화된 형태로 재저장합니다.")
            need_resave = True

        if not self.config['imap'].get('password'):
            self.config['imap']['password'] = getpass.getpass('IMAP 비밀번호를 입력하세요: ')
            need_resave = True

        # 비밀번호를 (재)암호화하여 파일에 저장, 평문 password 키는 파일에 남기지 않음
        if need_resave:
            try:
                self.config['imap']['password_encrypted'] = encrypt_password(self.config['imap']['password'])
                self._save_config_excluding_password(config_path)
                self.logger.info("IMAP password encrypted and saved via Windows DPAPI")
            except Exception as e:
                self.logger.error("비밀번호 암호화 저장 실패 (다음 실행 시 다시 입력 필요): %s", e)

        # 최초 실행 시 설치 날짜 기록 (ISO date)
        self._is_first_run = not self.config.get('install_date')

        self.logger.debug("[DIAG] _is_first_run initialized to %s (install_date in config: %r)",
                          self._is_first_run, self.config.get('install_date'))

        if self._is_first_run:
            from datetime import datetime
            self.config['install_date'] = datetime.now().date().isoformat()
            self.logger.info("Install date recorded: %s", self.config['install_date'])
            try:
                self._save_config_excluding_password(config_path)
                print(f"[Info] 설치 날짜가 기록되었습니다: {self.config['install_date']}")
            except Exception as e:
                print(f"[Warning] 설치 날짜 기록 실패: {e}")
        
        self.seen_ids_file = base_path / "seen_ids.json"
       
        # Duplicate init block removed
        self.seen_ids = self._load_seen_ids()
        self.remind_queue = {}
        # 설치 날짜를 datetime 객체로 보관해 빠른 비교에 사용
        from datetime import datetime
        self._install_date_dt = datetime.fromisoformat(self.config['install_date'])
        # control flag for graceful shutdown
        self._running = True
        
    def stop(self) -> None:
        """Signal the notifier loop to stop gracefully."""
        self.logger.info("Stopping EmailNotifier loop")
        self._running = False

    def _save_config_excluding_password(self, config_path: Path) -> None:
        """self.config를 파일에 저장하되, 평문 'password' 키는 절대 기록하지 않는다.
        'password_encrypted'(DPAPI 암호화 값)만 저장된다."""
        cfg_to_save = dict(self.config)
        imap_cfg = dict(cfg_to_save.get('imap', {}))
        imap_cfg.pop('password', None)  # 평문 비밀번호는 파일에 저장하지 않음
        cfg_to_save['imap'] = imap_cfg
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg_to_save, f, default_flow_style=False, allow_unicode=True)

    def _load_config(self, path: Path) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    # def _load_seen_ids(self) -> set:
    #     if self.seen_ids_file.is_file():
    #         with open(self.seen_ids_file, "r", encoding="utf-8") as f:
    #             return set(json.load(f))
    #     return set()

    # def _save_seen_ids(self):
    #     with open(self.seen_ids_file, "w", encoding="utf-8") as f:
    #         json.dump(list(self.seen_ids), f, ensure_ascii=False, indent=2)

    def _load_seen_ids(self) -> set:
        if not self.seen_ids_file.is_file():
            return set()
        try:
            with open(self.seen_ids_file, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except (json.JSONDecodeError, ValueError, OSError) as e:
            # 파일이 손상된 경우: 손상된 파일을 백업해두고 빈 상태로 새로 시작 (프로그램 시작 불가 방지)
            self.logger.error(
                "seen_ids.json 파일이 손상되어 읽을 수 없습니다 (%s). 빈 목록으로 새로 시작합니다.", e
            )
            try:
                backup_path = self.seen_ids_file.with_suffix(".json.corrupted")
                self.seen_ids_file.replace(backup_path)
                self.logger.warning("손상된 파일을 %s 로 백업했습니다.", backup_path)
            except Exception as backup_err:
                self.logger.error("손상된 seen_ids.json 백업 실패: %s", backup_err)
            return set()
 
    def _save_seen_ids(self):
        # 임시 파일에 먼저 쓰고 교체하는 방식으로, 쓰는 도중 실패해도 기존 파일이 깨지지 않도록 한다.
        tmp_path = self.seen_ids_file.with_suffix(".json.tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(list(self.seen_ids), f, ensure_ascii=False, indent=2)
            tmp_path.replace(self.seen_ids_file)
        except Exception as e:
            self.logger.error("seen_ids.json 저장 실패: %s", e)
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass    

    def _connect(self):
        self.logger.info("Connecting to IMAP server %s:%s", self.config['imap']['host'], self.config['imap']['port'])
        imap_cfg = self.config["imap"]
        client = IMAPClient(imap_cfg["host"], port=imap_cfg["port"], ssl=imap_cfg["ssl"])
        client.login(imap_cfg["username"], imap_cfg["password"])
        client.select_folder(imap_cfg["folder"])
        self.logger.info("IMAP connection established and folder selected")
        return client

    def _fetch_unseen(self, client):
        self.logger.info("Fetching unseen emails")
        uids = client.search(["UNSEEN"])
        unseen = [uid for uid in uids if uid not in self.seen_ids]
        self.logger.info("Found %d new unseen emails", len(unseen))
        return unseen

    def _parse_message(self, client, uid):
        self.logger.debug("Parsing message UID %s", uid)
        # BODY.PEEK[]를 사용하여 서버에서 읽음(Seen) 처리되는 것을 방지
        fetch_res = client.fetch([uid], [b"BODY.PEEK[]", b"INTERNALDATE"])
        if not fetch_res or uid not in fetch_res:
            self.logger.warning("Message UID %s not found on server during parsing", uid)
            return None
        raw = fetch_res[uid]
        # IMAP 응답은 PEEK로 요청해도 BODY[] 키로 데이터를 반환합니다.
        raw_bytes = raw.get(b"BODY[]") or raw.get(b"RFC822", b"")
        internal_date = raw.get(b"INTERNALDATE")
        msg = message_from_bytes(raw_bytes, policy=policy.default)
        sender = safe_decode_header(msg["From"]) or "(unknown)"
        subject = safe_decode_header(msg["Subject"]) or "(no subject)"
        # extract body text
        if msg.is_multipart():
            parts = []
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        parts.append(payload)
            body = b"".join(parts).decode(errors="ignore")
        else:
            body = msg.get_payload(decode=True).decode(errors="ignore") if msg.get_payload(decode=True) else ""
        # fallback to HTML if plain text empty
        if not body.strip():
            html = msg.get_payload(decode=True).decode(errors="ignore") if msg.get_payload(decode=True) else ""
            soup = BeautifulSoup(html, "html.parser")
            body = soup.get_text(separator=" ")
        snippet = body.strip().replace("\r", "").replace("\n", " ")
        snippet = snippet[: self.config.get("snippet_length", 200)]
        # parse email date for install‑date filtering
        from email.utils import parsedate_to_datetime
        try:
            email_dt = parsedate_to_datetime(msg["Date"]).replace(tzinfo=None)
        except Exception:
            email_dt = None
        return {"uid": uid, "sender": sender, "subject": subject, "snippet": snippet, "date": email_dt}

    def _show_toast(self, info: dict):
        self.logger.info("Showing toast for email from %s", info.get('sender'))
        
        # 알림은 받은시간 / 보낸사람 / 제목 / 내용 요약 형태로 보여줘
        received_time = info.get("date")
        if received_time:
            time_str = received_time.strftime("%Y-%m-%d %H:%M")
        else:
            time_str = "알 수 없음"

        title = "새 메일 도착"            
        sender = info.get("sender", "알 수 없는 발신자")
        subject = info.get("subject", "제목 없음")
        snippet = info.get("snippet", "")

        # PowerShell -Command 문자열에 그대로 삽입되므로, 명령어를 깨뜨릴 수 있는 문자를 안전하게 치환
        def _sanitize_for_toast(text: str) -> str:
            return (text or "").replace('"', "'").replace("`", "'").replace("$", "")

        sender = _sanitize_for_toast(sender)
        subject = _sanitize_for_toast(subject)
        snippet = _sanitize_for_toast(snippet)

        # 글자수 제한 방지
        MAX_LEN = 240  # Windows Toast 알림 제한 255자에 여유를 둠

        # 보낸사람과 제목의 길이가 너무 길면 알림 실패 및 내용 잘림이 발생하므로 자름
        if len(sender) > 60:
            sender = sender[:57] + "..."
        if len(subject) > 80:
            subject = subject[:77] + "..."

        base_msg = f"받은시간: {time_str}\n보낸사람: {sender}\n제목: {subject}\n내용: "
        remaining = MAX_LEN - len(base_msg) - len(title)

        # 남는 길이만큼만 본문(snippet) 사용, 부족하면 빈 문자열
        snippet = snippet[:remaining] if remaining > 0 else ""

        msg = f"받은시간: {time_str}\n보낸사람: {sender}\n제목: {subject}\n내용: {snippet}"

        # 웹메일 딥링크 구성: IMAP 서버 주소로 mailplug 여부를 판별하여 분기.
        # mailplug는 IMAP UID를 URL에 그대로 사용하는 특이 케이스라 정확한 딥링크 구성이 가능하지만,
        # 다른 웹메일 서비스는 내부 ID 체계가 달라 UID로 특정 메일을 열 수 없으므로 받은편지함을 연다.
        webmail_url = self.config.get("webmail_url", "").strip()
        imap_host = self.config.get("imap", {}).get("host", "").lower()
        uid = info.get("uid")
        launch_url = None

        if webmail_url:
            if "mailplug" in imap_host and uid is not None:
                launch_url = f"{webmail_url.rstrip('/')}/mail/inbox/messages/{uid}"
            else:
                launch_url = webmail_url                           

        try:
            if _WINOTIFY_AVAILABLE:
                icon_path = _get_or_create_toast_icon_path()
                self.logger.debug("[DIAG] toast launch_url=%r icon_path=%r", launch_url, icon_path)
                toast = Notification(
                    app_id="Email Notifier",
                    title=title,
                    msg=msg,
                    duration="long",
                    icon=icon_path,
                    launch=launch_url or "",
                )
                toast.show()
                self.logger.debug("[DIAG] winotify script generated:\n%s", toast.script)
            elif hasattr(self, 'tray_icon') and self.tray_icon is not None:
                # winotify를 사용할 수 없는 경우의 폴백 (클릭 시 URL 열기는 지원되지 않음)
                self.tray_icon.notify(msg, title=title)
            else:
                self.logger.warning("winotify를 사용할 수 없어 알림을 표시하지 못했습니다: %s", title)
        except Exception as e:
            self.logger.error("Toast notification failed: %s", e)

    def run(self):
        while self._running:
            # 매 루프마다 최신 설정값을 다시 읽어옴
            poll = self.config.get("poll_interval_seconds", 10)
            remind = self.config.get("remind_interval_seconds", 30)
            
            # 로그 레벨도 매 루프마다 최신 설정을 동적으로 로드 및 반영할 수 있도록 합니다. (실시간 반영 완벽화)
            level_str = self.config.get("log_level", "INFO")
            level = getattr(logging, level_str, logging.INFO)
            self.logger.setLevel(level)

            self.logger.info("Starting main loop: poll=%s sec, remind=%s sec", poll, remind)
            self.logger.info("=========================================")
            self.logger.info("Polling for new emails...")
            t_loop_start = time.time()
            try:
                t_connect_start = time.time()
                client = self._connect()
                self.logger.debug("[DIAG] _connect() took %.2f sec", time.time() - t_connect_start)
                try:
                    t_fetch_start = time.time()
                    new_uids = self._fetch_unseen(client)
                    
                    if new_uids:
                        if self._is_first_run:
                            # 최초 실행: 쌓여있는 과거 안읽음 메일은 본문 조회/알림 없이 조용히 읽음 처리만 수행 (속도 최적화)
                            self.logger.info(
                                "First run detected: %d backlog emails will be marked as seen without fetching body or notifying",
                                len(new_uids)
                            )
                            for uid in new_uids:
                                self.seen_ids.add(uid)
                            self.logger.info("First-run backlog processing complete in %.2f sec", time.time() - t_loop_start)
                            self._is_first_run = False  # 이후 루프부터는 정상 처리
                        else:
                            self.logger.info("Checking dates for %d emails to filter old messages...", len(new_uids))
                            dates_data = client.fetch(new_uids, ["INTERNALDATE"])

                            for i, uid in enumerate(new_uids, 1):
                                # INTERNALDATE로 과거 메일 필터링 (본문 다운로드 방지)
                                uid_data = dates_data.get(uid, {})
                                internal_dt = uid_data.get(b"INTERNALDATE")
                                if internal_dt is not None:
                                    naive_dt = internal_dt.replace(tzinfo=None)
                                    if naive_dt < self._install_date_dt:
                                        # 설치 이전 메일은 알림 대상이 아니므로 읽음 처리하여 다음에 또 검사하지 않음
                                        self.seen_ids.add(uid)
                                        continue

                                self.logger.info("Processing new email %d/%d (UID: %s)", i, len(new_uids), uid)
                                info = self._parse_message(client, uid)
                                if info is None:
                                    # 파싱 실패: seen_ids에 추가하지 않아 다음 루프에서 다시 시도
                                    self.logger.warning("Skipping UID %s due to parse failure; will retry next poll", uid)
                                    continue
                                # 알림 적용 기준: 설치 날짜 이후 메일만 알림
                                if info["date"] is None or info["date"] >= self._install_date_dt:
                                    self._show_toast(info)
                                    self.remind_queue[uid] = time.time() + remind
                                # 처리 완료(알림 발송 또는 의도적 스킵) 후 읽음 처리
                                self.seen_ids.add(uid)
                    # 재알림 검사: 메일을 이미 읽었거나(Seen) 삭제되었으면 알림 큐에서 제거
                    t_remind_start = time.time()
                    now = time.time()
                    if self.remind_queue:
                        self.logger.debug("[DIAG] remind_queue check start, %d item(s)", len(self.remind_queue))
                        remind_uids = list(self.remind_queue.keys())
                        try:
                            flags_data = client.fetch(remind_uids, ["FLAGS"])
                        except Exception:
                            flags_data = {}
                            
                        for uid, next_time in list(self.remind_queue.items()):
                            uid_data = flags_data.get(uid)
                            # 메일이 삭제되었거나 읽음 처리된 경우
                            if not uid_data or b"\\Seen" in uid_data.get(b"FLAGS", ()):
                                del self.remind_queue[uid]
                                continue
                                
                            if now >= next_time:
                                try:
                                    info = self._parse_message(client, uid)
                                    if info and (info["date"] is None or info["date"] >= self._install_date_dt):
                                        self._show_toast(info)
                                        self.remind_queue[uid] = now + remind
                                except Exception as e:
                                    self.logger.error("Failed to parse remind message UID %s: %s", uid, e)
                                    del self.remind_queue[uid]
                    self.logger.debug("[DIAG] remind_queue check took %.2f sec", time.time() - t_remind_start)

                    t_save_start = time.time()
                    self._save_seen_ids()
                    self.logger.debug("[DIAG] _save_seen_ids took %.2f sec", time.time() - t_save_start)
                finally:
                    t_logout_start = time.time()
                    client.logout()
                    self.logger.debug("[DIAG] client.logout() took %.2f sec", time.time() - t_logout_start)
            except Exception as e:
                self.logger.error("Run loop error: %s", e, exc_info=True)
                print(f"[Error] {e}")

            t_total = time.time() - t_loop_start
            self.logger.debug("[DIAG] Total loop processing took %.2f sec, now sleeping %s sec", t_total, poll)
            time.sleep(poll)

if __name__ == "__main__":
    # 개발 중 테스트용 진입점 (실제 서비스는 src/main.py 에서 호출)
    cfg_path = Path(__file__).parent / "config.yaml"
    EmailNotifier(cfg_path).run()