"""주변 와이파이 수집 + 위치 추정 (BeaconDB / WiGLE / off)."""
import json
import subprocess
import urllib.request


def scan():
    """주변 AP 목록. [(ssid, bssid, signal_dbm), ...]"""
    try:
        subprocess.run(["nmcli", "dev", "wifi", "rescan"],
                       timeout=15, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    import time
    time.sleep(4)
    try:
        out = subprocess.check_output(
            ["nmcli", "-t", "-f", "SSID,BSSID,SIGNAL", "dev", "wifi", "list"],
            timeout=10).decode()
    except Exception:
        return []
    aps = []
    for line in out.splitlines():
        # nmcli는 BSSID의 콜론을 \: 로 escape 하므로 복원
        line = line.replace("\\:", "\x00")
        cols = line.split(":")
        if len(cols) < 3:
            continue
        ssid = cols[0].replace("\x00", ":")
        bssid = cols[1].replace("\x00", ":")
        try:
            sig = int(cols[2])
        except ValueError:
            continue
        # nmcli SIGNAL(0~100)을 대략적인 dBm으로 환산
        dbm = sig // 2 - 100
        aps.append((ssid, bssid, dbm))
    return aps


def locate(aps, method, wigle_name="", wigle_token=""):
    """위치 추정. 성공 시 (lat, lng, accuracy_m), 실패 시 None."""
    if method == "off" or len(aps) < 2:
        return None
    if method == "wigle":
        return _locate_wigle(aps, wigle_name, wigle_token)
    return _locate_beacondb(aps)


def _locate_beacondb(aps):
    payload = {
        "considerIp": False,
        "wifiAccessPoints": [
            {"macAddress": b, "signalStrength": d} for (_, b, d) in aps
        ],
    }
    try:
        req = urllib.request.Request(
            "https://api.beacondb.net/v1/geolocate",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            j = json.loads(r.read().decode())
        loc = j.get("location")
        if loc:
            return (loc["lat"], loc["lng"], j.get("accuracy", 0))
    except Exception:
        pass
    return None


def _locate_wigle(aps, name, token):
    """WiGLE는 사용자 본인 API 키 필요. 가장 신호 강한 AP를 조회."""
    import base64
    if not name or not token:
        return None
    aps_sorted = sorted(aps, key=lambda a: a[2], reverse=True)
    auth = base64.b64encode(("%s:%s" % (name, token)).encode()).decode()
    for _, bssid, _ in aps_sorted[:3]:
        try:
            url = "https://api.wigle.net/api/v2/network/detail?netid=%s" % bssid
            req = urllib.request.Request(url, headers={"Authorization": "Basic %s" % auth})
            with urllib.request.urlopen(req, timeout=15) as r:
                j = json.loads(r.read().decode())
            results = j.get("results") or []
            if results and results[0].get("trilat") is not None:
                return (results[0]["trilat"], results[0]["trilong"], 0)
        except Exception:
            continue
    return None
