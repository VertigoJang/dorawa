#!/usr/bin/env python3
"""Dorawa 에이전트 — 한 번 실행되고 끝나는 oneshot.
systemd 타이머가 주기적으로 호출한다.

도난 여부를 어디서 판단하느냐가 채널에 따라 다르다.
- 서버 채널: 서버가 도난 깃발을 쥐고 있다. 에이전트는 서버에 물어본다.
- 메신저 채널(ntfy): 사용자가 보낸 /lost 명령을 읽어 로컬 상태로 관리한다.
두 방식을 함께 쓸 수 있다(서버 + ntfy 동시).
"""
import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
import state
from channels import base as channel_base
from channels.server_ch import ServerChannel
from reporters import sysinfo, wifi, webcam
from reports_struct import build_struct


def handle_commands(ch):
    """메신저 채널(ntfy 등)에서 온 명령 처리."""
    for text in ch.poll_commands():
        if text == "/lost":
            state.set_lost(True)
            ch.send_text("🚨 도난 모드 켜짐 — 주기적으로 보고합니다")
        elif text == "/found":
            state.set_lost(False)
            ch.send_text("✅ 도난 모드 꺼짐")
        elif text == "/status":
            state.set_once()


def collect(cfg):
    """공통 수집: ip, 로그인 사용자, 연결 와이파이, 주변 AP, 위치."""
    ip = sysinfo.public_ip()
    wifi_ssid = sysinfo.active_wifi()
    aps = wifi.scan()
    loc = wifi.locate(aps, cfg.wifi_location, cfg.wigle_api_name, cfg.wigle_api_token)
    return ip, wifi_ssid, aps, loc


def text_report(ip, wifi_ssid, aps, loc):
    lines = [
        "📍 %s 보고 %s" % (sysinfo.hostname(), datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        "공인IP: %s (%s)" % (ip["ip"], ip["desc"]),
        "로그인 사용자: %s" % (sysinfo.logged_in_users() or "(없음)"),
        "연결된 와이파이: %s" % (wifi_ssid or "(없음)"),
    ]
    if loc:
        lat, lng, acc = loc
        lines.append("와이파이 기준 위치(오차 약 %dm): https://maps.google.com/?q=%s,%s"
                     % (int(acc), lat, lng))
    else:
        lines.append("와이파이 기준 위치: 찾지 못함 (주변 AP %d개)" % len(aps))
    return "\n".join(lines)


def capture_webcam(cfg):
    """사진을 찍어 임시 경로 반환(없으면 None). 호출자가 지울 것."""
    if not cfg.webcam_enabled:
        return None
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
        path = tf.name
    if webcam.capture(path):
        return path
    try:
        os.remove(path)
    except OSError:
        pass
    return None


def should_auto_capture(camera_mode, auto_interval):
    """auto 모드에서 지금 주기가 됐는지. state에 마지막 촬영 시각 저장."""
    if camera_mode != "auto":
        return False
    import time
    last = state.get_last_auto_shot()
    return (time.time() - last) >= auto_interval * 60 - 5  # 약간의 여유


def capture_now(cfg, kind):
    """kind: 'photo' | 'video'. (photo_path, video_path) 반환, 호출자가 지움."""
    photo = video = None
    if kind == "video":
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            vp = tf.name
        if webcam.record(vp, seconds=10):
            video = vp
        else:
            try:
                os.remove(vp)
            except OSError:
                pass
    else:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
            pp = tf.name
        if webcam.capture(pp):
            photo = pp
        else:
            try:
                os.remove(pp)
            except OSError:
                pass
    return photo, video


def do_report(cfg, server, cmd=""):
    """위치 수집 + (명령/자동에 따라) 촬영 + 서버 보고. 한 회차."""
    ip, wifi_ssid, aps, loc = collect(cfg)
    photo = video = None
    if cfg.webcam_enabled:
        if cmd == "video":
            photo, video = capture_now(cfg, "video")
        elif cmd == "photo":
            photo, video = capture_now(cfg, "photo")
        elif should_auto_capture(_camera_mode, _auto_interval):
            photo, video = capture_now(cfg, "photo")
            state.set_last_auto_shot()
    try:
        meta = build_struct(ip, wifi_ssid, loc, aps)
        if video:
            server.send_report_struct_video(meta, photo_path=photo, video_path=video)
        else:
            server.send_report_struct(meta, photo_path=photo)
    finally:
        for p in (photo, video):
            if p:
                try:
                    os.remove(p)
                except OSError:
                    pass


# 롱폴링 루프에서 최신 모드를 공유하기 위한 모듈 변수
_camera_mode = "remote"
_auto_interval = 5


def main():
    """타이머가 1분마다 부른다.
    - 평상시: poll 한 번 하고 도난 아니면 즉시 종료.
    - 도난 모드: 이 프로세스 안에서 롱폴링 루프를 돌며 명령에 즉시 반응.
      (다음 타이머 실행과 겹치지 않게, 약 55초만 돌고 종료 → 타이머가 곧 다시 띄움)
    """
    global _camera_mode, _auto_interval
    import time
    cfg = Config()
    server = ServerChannel(cfg)
    if not server.alive():
        return

    st = server.poll_status()
    if st is None or not st["lost"]:
        return  # 서버 못 닿거나 평상시면 종료

    _camera_mode = st["camera_mode"]
    _auto_interval = st["auto_interval"]

    deadline = time.time() + 55          # 이 프로세스는 최대 55초 돌고 종료
    last_location = 0                    # 위치 보고 주기 관리 (초)
    LOC_EVERY = 60                       # 위치는 1분에 한 번

    # 진입 시 명령이 이미 있으면 처리, 없으면 위치 1회 보고
    if st["cmd"]:
        do_report(cfg, server, cmd=st["cmd"])
    else:
        do_report(cfg, server)
    last_location = time.time()

    # 롱폴링 루프: 명령이 오면 즉시 촬영, 없으면 주기적으로 위치만
    while time.time() < deadline:
        st = server.poll_status()        # 서버가 최대 25초 대기(롱폴링)
        if st is None:
            time.sleep(3)
            continue
        if not st["lost"]:
            break                        # 도난 해제되면 종료
        _camera_mode = st["camera_mode"]
        _auto_interval = st["auto_interval"]
        if st["cmd"]:
            do_report(cfg, server, cmd=st["cmd"])   # 버튼 명령 → 즉시 촬영
        elif time.time() - last_location >= LOC_EVERY:
            do_report(cfg, server)                  # 주기적 위치 보고
            last_location = time.time()


if __name__ == "__main__":
    main()
