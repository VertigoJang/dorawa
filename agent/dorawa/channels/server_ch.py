"""Dorawa 자체 서버 채널.

다른 채널과 달리, 이 채널은 서버가 '도난 여부'를 알려준다.
- 보고 전송: POST /api/report (헤더 X-Device-Secret), 사진은 multipart
- 도난 확인: GET  /api/poll
- 명령(/lost 등)은 서버 웹에서 켜므로 poll_commands 는 쓰지 않는다.

기기 전용 secret 은 페어링(setup) 때 받아 설정 파일에 저장된다.
"""
import json
import urllib.request


class ServerChannel:
    def __init__(self, cfg):
        self.base = (cfg.get("server", "url", "") or "").rstrip("/")
        self.secret = cfg.get("server", "secret", "")
        self.remote_lost = None  # 마지막 응답의 도난 여부

    def alive(self):
        return bool(self.base and self.secret)

    def _headers(self):
        return {"X-Device-Secret": self.secret}

    def send_report_struct(self, meta, photo_path=None):
        """구조화된 보고(dict)를 서버로 전송. 응답의 lost 를 저장."""
        url = "%s/api/report" % self.base
        try:
            if photo_path:
                boundary = "----DorawaBoundary7MA4YWxk"
                with open(photo_path, "rb") as f:
                    photo = f.read()
                parts = []
                parts.append(("--%s\r\n" % boundary).encode())
                parts.append(b'Content-Disposition: form-data; name="meta"\r\n\r\n')
                parts.append(json.dumps(meta).encode() + b"\r\n")
                parts.append(("--%s\r\n" % boundary).encode())
                parts.append(b'Content-Disposition: form-data; name="photo"; filename="cam.jpg"\r\n')
                parts.append(b"Content-Type: image/jpeg\r\n\r\n")
                parts.append(photo + b"\r\n")
                parts.append(("--%s--\r\n" % boundary).encode())
                body = b"".join(parts)
                h = self._headers()
                h["Content-Type"] = "multipart/form-data; boundary=%s" % boundary
                req = urllib.request.Request(url, data=body, headers=h)
            else:
                h = self._headers()
                h["Content-Type"] = "application/json"
                req = urllib.request.Request(url, data=json.dumps(meta).encode(), headers=h)
            with urllib.request.urlopen(req, timeout=30) as r:
                j = json.loads(r.read().decode())
                self.remote_lost = bool(j.get("lost"))
        except Exception:
            pass

    def poll_status(self):
        """서버에 상태를 물어본다. dict{lost, cmd, camera_mode, auto_interval} 또는 None."""
        url = "%s/api/poll" % self.base
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                j = json.loads(r.read().decode())
                return {
                    "lost": bool(j.get("lost")),
                    "cmd": j.get("cmd", ""),
                    "camera_mode": j.get("camera_mode", "remote"),
                    "auto_interval": int(j.get("auto_interval", 5)),
                }
        except Exception:
            return None

    def send_report_struct_video(self, meta, photo_path=None, video_path=None):
        """사진+영상까지 포함해 전송."""
        if not video_path:
            return self.send_report_struct(meta, photo_path=photo_path)
        url = "%s/api/report" % self.base
        try:
            boundary = "----DorawaBoundary7MA4YWxk"
            parts = []
            parts.append(("--%s\r\n" % boundary).encode())
            parts.append(b'Content-Disposition: form-data; name="meta"\r\n\r\n')
            parts.append(json.dumps(meta).encode() + b"\r\n")
            if photo_path:
                with open(photo_path, "rb") as f:
                    photo = f.read()
                parts.append(("--%s\r\n" % boundary).encode())
                parts.append(b'Content-Disposition: form-data; name="photo"; filename="cam.jpg"\r\n')
                parts.append(b"Content-Type: image/jpeg\r\n\r\n")
                parts.append(photo + b"\r\n")
            with open(video_path, "rb") as f:
                vid = f.read()
            parts.append(("--%s\r\n" % boundary).encode())
            parts.append(b'Content-Disposition: form-data; name="video"; filename="cam.mp4"\r\n')
            parts.append(b"Content-Type: video/mp4\r\n\r\n")
            parts.append(vid + b"\r\n")
            parts.append(("--%s--\r\n" % boundary).encode())
            body = b"".join(parts)
            h = self._headers()
            h["Content-Type"] = "multipart/form-data; boundary=%s" % boundary
            req = urllib.request.Request(url, data=body, headers=h)
            with urllib.request.urlopen(req, timeout=60) as r:
                j = json.loads(r.read().decode())
                self.remote_lost = bool(j.get("lost"))
        except Exception:
            pass

    # 공통 인터페이스 호환용 (서버 채널은 텍스트/사진을 따로 안 쓰고 구조화 보고를 씀)
    def send_text(self, text):
        pass

    def send_photo(self, path, caption=""):
        pass

    def poll_commands(self):
        return []
