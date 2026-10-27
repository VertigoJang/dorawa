"""롱폴링용 기기별 알림.
웹에서 촬영 명령을 예약하면 해당 기기의 Event를 깨워서,
그 기기가 걸어둔 롱폴링 연결이 즉시 응답하도록 한다.

주의: gunicorn 워커가 여러 개면 메모리가 공유되지 않는다.
그래서 운영 시 워커는 1개(-w 1)로 두거나, 스레드 기반(--threads)으로 둔다.
"""
import threading

_events = {}
_lock = threading.Lock()


def _ev(device_id):
    with _lock:
        e = _events.get(device_id)
        if e is None:
            e = threading.Event()
            _events[device_id] = e
        return e


def notify(device_id):
    """해당 기기의 롱폴링을 깨운다."""
    _ev(device_id).set()


def wait(device_id, timeout):
    """명령이 올 때까지(또는 timeout) 대기. 깨면 True."""
    e = _ev(device_id)
    got = e.wait(timeout)
    if got:
        e.clear()
    return got
