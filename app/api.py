"""Dorawa 서버 통신 클라이언트. 표준 라이브러리만 사용."""
import json
import urllib.request
import urllib.error


class DorawaAPI:
    def __init__(self, base_url=""):
        self.base = base_url.rstrip("/")
        self.token = ""

    def _req(self, method, path, data=None, auth=True, timeout=15):
        url = "%s%s" % (self.base, path)
        headers = {"Content-Type": "application/json"}
        if auth and self.token:
            headers["Authorization"] = "Bearer %s" % self.token
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read().decode()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            try:
                j = json.loads(e.read().decode())
                raise ApiError(j.get("error", "오류 %d" % e.code), e.code)
            except (ValueError, AttributeError):
                raise ApiError("서버 오류 %d" % e.code, e.code)
        except Exception as e:
            raise ApiError("연결 실패: %s" % e, 0)

    # --- 인증 ---
    def login(self, username, password):
        j = self._req("POST", "/api/app/login",
                      {"username": username, "password": password}, auth=False)
        self.token = j["token"]
        return j

    def logout(self):
        try:
            self._req("POST", "/api/app/logout")
        except ApiError:
            pass
        self.token = ""

    # --- 기기 ---
    def devices(self):
        return self._req("GET", "/api/app/devices")["devices"]

    def paircode(self):
        return self._req("POST", "/api/app/paircode")["code"]

    def reports(self, did):
        return self._req("GET", "/api/app/device/%d/reports" % did)["reports"]

    def set_lost(self, did, lost):
        return self._req("POST", "/api/app/device/%d/lost" % did, {"lost": bool(lost)})

    def capture(self, did, cmd):
        return self._req("POST", "/api/app/device/%d/capture" % did, {"cmd": cmd})

    def set_camera_mode(self, did, mode, interval=5):
        return self._req("POST", "/api/app/device/%d/camera_mode" % did,
                         {"mode": mode, "interval": interval})

    # 노트북 에이전트 페어링 (이 기기 보호 탭에서 사용)
    def pair_device(self, code, name):
        return self._req("POST", "/api/pair", {"code": code, "name": name}, auth=False)


class ApiError(Exception):
    def __init__(self, msg, code=0):
        super().__init__(msg)
        self.code = code
