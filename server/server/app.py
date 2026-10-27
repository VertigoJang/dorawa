#!/usr/bin/env python3
"""Dorawa 서버 — Flask.

노트북용 API (기기 secret으로 인증):
  POST /api/pair        {code, name}            -> {secret}
  POST /api/report      (헤더 X-Device-Secret)  -> {lost: bool}
  GET  /api/poll        (헤더 X-Device-Secret)  -> {lost: bool}

사람용 웹 (세션 로그인):
  /register /login /logout
  /            대시보드 (기기 목록, 페어링 코드 발급)
  /device/<id> 기기 상세 (보고·사진·도난 켜기)
"""
import os
import json
import time
import hashlib
import secrets as _secrets
from functools import wraps

from flask import (Flask, request, jsonify, session, redirect,
                   url_for, render_template, send_from_directory, abort)

import db
import mailer
import events


def _gen_code():
    return "".join(_secrets.choice("0123456789") for _ in range(6))

app = Flask(__name__)
app.secret_key = os.environ.get("DORAWA_SECRET_KEY", _secrets.token_hex(32))
PHOTO_DIR = os.environ.get("DORAWA_PHOTOS", os.path.join(os.path.dirname(__file__), "data", "photos"))

db.init()
os.makedirs(PHOTO_DIR, exist_ok=True)


@app.template_filter("kst")
def kst(ts):
    """유닉스 시간 -> 'YYYY-MM-DD HH:MM:SS' (KST)."""
    from datetime import datetime, timezone, timedelta
    if not ts:
        return "-"
    dt = datetime.fromtimestamp(float(ts), tz=timezone(timedelta(hours=9)))
    return dt.strftime("%Y-%m-%d %H:%M:%S")


# --- 비밀번호 해시 (의존성 없이 표준 라이브러리) ---
def hash_pw(pw, salt=None):
    salt = salt or _secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200_000).hex()
    return "%s$%s" % (salt, h)


def check_pw(pw, stored):
    try:
        salt, _ = stored.split("$", 1)
    except ValueError:
        return False
    return hash_pw(pw, salt) == stored


# ================= 노트북용 API =================
@app.post("/api/pair")
def api_pair():
    d = request.get_json(force=True, silent=True) or {}
    code = (d.get("code") or "").strip()
    name = (d.get("name") or "laptop").strip()
    secret = db.redeem_pair_code(code, name)
    if not secret:
        return jsonify(error="invalid or expired code"), 400
    return jsonify(secret=secret)


def _device_from_header():
    s = request.headers.get("X-Device-Secret", "")
    return db.device_by_secret(s) if s else None


@app.post("/api/report")
def api_report():
    dev = _device_from_header()
    if not dev:
        return jsonify(error="unauthorized"), 401
    # 사진/영상은 multipart, 그 외는 JSON
    photo_name = video_name = None
    if request.files:
        ts = int(time.time())
        if "photo" in request.files:
            photo_name = "%d_%d.jpg" % (dev["id"], ts)
            request.files["photo"].save(os.path.join(PHOTO_DIR, photo_name))
        if "video" in request.files:
            video_name = "%d_%d.mp4" % (dev["id"], ts)
            request.files["video"].save(os.path.join(PHOTO_DIR, video_name))
        meta = json.loads(request.form.get("meta", "{}"))
    else:
        meta = request.get_json(force=True, silent=True) or {}
    meta["photo"] = photo_name
    meta["video"] = video_name
    db.add_report(dev["id"], meta)
    return jsonify(lost=bool(dev["lost"]))


@app.get("/api/poll")
def api_poll():
    dev = _device_from_header()
    if not dev:
        return jsonify(error="unauthorized"), 401
    # 롱폴링: 명령이 없고 도난 모드면, 명령이 올 때까지 최대 25초 대기
    cmd = db.take_cmd(dev["id"]) if dev["lost"] else ""
    if not cmd and dev["lost"]:
        if events.wait(dev["id"], timeout=25):
            cmd = db.take_cmd(dev["id"])
    return jsonify(lost=bool(dev["lost"]),
                   cmd=cmd,
                   camera_mode=dev["camera_mode"],
                   auto_interval=dev["auto_interval"])


# ================= 사람용 웹 =================
def login_required(f):
    @wraps(f)
    def g(*a, **k):
        if "uid" not in session:
            return redirect(url_for("login"))
        return f(*a, **k)
    return g


