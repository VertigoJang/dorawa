"""디스코드 웹훅 채널. 봇 아님 — 보내기 전용(명령 수신 불가).

채널 설정 > 연동 > 웹후크 에서 URL을 만들어 그대로 넣으면 된다.
"""
import json
import urllib.request


class DiscordChannel:
    def __init__(self, cfg):
        self.webhook = cfg.get("discord", "webhook_url", "")

    def alive(self):
        return bool(self.webhook)

    def send_text(self, text):
        data = json.dumps({"content": text[:1900]}).encode()
        req = urllib.request.Request(
            self.webhook, data=data,
            headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=20).read()
        except Exception:
            pass

    def send_photo(self, path, caption=""):
        boundary = "----DorawaBoundary7MA4YWxk"
        with open(path, "rb") as f:
            photo = f.read()
        parts = []
        payload = json.dumps({"content": caption[:1900]})
        parts.append(("--%s\r\n" % boundary).encode())
        parts.append(b'Content-Disposition: form-data; name="payload_json"\r\n')
        parts.append(b"Content-Type: application/json\r\n\r\n")
        parts.append(payload.encode() + b"\r\n")
        parts.append(("--%s\r\n" % boundary).encode())
        parts.append(b'Content-Disposition: form-data; name="files[0]"; filename="cam.jpg"\r\n')
        parts.append(b"Content-Type: image/jpeg\r\n\r\n")
        parts.append(photo + b"\r\n")
        parts.append(("--%s--\r\n" % boundary).encode())
        body = b"".join(parts)
        req = urllib.request.Request(
            self.webhook, data=body,
            headers={"Content-Type": "multipart/form-data; boundary=%s" % boundary})
        try:
            urllib.request.urlopen(req, timeout=30).read()
        except Exception:
            pass

    def poll_commands(self):
        # 웹훅은 보내기 전용. 명령 수신 불가.
        return []
