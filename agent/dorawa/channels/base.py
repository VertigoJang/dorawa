"""채널(알림 서비스) 공통 인터페이스 + 다중 채널 묶음.

새 서비스를 추가하려면 Channel을 상속해서
send_text / send_photo / poll_commands / alive 를 구현하고,
build() 의 분기에 한 줄 추가하면 된다.
"""


class Channel:
    def send_text(self, text):
        raise NotImplementedError

    def send_photo(self, path, caption=""):
        raise NotImplementedError

    def poll_commands(self):
        """새 명령 문자열 리스트. 명령 수신을 지원 안 하면 빈 리스트."""
        return []

    def alive(self):
        return True


class MultiChannel:
    """여러 채널을 하나처럼 다룬다.
    - 보고(send_*)는 살아있는 모든 채널에 보낸다.
    - 명령(poll_commands)은 명령을 지원하는 채널에서만 읽는다.
    """
    def __init__(self, channels):
        self.channels = [c for c in channels if c.alive()]

    def alive(self):
        return len(self.channels) > 0

    def send_text(self, text):
        for c in self.channels:
            c.send_text(text)

    def send_photo(self, path, caption=""):
        for c in self.channels:
            c.send_photo(path, caption)

    def poll_commands(self):
        cmds = []
        for c in self.channels:
            cmds.extend(c.poll_commands())
        return cmds


def _make_one(name, cfg):
    if name == "ntfy":
        from channels.ntfy_ch import NtfyChannel
        return NtfyChannel(cfg)
    if name == "discord":
        from channels.discord import DiscordChannel
        return DiscordChannel(cfg)
    raise ValueError("알 수 없는 채널: %s" % name)


def build(cfg):
    """설정의 channels(쉼표 구분)에 따라 채널들을 묶어 돌려준다.
    예: channels = ntfy, discord
    """
    names = [n.strip().lower() for n in cfg.channels_list if n.strip()]
    chans = []
    for n in names:
        try:
            chans.append(_make_one(n, cfg))
        except ValueError:
            pass
    return MultiChannel(chans)