def _valid_email(e):
    import re
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", e))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        e = request.form.get("email", "").strip().lower()
        p = request.form.get("password", "")
        if not u or not e or not p:
            return render_template("register.html", error="모든 칸을 입력하세요")
        if not _valid_email(e):
            return render_template("register.html", error="이메일 형식이 올바르지 않습니다")
        if db.get_user(u):
            return render_template("register.html", error="이미 있는 아이디입니다")
        if db.get_user_by_email(e):
            return render_template("register.html", error="이미 가입된 이메일입니다")
        code = _gen_code()
        db.create_user(u, e, hash_pw(p), code)
        mailer.send_code(e, code)
        session["pending_user"] = u
        return redirect(url_for("verify"))
    return render_template("register.html")


@app.route("/verify", methods=["GET", "POST"])
def verify():
    u = session.get("pending_user")
    if not u:
        return redirect(url_for("register"))
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        if db.verify_user(u, code):
            row = db.get_user(u)
            session.pop("pending_user", None)
            session["uid"] = row["id"]
            session["uname"] = u
            return redirect(url_for("dashboard"))
        return render_template("verify.html", email_user=u,
                               error="코드가 틀렸거나 만료되었습니다")
    return render_template("verify.html", email_user=u)


@app.post("/verify/resend")
def verify_resend():
    u = session.get("pending_user")
    if not u:
        return redirect(url_for("register"))
    row = db.get_user(u)
    if row and not row["verified"]:
        code = _gen_code()
        db.refresh_verify_code(u, code)
        mailer.send_code(row["email"], code)
    return render_template("verify.html", email_user=u, error="새 코드를 보냈습니다")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        p = request.form.get("password", "")
        row = db.get_user(u)
        if not row or not check_pw(p, row["pw_hash"]):
            return render_template("login.html", error="아이디 또는 비밀번호가 틀렸습니다")
        if not row["verified"]:
            session["pending_user"] = u
            return redirect(url_for("verify"))
        session["uid"] = row["id"]
        session["uname"] = u
        return redirect(url_for("dashboard"))
    msg = session.pop("flash", None)
    return render_template("login.html", notice=msg)


@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    """비밀번호 찾기 1단계: 이메일 입력 → 재설정 코드 발송."""
    if request.method == "POST":
        e = request.form.get("email", "").strip().lower()
        code = _gen_code()
        # 이메일이 있든 없든 같은 메시지 (계정 존재 여부 노출 방지)
        if db.set_reset_code(e, code):
            mailer.send_reset_code(e, code)
        session["reset_email"] = e
        return redirect(url_for("reset"))
    return render_template("forgot.html")


@app.route("/reset", methods=["GET", "POST"])
def reset():
    """비밀번호 찾기 2단계: 코드 + 새 비번."""
    e = session.get("reset_email")
    if not e:
        return redirect(url_for("forgot"))
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        p = request.form.get("password", "")
        if not p:
            return render_template("reset.html", error="새 비밀번호를 입력하세요")
        if db.reset_password(e, code, hash_pw(p)):
            session.pop("reset_email", None)
            session["flash"] = "비밀번호가 변경되었습니다. 로그인하세요."
            return redirect(url_for("login"))
        return render_template("reset.html", error="코드가 틀렸거나 만료되었습니다")
    return render_template("reset.html")


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/")
@login_required
def dashboard():
    devices = db.devices_of_user(session["uid"])
    return render_template("dashboard.html", uname=session["uname"], devices=devices)


@app.post("/paircode")
@login_required
def paircode():
    code = db.make_pair_code(session["uid"])
    return jsonify(code=code)


@app.get("/device/<int:did>")
@login_required
def device(did):
    devs = {d["id"]: d for d in db.devices_of_user(session["uid"])}
    if did not in devs:
        abort(404)
    reports = db.recent_reports(did)
    return render_template("device.html", dev=devs[did], reports=reports)


def _own_device(did):
    devs = {d["id"]: d for d in db.devices_of_user(session["uid"])}
    if did not in devs:
        abort(404)
    return devs[did]


@app.post("/device/<int:did>/lost")
@login_required
def device_lost(did):
    _own_device(did)
    db.set_lost(did, request.form.get("lost") == "1")
    return redirect(url_for("device", did=did))


@app.post("/device/<int:did>/capture")
@login_required
def device_capture(did):
    """원격 촬영 명령 예약: photo 또는 video."""
    _own_device(did)
    cmd = request.form.get("cmd")
    if cmd in ("photo", "video"):
        db.queue_cmd(did, cmd)
        events.notify(did)  # 롱폴링 중인 노트북을 즉시 깨움
    return redirect(url_for("device", did=did))


@app.post("/device/<int:did>/camera_mode")
@login_required
def device_camera_mode(did):
    """촬영 모드 설정: remote 또는 auto(N분)."""
    _own_device(did)
    mode = request.form.get("mode", "remote")
    try:
        interval = max(1, int(request.form.get("interval", 5)))
    except ValueError:
        interval = 5
    db.set_camera_mode(did, "auto" if mode == "auto" else "remote", interval)
    return redirect(url_for("device", did=did))


