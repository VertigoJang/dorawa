"""이메일 발송 (Brevo HTTPS API).
구글 클라우드는 SMTP를 차단하므로 HTTPS API로 보낸다.

환경변수:
  DORAWA_BREVO_KEY    Brevo API 키 (xkeysib-...)
  DORAWA_SENDER       인증된 발신 주소 (예: dorawaadmin@gmail.com)
키가 없으면 콘솔에 코드만 출력(개발용).
"""
import os
import json
import urllib.request
import urllib.error

BREVO_KEY = os.environ.get("DORAWA_BREVO_KEY", "")
SENDER = os.environ.get("DORAWA_SENDER", "dorawaadmin@gmail.com")


def enabled():
    return bool(BREVO_KEY and SENDER)


def _send(to_email, subject, text):
    if not enabled():
        print("[mailer] (API 미설정) %s / %s: %s" % (to_email, subject, text))
        return False
    payload = {
        "sender": {"name": "Dorawa", "email": SENDER},
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": text,
    }
    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload).encode(),
        headers={"api-key": BREVO_KEY, "Content-Type": "application/json",
                 "accept": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            r.read()
        return True
    except urllib.error.HTTPError as e:
        print("[mailer] Brevo 오류 %s: %s" % (e.code, e.read().decode()[:300]))
        return False
    except Exception as e:
        print("[mailer] 발송 실패: %s" % e)
        return False


def send_code(to_email, code):
    """가입 인증 코드."""
    return _send(
        to_email, "Dorawa 이메일 인증 코드",
        "Dorawa 가입을 위한 인증 코드입니다.\n\n    %s\n\n"
        "30분 안에 입력하세요. 본인이 요청하지 않았다면 무시해도 됩니다." % code)


def send_reset_code(to_email, code):
    """비밀번호 재설정 코드."""
    return _send(
        to_email, "Dorawa 비밀번호 재설정 코드",
        "Dorawa 비밀번호 재설정 코드입니다.\n\n    %s\n\n"
        "30분 안에 입력하세요. 본인이 요청하지 않았다면 이 메일을 무시하세요 "
        "(비밀번호는 바뀌지 않습니다)." % code)
