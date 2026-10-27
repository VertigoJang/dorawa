"""Dorawa 서버 저장소. 1차는 SQLite로 단순하게.
나중에 미니 PC/클라우드 어디로 옮겨도 파일 하나만 들고 가면 된다.
"""
import os
import sqlite3
import secrets
import time

DB_PATH = os.environ.get("DORAWA_DB", os.path.join(os.path.dirname(__file__), "data", "dorawa.db"))


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init():
    c = _conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE,              -- 한 이메일당 한 계정 (중복 방지)
        pw_hash TEXT NOT NULL,
        verified INTEGER DEFAULT 0,     -- 이메일 인증 완료 여부
        verify_code TEXT DEFAULT '',    -- 인증용 6자리
        verify_expires REAL DEFAULT 0,
        created REAL
    );
    CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY,
        user_id INTEGER NOT NULL,
        name TEXT,
        secret TEXT UNIQUE NOT NULL,   -- 노트북이 가지는 기기 전용 키
        lost INTEGER DEFAULT 0,        -- 도난 깃발
        camera_mode TEXT DEFAULT 'remote',  -- remote(원격만) | auto(주기 자동)
        auto_interval INTEGER DEFAULT 5,    -- auto 모드 촬영 주기(분)
        pending_cmd TEXT DEFAULT '',        -- 대기 명령: '' | photo | video
        created REAL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS pair_codes (
        code TEXT PRIMARY KEY,         -- 6자리 페어링 코드
        user_id INTEGER NOT NULL,
        expires REAL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS api_tokens (
        token TEXT PRIMARY KEY,        -- 앱(PC/폰)이 쓰는 로그인 토큰
        user_id INTEGER NOT NULL,
        created REAL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY,
        device_id INTEGER NOT NULL,
        ts REAL,
        public_ip TEXT,
        ip_desc TEXT,
        wifi_ssid TEXT,
        lat REAL, lng REAL, accuracy REAL,
        photo TEXT,                    -- 저장된 사진 파일명 (없으면 NULL)
        video TEXT,                    -- 저장된 영상 파일명 (없으면 NULL)
        raw TEXT,                      -- 원본 전체 (주변 AP 목록 등)
        FOREIGN KEY(device_id) REFERENCES devices(id)
    );
    """)
    # 기존 DB에 새 컬럼 보충 (이미 운영 중인 서버 대응)
    for table, col, decl in [
        ("devices", "camera_mode", "TEXT DEFAULT 'remote'"),
        ("devices", "auto_interval", "INTEGER DEFAULT 5"),
        ("devices", "pending_cmd", "TEXT DEFAULT ''"),
        ("reports", "video", "TEXT"),
        ("users", "email", "TEXT"),
        ("users", "verified", "INTEGER DEFAULT 0"),
        ("users", "verify_code", "TEXT DEFAULT ''"),
        ("users", "verify_expires", "REAL DEFAULT 0"),
        ("users", "reset_code", "TEXT DEFAULT ''"),
        ("users", "reset_expires", "REAL DEFAULT 0"),
    ]:
        cols = [r["name"] for r in c.execute("PRAGMA table_info(%s)" % table).fetchall()]
        if col not in cols:
            c.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, col, decl))
    c.commit()
    c.close()


# --- 사용자 ---
def create_user(username, email, pw_hash, code, ttl=1800):
    """미인증 상태로 생성. 인증코드와 만료시각 저장."""
    c = _conn()
    try:
        cur = c.execute(
            """INSERT INTO users(username, email, pw_hash, verified, verify_code,
               verify_expires, created) VALUES(?,?,?,0,?,?,?)""",
            (username, email, pw_hash, code, time.time() + ttl, time.time()))
        c.commit()
        return cur.lastrowid
    finally:
        c.close()


def get_user(username):
    c = _conn()
    try:
        return c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    finally:
        c.close()


def get_user_by_email(email):
    c = _conn()
    try:
        return c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    finally:
        c.close()


def verify_user(username, code):
    """코드가 맞고 안 만료됐으면 verified=1. 결과 bool."""
    c = _conn()
    try:
        row = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not row or row["verified"]:
            return bool(row and row["verified"])
        if row["verify_code"] != code or row["verify_expires"] < time.time():
            return False
        c.execute("UPDATE users SET verified=1, verify_code='' WHERE id=?", (row["id"],))
        c.commit()
        return True
    finally:
        c.close()


def refresh_verify_code(username, code, ttl=1800):
    c = _conn()
    try:
        c.execute("UPDATE users SET verify_code=?, verify_expires=? WHERE username=?",
                  (code, time.time() + ttl, username))
        c.commit()
    finally:
        c.close()


# --- 비밀번호 재설정 ---
def set_reset_code(email, code, ttl=1800):
    """이메일로 재설정 코드 저장. 해당 이메일 계정이 있으면 True."""
    c = _conn()
    try:
        row = c.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if not row:
            return False
        c.execute("UPDATE users SET reset_code=?, reset_expires=? WHERE id=?",
                  (code, time.time() + ttl, row["id"]))
        c.commit()
        return True
    finally:
        c.close()


def reset_password(email, code, new_hash):
    """코드가 맞고 안 만료됐으면 비번 변경. 결과 bool."""
    c = _conn()
    try:
        row = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if not row or not row["reset_code"]:
            return False
        if row["reset_code"] != code or row["reset_expires"] < time.time():
            return False
        # 비번 재설정 시 이메일 인증도 완료 처리(어차피 메일 수신 확인됨)
        c.execute("UPDATE users SET pw_hash=?, reset_code='', verified=1 WHERE id=?",
                  (new_hash, row["id"]))
        c.commit()
        return True
    finally:
        c.close()


# --- 페어링 ---
def make_pair_code(user_id, ttl=600):
    code = "".join(secrets.choice("0123456789") for _ in range(6))
    c = _conn()
    try:
        c.execute("INSERT OR REPLACE INTO pair_codes(code, user_id, expires) VALUES(?,?,?)",
                  (code, user_id, time.time() + ttl))
        c.commit()
        return code
    finally:
        c.close()


def redeem_pair_code(code, device_name):
    """6자리 코드를 기기 전용 secret으로 교환. 성공 시 secret 문자열."""
    c = _conn()
    try:
        row = c.execute("SELECT * FROM pair_codes WHERE code=?", (code,)).fetchone()
        if not row or row["expires"] < time.time():
            return None
        secret = secrets.token_urlsafe(32)
        c.execute("INSERT INTO devices(user_id, name, secret, created) VALUES(?,?,?,?)",
                  (row["user_id"], device_name, secret, time.time()))
        c.execute("DELETE FROM pair_codes WHERE code=?", (code,))
        c.commit()
        return secret
    finally:
        c.close()


# --- 기기 ---
def device_by_secret(secret):
    c = _conn()
    try:
        return c.execute("SELECT * FROM devices WHERE secret=?", (secret,)).fetchone()
    finally:
        c.close()


def devices_of_user(user_id):
    c = _conn()
    try:
        return c.execute("SELECT * FROM devices WHERE user_id=? ORDER BY id", (user_id,)).fetchall()
    finally:
        c.close()


def set_lost(device_id, lost):
    c = _conn()
    try:
        c.execute("UPDATE devices SET lost=? WHERE id=?", (1 if lost else 0, device_id))
        c.commit()
    finally:
        c.close()


def set_camera_mode(device_id, mode, interval):
    c = _conn()
    try:
        c.execute("UPDATE devices SET camera_mode=?, auto_interval=? WHERE id=?",
                  (mode, interval, device_id))
        c.commit()
    finally:
        c.close()


def queue_cmd(device_id, cmd):
    """원격 촬영 명령 예약: photo | video."""
    c = _conn()
    try:
        c.execute("UPDATE devices SET pending_cmd=? WHERE id=?", (cmd, device_id))
        c.commit()
    finally:
        c.close()


def take_cmd(device_id):
    """대기 명령을 읽고 비운다(한 번만 수행되도록)."""
    c = _conn()
    try:
        row = c.execute("SELECT pending_cmd FROM devices WHERE id=?", (device_id,)).fetchone()
        cmd = row["pending_cmd"] if row else ""
        if cmd:
            c.execute("UPDATE devices SET pending_cmd='' WHERE id=?", (device_id,))
            c.commit()
        return cmd
    finally:
        c.close()


# --- 보고 ---
def add_report(device_id, d):
    c = _conn()
    try:
        c.execute("""INSERT INTO reports(device_id, ts, public_ip, ip_desc, wifi_ssid,
                     lat, lng, accuracy, photo, video, raw) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                  (device_id, time.time(), d.get("public_ip"), d.get("ip_desc"),
                   d.get("wifi_ssid"), d.get("lat"), d.get("lng"), d.get("accuracy"),
                   d.get("photo"), d.get("video"), d.get("raw")))
        c.commit()
    finally:
        c.close()


def recent_reports(device_id, limit=50):
    c = _conn()
    try:
        return c.execute("SELECT * FROM reports WHERE device_id=? ORDER BY id DESC LIMIT ?",
                         (device_id, limit)).fetchall()
    finally:
        c.close()


# --- API 토큰 (PC/폰 앱 로그인) ---
def issue_token(user_id):
    import secrets as _s
    tok = _s.token_urlsafe(32)
    c = _conn()
    try:
        c.execute("INSERT INTO api_tokens(token, user_id, created) VALUES(?,?,?)",
                  (tok, user_id, time.time()))
        c.commit()
        return tok
    finally:
        c.close()


def user_by_token(token):
    c = _conn()
    try:
        row = c.execute("SELECT user_id FROM api_tokens WHERE token=?", (token,)).fetchone()
        return row["user_id"] if row else None
    finally:
        c.close()


def revoke_token(token):
    c = _conn()
    try:
        c.execute("DELETE FROM api_tokens WHERE token=?", (token,))
        c.commit()
    finally:
        c.close()


def device_of_user(user_id, device_id):
    c = _conn()
    try:
        return c.execute("SELECT * FROM devices WHERE id=? AND user_id=?",
                         (device_id, user_id)).fetchone()
    finally:
        c.close()
