"""공인 IP, 통신사, 로그인 사용자, 연결된 와이파이 등 기본 정보."""
import json
import socket
import subprocess
import urllib.request


def _run(cmd):
    try:
        return subprocess.check_output(cmd, timeout=10, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return ""


def public_ip():
    """공인 IP와 통신사/도시. 지도 링크는 만들지 않는다 (IP 좌표는 부정확)."""
    try:
        with urllib.request.urlopen("https://ipinfo.io/json", timeout=10) as r:
            j = json.loads(r.read().decode())
    except Exception:
        return {"ip": "?", "desc": "조회 실패"}
    parts = [j.get("city"), j.get("region"), j.get("org")]
    desc = ", ".join(p for p in parts if p)
    return {"ip": j.get("ip", "?"), "desc": desc}


def logged_in_users():
    out = _run(["who"])
    users = sorted({line.split()[0] for line in out.splitlines() if line.split()})
    return " ".join(users)


def active_wifi():
    out = _run(["nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi"])
    for line in out.splitlines():
        if line.startswith("yes:"):
            return line.split(":", 1)[1]
    return ""


def hostname():
    return socket.gethostname()