def _media_authorized():
    """세션 로그인 또는 ?token= 로 접근 허용 (앱이 이미지 볼 때)."""
    if "uid" in session:
        return True
    tok = request.args.get("token", "")
    return bool(tok and db.user_by_token(tok))


@app.get("/photo/<name>")
def photo(name):
    if not _media_authorized():
        abort(401)
    return send_from_directory(PHOTO_DIR, os.path.basename(name))


@app.get("/video/<name>")
def video(name):
    if not _media_authorized():
        abort(401)
    return send_from_directory(PHOTO_DIR, os.path.basename(name))


# ================= 앱용 JSON API (PC/폰 앱) =================
def _api_user():
    """Authorization: Bearer <token> 로 사용자 식별. 실패 시 None."""
    auth = request.headers.get("Authorization", "")
    tok = auth[7:].strip() if auth.startswith("Bearer ") else ""
    return (db.user_by_token(tok), tok) if tok else (None, "")


def _dev_dict(d):
    return {
        "id": d["id"], "name": d["name"], "lost": bool(d["lost"]),
        "camera_mode": d["camera_mode"], "auto_interval": d["auto_interval"],
        "pending_cmd": d["pending_cmd"],
    }


@app.post("/api/app/login")
def app_login():
    d = request.get_json(force=True, silent=True) or {}
    u = (d.get("username") or "").strip()
    p = d.get("password") or ""
    row = db.get_user(u)
    if not row or not check_pw(p, row["pw_hash"]):
        return jsonify(error="아이디 또는 비밀번호가 틀렸습니다"), 401
    if not row["verified"]:
        return jsonify(error="이메일 인증이 안 된 계정입니다"), 403
    return jsonify(token=db.issue_token(row["id"]), username=u)


@app.post("/api/app/logout")
def app_logout():
    _, tok = _api_user()
    if tok:
        db.revoke_token(tok)
    return jsonify(ok=True)


@app.get("/api/app/devices")
def app_devices():
    uid, _ = _api_user()
    if not uid:
        return jsonify(error="unauthorized"), 401
    return jsonify(devices=[_dev_dict(d) for d in db.devices_of_user(uid)])


@app.post("/api/app/paircode")
def app_paircode():
    uid, _ = _api_user()
    if not uid:
        return jsonify(error="unauthorized"), 401
    return jsonify(code=db.make_pair_code(uid))


@app.get("/api/app/device/<int:did>/reports")
def app_reports(did):
    uid, tok = _api_user()
    if not uid or not db.device_of_user(uid, did):
        return jsonify(error="unauthorized"), 401
    out = []
    for r in db.recent_reports(did):
        out.append({
            "ts": r["ts"], "public_ip": r["public_ip"], "ip_desc": r["ip_desc"],
            "wifi_ssid": r["wifi_ssid"], "lat": r["lat"], "lng": r["lng"],
            "accuracy": r["accuracy"],
            "photo_url": (url_for("photo", name=r["photo"]) + "?token=" + tok) if r["photo"] else None,
            "video_url": (url_for("video", name=r["video"]) + "?token=" + tok) if r["video"] else None,
            "raw": r["raw"],
        })
    return jsonify(reports=out)


@app.post("/api/app/device/<int:did>/lost")
def app_lost(did):
    uid, _ = _api_user()
    if not uid or not db.device_of_user(uid, did):
        return jsonify(error="unauthorized"), 401
    d = request.get_json(force=True, silent=True) or {}
    db.set_lost(did, bool(d.get("lost")))
    return jsonify(ok=True)


@app.post("/api/app/device/<int:did>/capture")
def app_capture(did):
    uid, _ = _api_user()
    if not uid or not db.device_of_user(uid, did):
        return jsonify(error="unauthorized"), 401
    d = request.get_json(force=True, silent=True) or {}
    cmd = d.get("cmd")
    if cmd in ("photo", "video"):
        db.queue_cmd(did, cmd)
        events.notify(did)
    return jsonify(ok=True)


@app.post("/api/app/device/<int:did>/camera_mode")
def app_camera_mode(did):
    uid, _ = _api_user()
    if not uid or not db.device_of_user(uid, did):
        return jsonify(error="unauthorized"), 401
    d = request.get_json(force=True, silent=True) or {}
    mode = "auto" if d.get("mode") == "auto" else "remote"
    try:
        interval = max(1, int(d.get("interval", 5)))
    except (ValueError, TypeError):
        interval = 5
    db.set_camera_mode(did, mode, interval)
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
