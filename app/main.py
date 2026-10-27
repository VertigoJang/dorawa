#!/usr/bin/env python3
"""Dorawa 노트북 앱 (리눅스/윈도우).
탭 2개:
  - 내 기기 추적: 로그인 후 기기 목록, 도난 모드, 원격 촬영, 보고 조회
  - 이 기기 보호: 이 노트북을 에이전트로 등록(6자리 페어링), 웹캠 설정
"""
import sys
import json
import os

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTabWidget, QListWidget, QListWidgetItem,
    QTextEdit, QMessageBox, QCheckBox, QRadioButton, QSpinBox, QButtonGroup,
    QStackedWidget, QScrollArea, QFrame,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QIcon

from api import DorawaAPI, ApiError
import agent_ctl

CONFIG_FILE = os.path.expanduser("~/.config/dorawa-app.json")
DEFAULT_SERVER = "https://dorawa.duckdns.org"


def icon_path():
    """실행/번들 양쪽에서 아이콘 경로를 찾는다."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    p = os.path.join(base, "icon.png")
    return p if os.path.exists(p) else ""


def load_cfg():
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_cfg(d):
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(d, f)
    except Exception:
        pass


# ---------- 백그라운드 작업 (네트워크가 UI를 멈추지 않도록) ----------
class Worker(QThread):
    done = Signal(object)
    fail = Signal(str)

    # 실행 중인 모든 Worker 추적 (창이 닫혀도 GC로 사라지지 않게, 종료 시 정리)
    _alive = set()

    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        Worker._alive.add(self)
        self.finished.connect(lambda: Worker._alive.discard(self))

    def run(self):
        try:
            self.done.emit(self.fn())
        except ApiError as e:
            self.fail.emit(str(e))
        except Exception as e:
            self.fail.emit("오류: %s" % e)

    @classmethod
    def wait_all(cls, ms=3000):
        for w in list(cls._alive):
            try:
                w.wait(ms)
            except Exception:
                pass


# ---------- 로그인 화면 ----------
class LoginPage(QWidget):
    logged_in = Signal()

    def __init__(self, api):
        super().__init__()
        self.api = api
        cfg = load_cfg()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 40, 40, 40)
        lay.setSpacing(10)

        title = QLabel("Dorawa")
        title.setStyleSheet("font-size:28px; font-weight:bold;")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)
        lay.addSpacing(10)

        lay.addWidget(QLabel("서버 주소"))
        self.server = QLineEdit(cfg.get("server", DEFAULT_SERVER))
        lay.addWidget(self.server)

        lay.addWidget(QLabel("아이디"))
        self.user = QLineEdit(cfg.get("username", ""))
        lay.addWidget(self.user)

        lay.addWidget(QLabel("비밀번호"))
        self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.Password)
        self.pw.returnPressed.connect(self.do_login)
        lay.addWidget(self.pw)

        self.btn = QPushButton("로그인")
        self.btn.clicked.connect(self.do_login)
        lay.addWidget(self.btn)

        self.msg = QLabel("")
        self.msg.setStyleSheet("color:#dc2626;")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)

        hint = QLabel("계정이 없으면 웹(%s)에서 먼저 가입하세요." % DEFAULT_SERVER)
        hint.setStyleSheet("color:#666; font-size:12px;")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        lay.addStretch()

    def do_login(self):
        self.msg.setText("")
        self.btn.setEnabled(False)
        self.btn.setText("로그인 중...")
        self.api.base = self.server.text().strip().rstrip("/")
        u, p = self.user.text().strip(), self.pw.text()

        self.w = Worker(lambda: self.api.login(u, p))
        self.w.done.connect(self._ok)
        self.w.fail.connect(self._err)
        self.w.start()

    def _ok(self, _):
        save_cfg({"server": self.api.base, "username": self.user.text().strip()})
        self.btn.setEnabled(True)
        self.btn.setText("로그인")
        self.logged_in.emit()

    def _err(self, m):
        self.btn.setEnabled(True)
        self.btn.setText("로그인")
        self.msg.setText(m)


# ---------- 내 기기 추적 탭 ----------
class TrackTab(QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.cur_did = None
        lay = QHBoxLayout(self)

        # 왼쪽: 기기 목록
        left = QVBoxLayout()
        left.addWidget(QLabel("내 기기"))
        self.dev_list = QListWidget()
        self.dev_list.itemClicked.connect(self.on_select)
        left.addWidget(self.dev_list)
        self.refresh_btn = QPushButton("새로고침")
        self.refresh_btn.clicked.connect(self.load_devices)
        left.addWidget(self.refresh_btn)
        lay.addLayout(left, 1)

        # 오른쪽: 상세
        right = QVBoxLayout()
        self.dev_title = QLabel("기기를 선택하세요")
        self.dev_title.setStyleSheet("font-size:18px; font-weight:bold;")
        right.addWidget(self.dev_title)

        self.lost_btn = QPushButton("🚨 도난 모드 켜기")
        self.lost_btn.clicked.connect(self.toggle_lost)
        self.lost_btn.setEnabled(False)
        right.addWidget(self.lost_btn)

        cap = QHBoxLayout()
        self.photo_btn = QPushButton("📷 사진 찍기")
        self.photo_btn.clicked.connect(lambda: self.capture("photo"))
        self.video_btn = QPushButton("🎥 10초 영상")
        self.video_btn.clicked.connect(lambda: self.capture("video"))
        self.photo_btn.setEnabled(False)
        self.video_btn.setEnabled(False)
        cap.addWidget(self.photo_btn)
        cap.addWidget(self.video_btn)
        right.addLayout(cap)

        right.addWidget(QLabel("최근 보고"))
        self.reports = QTextEdit()
        self.reports.setReadOnly(True)
        right.addWidget(self.reports)
        lay.addLayout(right, 2)

        self.load_devices()

    def load_devices(self):
        self.w = Worker(self.api.devices)
        self.w.done.connect(self._fill_devices)
        self.w.fail.connect(lambda m: self.reports.setText(m))
        self.w.start()

    def _fill_devices(self, devs):
        self.devs = {d["id"]: d for d in devs}
        self.dev_list.clear()
        for d in devs:
            label = ("🚨 " if d["lost"] else "") + (d["name"] or "이름없음")
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, d["id"])
            self.dev_list.addItem(it)

    def on_select(self, item):
        self.cur_did = item.data(Qt.UserRole)
        d = self.devs[self.cur_did]
        self.dev_title.setText(d["name"] or "이름없음")
        self._update_lost_btn(d["lost"])
        self.photo_btn.setEnabled(True)
        self.video_btn.setEnabled(True)
        self.lost_btn.setEnabled(True)
        self.load_reports()

    def _update_lost_btn(self, lost):
        self.cur_lost = lost
        self.lost_btn.setText("✅ 도난 모드 끄기" if lost else "🚨 도난 모드 켜기")

    def toggle_lost(self):
        if self.cur_did is None:
            return
        new = not self.cur_lost
        self.w2 = Worker(lambda: self.api.set_lost(self.cur_did, new))
        self.w2.done.connect(lambda _: (self._update_lost_btn(new), self.load_devices()))
        self.w2.fail.connect(lambda m: QMessageBox.warning(self, "오류", m))
        self.w2.start()

    def capture(self, cmd):
        if self.cur_did is None:
            return
        self.w3 = Worker(lambda: self.api.capture(self.cur_did, cmd))
        self.w3.done.connect(lambda _: QMessageBox.information(
            self, "요청됨", "촬영 명령을 보냈습니다. 잠시 뒤 '최근 보고'를 새로고침하세요."))
        self.w3.fail.connect(lambda m: QMessageBox.warning(self, "오류", m))
        self.w3.start()

    def load_reports(self):
        if self.cur_did is None:
            return
        self.w4 = Worker(lambda: self.api.reports(self.cur_did))
        self.w4.done.connect(self._show_reports)
        self.w4.fail.connect(lambda m: self.reports.setText(m))
        self.w4.start()

    def _show_reports(self, reps):
        import datetime
        lines = []
        for r in reps:
            t = datetime.datetime.fromtimestamp(r["ts"]).strftime("%Y-%m-%d %H:%M:%S")
            lines.append("[%s]" % t)
            lines.append("  IP: %s (%s)" % (r.get("public_ip") or "?", r.get("ip_desc") or ""))
            if r.get("lat"):
                lines.append("  위치: https://maps.google.com/?q=%s,%s" % (r["lat"], r["lng"]))
            if r.get("photo_url"):
                lines.append("  사진: %s%s" % (self.api.base, r["photo_url"]))
            if r.get("video_url"):
                lines.append("  영상: %s%s" % (self.api.base, r["video_url"]))
            lines.append("")
        self.reports.setText("\n".join(lines) or "아직 보고가 없습니다.")


# ---------- 이 기기 보호 탭 ----------
class ProtectTab(QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        self.status_lbl = QLabel()
        self.status_lbl.setStyleSheet("font-size:15px; font-weight:bold;")
        lay.addWidget(self.status_lbl)

        info = QLabel("이 노트북을 도난 추적 대상으로 등록합니다.\n"
                      "웹에서 '페어링 코드 만들기'로 나온 6자리를 입력하세요.")
        info.setWordWrap(True)
        info.setStyleSheet("color:#666;")
        lay.addWidget(info)

        lay.addWidget(QLabel("6자리 페어링 코드"))
        self.code = QLineEdit()
        self.code.setMaxLength(6)
        lay.addWidget(self.code)

        lay.addWidget(QLabel("이 기기 이름"))
        self.name = QLineEdit("my-laptop")
        lay.addWidget(self.name)

        self.webcam = QCheckBox("웹캠 촬영 허용 (도난 시 원격으로 사진·영상)")
        self.webcam.setChecked(True)
        lay.addWidget(self.webcam)

        self.protect_btn = QPushButton("이 기기 보호 시작")
        self.protect_btn.clicked.connect(self.do_protect)
        lay.addWidget(self.protect_btn)

        self.unprotect_btn = QPushButton("보호 해제")
        self.unprotect_btn.clicked.connect(self.do_unprotect)
        lay.addWidget(self.unprotect_btn)

        self.msg = QLabel("")
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        lay.addStretch()

        self.refresh_status()

    def refresh_status(self):
        self.status_lbl.setText("상태: " + agent_ctl.status())
        installed = agent_ctl.agent_installed()
        self.unprotect_btn.setEnabled(installed)

    def do_protect(self):
        code = self.code.text().strip()
        name = self.name.text().strip() or "my-laptop"
        if len(code) != 6:
            self.msg.setText("6자리 코드를 입력하세요.")
            return
        self.msg.setText("페어링 중...")
        self.protect_btn.setEnabled(False)

        def task():
            # 1) 서버에 페어링 → secret 받기
            r = self.api.pair_device(code, name)
            secret = r.get("secret")
            if not secret:
                raise ApiError(r.get("error", "페어링 실패"))
            # 2) 로컬 에이전트 설치·설정 (관리자 권한)
            ok, out = agent_ctl.install_and_configure(
                self.api.base, secret, self.webcam.isChecked())
            if not ok:
                raise ApiError("에이전트 설정 실패: %s" % out)
            return True

        self.w = Worker(task)
        self.w.done.connect(self._protect_ok)
        self.w.fail.connect(self._protect_err)
        self.w.start()

    def _protect_ok(self, _):
        self.protect_btn.setEnabled(True)
        self.msg.setText("보호를 시작했습니다. 이제 '내 기기 추적'에서 이 기기를 볼 수 있습니다.")
        self.refresh_status()

    def _protect_err(self, m):
        self.protect_btn.setEnabled(True)
        self.msg.setText(m)

    def do_unprotect(self):
        if QMessageBox.question(self, "확인", "이 기기의 보호를 해제할까요?") != QMessageBox.Yes:
            return
        ok, out = agent_ctl.uninstall()
        self.msg.setText("보호를 해제했습니다." if ok else ("해제 실패: %s" % out))
        self.refresh_status()


# ---------- 메인 창 ----------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dorawa")
        self.resize(720, 520)
        if icon_path():
            self.setWindowIcon(QIcon(icon_path()))
        self.api = DorawaAPI()

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.login = LoginPage(self.api)
        self.login.logged_in.connect(self.show_main)
        self.stack.addWidget(self.login)

    def show_main(self):
        tabs = QTabWidget()
        tabs.addTab(TrackTab(self.api), "내 기기 추적")
        tabs.addTab(ProtectTab(self.api), "이 기기 보호")
        self.stack.addWidget(tabs)
        self.stack.setCurrentWidget(tabs)

    def closeEvent(self, ev):
        # 백그라운드 스레드가 끝날 때까지 기다린 뒤 종료 (크래시 방지)
        Worker.wait_all()
        ev.accept()


def main():
    app = QApplication(sys.argv)
    if icon_path():
        app.setWindowIcon(QIcon(icon_path()))
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
