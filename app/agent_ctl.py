"""'이 기기 보호' 탭에서 로컬 에이전트를 설치·설정·제어.
관리자 권한이 필요한 작업은 pkexec(리눅스)로 요청한다.
윈도우는 추후 별도 구현(관리자 권한 + 작업 스케줄러).
"""
import os
import sys
import platform
import subprocess

IS_LINUX = platform.system() == "Linux"
IS_WINDOWS = platform.system() == "Windows"

CONF_PATH = "/etc/dorawa/dorawa.conf"


def agent_installed():
    """에이전트가 설치돼 있는지(설정 파일 존재)."""
    return os.path.exists(CONF_PATH)


def _run_as_root(script):
    """셸 스크립트를 관리자 권한으로 실행. 성공 bool, 메시지."""
    if IS_LINUX:
        try:
            p = subprocess.run(["pkexec", "bash", "-c", script],
                               capture_output=True, text=True, timeout=120)
            if p.returncode == 0:
                return True, p.stdout
            return False, (p.stderr or p.stdout or "권한 거부 또는 실패")
        except FileNotFoundError:
            return False, "pkexec가 없습니다. polkit을 설치하세요."
        except Exception as e:
            return False, str(e)
    return False, "이 OS는 아직 지원하지 않습니다."


def install_and_configure(server_url, secret, webcam):
    """에이전트 설정 파일을 쓰고 서비스를 켠다.
    (프로그램 파일은 이미 /usr/local/lib/dorawa 에 있다고 가정 — 앱 패키지에 동봉)
    """
    webcam_s = "true" if webcam else "false"
    conf = (
        "[server]\nurl = %s\nsecret = %s\n\n"
        "[features]\nwebcam = %s\nwifi_location = beacondb\n"
    ) % (server_url, secret, webcam_s)
    # 설정 파일 쓰기 + 권한 600 + 타이머 활성화
    script = (
        "set -e\n"
        "mkdir -p /etc/dorawa /var/lib/dorawa\n"
        "cat > /etc/dorawa/dorawa.conf <<'DORAWAEOF'\n%s\nDORAWAEOF\n"
        "chmod 600 /etc/dorawa/dorawa.conf\n"
        "systemctl daemon-reload\n"
        "systemctl enable --now dorawa.timer\n"
        "echo OK\n"
    ) % conf
    return _run_as_root(script)


def set_webcam(enabled):
    """웹캠 설정만 변경."""
    val = "true" if enabled else "false"
    script = (
        "set -e\n"
        "sed -i 's/^webcam = .*/webcam = %s/' /etc/dorawa/dorawa.conf\n"
        "echo OK\n"
    ) % val
    return _run_as_root(script)


def uninstall():
    """보호 해제: 타이머 끄고 설정 삭제."""
    script = (
        "systemctl disable --now dorawa.timer 2>/dev/null || true\n"
        "rm -f /etc/dorawa/dorawa.conf\n"
        "rm -rf /var/lib/dorawa\n"
        "echo OK\n"
    )
    return _run_as_root(script)


def status():
    """에이전트 상태 문자열."""
    if not agent_installed():
        return "미설치 (이 기기는 보호되고 있지 않음)"
    if IS_LINUX:
        try:
            p = subprocess.run(["systemctl", "is-active", "dorawa.timer"],
                               capture_output=True, text=True, timeout=10)
            active = p.stdout.strip() == "active"
            return "보호 중 (에이전트 작동)" if active else "설치됨 (타이머 꺼짐)"
        except Exception:
            return "설치됨 (상태 확인 불가)"
    return "설치됨"
