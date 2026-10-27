#!/usr/bin/env python3
"""Dorawa 설정 마법사. sudo python3 setup.py 로 실행.
터미널에서 대화형으로 설정 파일을 만든다. (GUI는 다음 단계)
"""
import os
import sys
import secrets
import getpass

try:
    import termios
    import tty
    HAVE_TTY = True
except ImportError:
    HAVE_TTY = False

CONF_DIR = "/etc/dorawa"
CONF_PATH = os.path.join(CONF_DIR, "dorawa.conf")


def _flush_input():
    """입력 버퍼에 미리 들어온(앞 명령이 흘러든) 내용을 비운다.
    이전 버전에서 토큰 입력이 앞 명령을 삼키던 버그를 막는다."""
    if not HAVE_TTY:
        return
    try:
        termios.tcflush(sys.stdin, termios.TCIFLUSH)
    except Exception:
        pass


def ask(prompt, default=""):
    _flush_input()
    s = input("%s%s: " % (prompt, (" [%s]" % default) if default else "")).strip()
    return s or default


def ask_secret(prompt):
    _flush_input()
    return getpass.getpass(prompt).strip()


def setup_server():
    """Dorawa 서버와 6자리 코드로 페어링. 성공 시 (url, secret)."""
    import json
    import urllib.request
    print("\n[Dorawa 서버 연결]")
    url = ask("서버 주소 (예: https://내서버.com)").rstrip("/")
    print("웹에서 로그인 > '페어링 코드 만들기' 로 나온 6자리를 입력하세요.")
    code = ask("6자리 코드")
    name = ask("이 기기 이름", "laptop")
    try:
        req = urllib.request.Request(
            "%s/api/pair" % url,
            data=json.dumps({"code": code, "name": name}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            j = json.loads(r.read().decode())
        secret = j.get("secret")
        if secret:
            print("   페어링 성공.")
            return url, secret
        print("   실패: %s" % j.get("error", "알 수 없음"))
    except Exception as e:
        print("   서버 연결 실패: %s" % e)
    return url, ""


def main():
    if os.geteuid() != 0:
        print("sudo python3 setup.py 로 실행하세요.")
        sys.exit(1)

    print("=== Dorawa 설정 ===")
    print("Dorawa 서버에 이 노트북을 연결합니다.\n")

    srv_url, srv_secret = setup_server()
    if not srv_secret:
        print("\n페어링에 실패해 종료합니다. 서버 주소와 6자리 코드를 확인하세요.")
        sys.exit(1)

    print()
    webcam = ask("웹캠 촬영을 켤까요? (도난 시 원격으로 사진·영상 촬영) (Y/n)", "y").lower() != "n"

    os.makedirs(CONF_DIR, exist_ok=True)
    with open(CONF_PATH, "w") as f:
        f.write("[server]\nurl = %s\nsecret = %s\n\n" % (srv_url, srv_secret))
        f.write("[features]\nwebcam = %s\nwifi_location = beacondb\n"
                % ("true" if webcam else "false"))
    os.chmod(CONF_PATH, 0o600)
    print("\n설정 완료.")
    print("웹(%s)에서 '도난 모드 켜기'를 누르면 이 노트북이 위치를 보고합니다." % srv_url)


if __name__ == "__main__":
    main()
