#!/usr/bin/env python3
"""Dorawa 노트북 앱 (리눅스/윈도우).
탭 2개:
  - 내 기기 추적: 로그인 후 기기 목록, 도난 모드, 원격 촬영, 보고 조회(사진·영상 인라인)
  - 이 기기 보호: 이 노트북을 에이전트로 등록(6자리 페어링), 웹캠 설정
"""
import sys
import json
import os
import urllib.request

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTabWidget, QListWidget, QListWidgetItem,
    QTextEdit, QMessageBox, QCheckBox, QRadioButton, QSpinBox, QButtonGroup,
    QStackedWidget, QScrollArea, QFrame, QDialog,
)
from PySide6.QtCore import Qt, QThread, Signal, QUrl, QByteArray
from PySide6.QtGui import QPixmap, QIcon, QDesktopServices

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


# ---------- 클릭 가능한 라벨 (썸네일용) ----------
class ClickableLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, e):
        self.clicked.emit()
        super().mousePressEvent(e)


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

        # 보고 헤더 + 새로고침
        rep_head = QHBoxLayout()
        rep_head.addWidget(QLabel("최근 보고"))
        rep_head.addStretch()
        self.rep_refresh = QPushButton("🔄 새로고침")
        self.rep_refresh.clicked.connect(self.load_reports)
        rep_head.addWidget(self.rep_refresh)
        right.addLayout(rep_head)

        # 보고 목록: 스크롤 카드 영역
        self.reports_scroll = QScrollArea()
        self.reports_scroll.setWidgetResizable(True)
        self.reports_container = QWidget()
        self.reports_vbox = QVBoxLayout(self.reports_container)
        self.reports_vbox.setAlignment(Qt.AlignTop)
        self.reports_scroll.setWidget(self.reports_container)
        right.addWidget(self.reports_scroll)

        lay.addLayout(right, 2)

        self.load_devices()

    # --- 보고 영역 헬퍼 ---
    def _clear_reports(self):
        while self.reports_vbox.count():
            item = self.reports_vbox.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _set_reports_message(self, text):
        self._clear_reports()
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color:#666;")
        self.reports_vbox.addWidget(lbl)

    def load_devices(self):
        self.w = Worker(self.api.devices)
        self.w.done.connect(self._fill_devices)
        self.w.fail.connect(self._set_reports_message)
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
            self, "요청됨", "촬영 명령을 보냈습니다. 잠시 뒤 '🔄 새로고침'을 누르세요."))
        self.w3.fail.connect(lambda m: QMessageBox.warning(self, "오류", m))
        self.w3.start()

    def load_reports(self):
        if self.cur_did is None:
            return
        self.w4 = Worker(lambda: self.api.reports(self.cur_did))
        self.w4.done.connect(self._show_reports)
        self.w4.fail.connect(self._set_reports_message)
        self.w4.start()

    def _show_reports(self, reps):
        import datetime
        self._clear_reports()
        if not reps:
            self._set_reports_message("아직 보고가 없습니다.")
            return
        for r in reps:
            card = QFrame()
            card.setFrameShape(QFrame.StyledPanel)
            cv = QVBoxLayout(card)

            t = datetime.datetime.fromtimestamp(r["ts"]).strftime("%Y-%m-%d %H:%M:%S")
            head = QLabel("🕒 %s" % t)
            head.setStyleSheet("font-weight:bold;")
            cv.addWidget(head)

            cv.addWidget(QLabel("IP: %s (%s)" % (
                r.get("public_ip") or "?", r.get("ip_desc") or "")))

            if r.get("wifi_ssid"):
                cv.addWidget(QLabel("Wi-Fi: %s" % r["wifi_ssid"]))

            if r.get("lat"):
                loc = QLabel('위치: <a href="https://maps.google.com/?q=%s,%s">지도에서 보기</a>'
                            % (r["lat"], r["lng"]))
                loc.setOpenExternalLinks(True)
                cv.addWidget(loc)

            if r.get("photo_url"):
                self._add_photo(cv, self.api.base + r["photo_url"])

            if r.get("video_url"):
                vurl = self.api.base + r["video_url"]
                vbtn = QPushButton("🎥 영상 재생")
                vbtn.clicked.connect(lambda checked=False, u=vurl: self._play_video(u))
                cv.addWidget(vbtn)

            self.reports_vbox.addWidget(card)
        self.reports_vbox.addStretch()

    def _add_photo(self, card_vbox, url):
        lbl = ClickableLabel("사진 불러오는 중...")
        lbl.setStyleSheet("color:#888;")
        card_vbox.addWidget(lbl)

        def load():
            with urllib.request.urlopen(url, timeout=20) as resp:
                return resp.read()

        w = Worker(load)

        def ok(data):
            pix = QPixmap()
            pix.loadFromData(QByteArray(data))
            # 새로고침으로 목록이 교체되면 lbl(C++ 객체)이 이미 삭제됐을 수 있다.
            try:
                if pix.isNull():
                    lbl.setText("사진 표시 실패")
                    return
                thumb = pix.scaledToWidth(240, Qt.SmoothTransformation)
                lbl.setPixmap(thumb)
                lbl.setText("")
                lbl.setCursor(Qt.PointingHandCursor)
                lbl.setToolTip("클릭하면 원본 크기로 보기")
                lbl.clicked.connect(lambda: self._show_full_image(pix))
            except RuntimeError:
                return  # 라벨이 이미 삭제됨 — 무시

        def fail_cb(m):
            try:
                lbl.setText("사진 불러오기 실패")
            except RuntimeError:
                pass

        w.done.connect(ok)
        w.fail.connect(fail_cb)
        w.start()

    def _show_full_image(self, pix):
        dlg = QDialog(self)
        dlg.setWindowTitle("사진")
        v = QVBoxLayout(dlg)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        big = QLabel()
        big.setPixmap(pix)
        big.setAlignment(Qt.AlignCenter)
        scroll.setWidget(big)
        v.addWidget(scroll)
        dlg.resize(min(pix.width() + 40, 1000), min(pix.height() + 60, 800))
        dlg.exec()

    def _play_video(self, url):
        # 앱 내 재생 시도, 실패하면 브라우저로 폴백
        try:
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
            from PySide6.QtMultimediaWidgets import QVideoWidget
        except Exception as e:
            QMessageBox.information(self, "영상",
                "앱 내 영상 재생 모듈이 없어 브라우저로 엽니다.\n%s" % e)
            QDesktopServices.openUrl(QUrl(url))
            return
        try:
            dlg = QDialog(self)
            dlg.setWindowTitle("영상")
            dlg.resize(680, 560)
            v = QVBoxLayout(dlg)

            vw = QVideoWidget()
            v.addWidget(vw)

            player = QMediaPlayer(dlg)
            audio = QAudioOutput(dlg)
            player.setAudioOutput(audio)
            player.setVideoOutput(vw)
            player.setSource(QUrl(url))

            ctl = QHBoxLayout()
            toggle = QPushButton("⏯ 재생/일시정지")
            toggle.clicked.connect(
                lambda: player.pause()
                if player.playbackState() == QMediaPlayer.PlayingState
                else player.play())
            open_ext = QPushButton("브라우저에서 열기")
            open_ext.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
            ctl.addWidget(toggle)
            ctl.addWidget(open_ext)
            v.addLayout(ctl)

            dlg.finished.connect(lambda _: player.stop())
            player.play()
            dlg.exec()
            # 창을 닫을 때 플레이어를 명시적으로 정지·해제 (종료 크래시 방지)
            try:
                player.stop()
                player.setVideoOutput(None)
                player.setSource(QUrl())
            except Exception:
                pass
        except Exception as e:
            QMessageBox.information(self, "영상",
                "앱 내 재생이 어려워 브라우저로 엽니다.\n%s" % e)
            QDesktopServices.openUrl(QUrl(url))


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
    # Wayland에서 작업표시줄이 .desktop 파일로 아이콘을 찾도록 ID 고정
    try:
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.setDesktopFileName("dorawa")
    except Exception:
        pass
    app = QApplication(sys.argv)
    app.setApplicationName("Dorawa")
    app.setApplicationDisplayName("Dorawa")
    if icon_path():
        app.setWindowIcon(QIcon(icon_path()))
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
