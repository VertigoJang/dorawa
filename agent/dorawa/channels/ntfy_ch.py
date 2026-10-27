"""ntfy 채널. 보고 전송 + 명령 수신(구독) 모두 지원.

ntfy는 topic 기반 pub/sub.
- 전송: POST https://<server>/<topic>  (본문이 메시지)
- 사진: PUT  https://<server>/<topic>  (본문이 이미지, Filename 헤더)
- 수신: GET  https://<server>/<topic>/json?poll=1&since=<t>  (한 줄에 JSON 하나씩)

명령은 사용자가 같은 topic으로 보낸 메시지를 노트북이 읽어 처리한다.
보안을 위해 명령용 topic은 추측하기 어려운 이름을 쓰는 것을 권장.
"""
import json
import os
import time
import urllib.request

from config import STATE_DIR


class NtfyChannel:
    def __init__(self, cfg):
        self.server = (cfg.get("ntfy", "server", "https://ntfy.sh") or "https://ntfy.sh").rstrip("/")
        self.topic = cfg.get("ntfy", "topic", "")
        self.token = cfg.get("ntfy", "token", "")  # 선택: 인증 토큰
        self._since_file = os.path.join(STATE_DIR, "ntfy_since")

    def _auth_headers(self):
        return {"Authorization": "Bearer %s" % self.token} if self.token else {}

    def alive(self):
        return bool(self.topic)

    def send_text(self, text):
        url = "%s/%s" % (self.server, self.topic)
        req = urllib.request.Request(url, data=text.encode("utf-8"),
                                     headers=self._auth_headers(), method="POST")
        try:
            urllib.request.urlopen(req, timeout=20).read()
        except Exception:
            pass

    def send_photo(self, path, caption=""):
        url = "%s/%s" % (self.server, self.topic)
        with open(path, "rb") as f:
            data = f.read()
        headers = self._auth_headers()
        headers["Filename"] = "cam.jpg"
        if caption:
            # 헤더는 ASCII만 안전하므로 캡션은 별도 텍스트로 보낸다
            self.send_text(caption)
        req = urllib.request.Request(url, data=data, headers=headers, method="PUT")
        try:
            urllib.request.urlopen(req, timeout=30).read()
        except Exception:
            pass

    def _get_since(self):
        try:
            with open(self._since_file) as f:
                return f.read().strip() or "all"
        except FileNotFoundError:
            # 최초 실행은 과거 메시지를 끌어오지 않도록 현재 시각부터
            return str(int(time.time()))

    def _set_since(self, v):
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(self._since_file, "w") as f:
            f.write(str(v))

    def poll_commands(self):
        since = self._get_since()
        url = "%s/%s/json?poll=1&since=%s" % (self.server, self.topic, since)
        req = urllib.request.Request(url, headers=self._auth_headers())
        try:
            raw = urllib.request.urlopen(req, timeout=20).read().decode()
        except Exception:
            return []
        cmds = []
        latest = since
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if msg.get("event") != "message":
                continue
            t = msg.get("time")
            if t is not None:
                latest = str(int(t) + 1)
            text = (msg.get("message") or "").strip()
            # 노트북이 보낸 보고를 명령으로 되읽지 않도록, 보고 메시지는 건너뛴다
            if text.startswith("📍") or text.startswith("주변 와이파이"):
                continue
            if text:
                cmds.append(text)
        self._set_since(latest)
        return cmds
