"""도난 모드 상태와 메시지 offset을 파일로 저장."""
import os
from config import STATE_DIR


def _ensure():
    os.makedirs(STATE_DIR, exist_ok=True)


def _p(name):
    return os.path.join(STATE_DIR, name)


def is_lost():
    return os.path.exists(_p("lost"))


def set_lost(on):
    _ensure()
    if on:
        open(_p("lost"), "w").close()
    else:
        try:
            os.remove(_p("lost"))
        except FileNotFoundError:
            pass


def pop_once():
    """/status 로 요청된 1회 보고 플래그를 읽고 지운다."""
    if os.path.exists(_p("once")):
        os.remove(_p("once"))
        return True
    return False


def set_once():
    _ensure()
    open(_p("once"), "w").close()


def get_offset():
    try:
        with open(_p("offset")) as f:
            return int(f.read().strip() or 0)
    except (FileNotFoundError, ValueError):
        return 0


def set_offset(v):
    _ensure()
    with open(_p("offset"), "w") as f:
        f.write(str(v))


def get_last_auto_shot():
    try:
        with open(_p("last_auto_shot")) as f:
            return float(f.read().strip() or 0)
    except (FileNotFoundError, ValueError):
        return 0.0


def set_last_auto_shot():
    import time
    _ensure()
    with open(_p("last_auto_shot"), "w") as f:
        f.write(str(time.time()))
