"""설정 로드. /etc/dorawa/dorawa.conf 를 읽는다 (root만 읽기 가능, 0600)."""
import os
import configparser

CONF_PATH = os.environ.get("DORAWA_CONF", "/etc/dorawa/dorawa.conf")
STATE_DIR = os.environ.get("DORAWA_STATE", "/var/lib/dorawa")


class Config:
    def __init__(self, path=CONF_PATH):
        self.path = path
        cp = configparser.ConfigParser()
        cp.read(path)
        self._cp = cp

    def get(self, section, key, fallback=None):
        return self._cp.get(section, key, fallback=fallback)

    def getbool(self, section, key, fallback=False):
        return self._cp.getboolean(section, key, fallback=fallback)

    # --- 채널 ---
    @property
    def channels_list(self):
        # 쉼표로 여러 개: "ntfy, discord". 명령은 ntfy에서만 받는다.
        raw = self.get("general", "channels", "ntfy")
        return [p for p in raw.split(",")]

    # --- 기능 토글 ---
    @property
    def webcam_enabled(self):
        # 기본 꺼짐 (타인 얼굴 촬영이라 사용자가 명시적으로 켜야 함)
        return self.getbool("features", "webcam", False)

    @property
    def wifi_location(self):
        # beacondb | wigle | off
        return self.get("features", "wifi_location", "beacondb").strip().lower()

    @property
    def wigle_api_name(self):
        return self.get("wigle", "api_name", "")

    @property
    def wigle_api_token(self):
        return self.get("wigle", "api_token", "")

    @property
    def report_interval(self):
        return int(self.get("general", "interval_sec", "300"))
