"""보고를 서버가 받기 좋은 구조(dict)로 만든다.
텍스트 채널(ntfy/discord)과 서버 채널이 같은 수집 결과를 공유하도록,
agent 가 모은 값들을 받아 dict 로 변환한다.
"""


def build_struct(ip, wifi_ssid, loc, aps):
    """ip: {'ip','desc'}, loc: (lat,lng,acc) or None, aps: [(ssid,bssid,dbm),...]"""
    lat = lng = acc = None
    if loc:
        lat, lng, acc = loc
    raw_aps = "\n".join("%s  %s  %ddBm" % (s or "(숨김)", b, d) for (s, b, d) in aps[:15])
    return {
        "public_ip": ip.get("ip"),
        "ip_desc": ip.get("desc"),
        "wifi_ssid": wifi_ssid,
        "lat": lat, "lng": lng, "accuracy": acc,
        "raw": raw_aps,
    }
