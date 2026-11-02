import sys
import socket

import subprocess
import threading

from pathlib import Path
from queue import Queue, Empty, Full

from PyQt5.QtCore import QObject, pyqtSignal

from PyQt5.QtCore import Qt, QTimer, QRectF
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QMainWindow,
    QLabel,
    QPushButton,
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
)

EMOTIONS = [
    "neutral", "joy", "sadness", "anger",
    "fear", "surprise", "disgust"
]

BACKGROUND = "#07111b"
FACE = "#f6cf61"
FACE_EDGE = "#bd7d2a"
FEATURE = "#172132"
TEAR = "#42d6ff"


class PixelFace(QWidget):
    """A 32x32 pixel face with simple emotion transitions."""

    def __init__(self):
        super().__init__()

        self.setMinimumSize(480, 480)

        self.current = "neutral"
        self.previous = "neutral"
        self.target = "neutral"
        self.phase = -1

        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.advance_transition)

    def set_emotion(self, emotion):
        if emotion not in EMOTIONS:
            return

        self.previous = self.current
        self.target = emotion
        self.phase = 0
        self.timer.start()
        self.update()

    def advance_transition(self):
        if self.phase < 2:
            self.phase += 1
            self.update()
        else:
            self.current = self.target
            self.phase = -1
            self.timer.stop()
            self.update()

    @staticmethod
    def pixel(p, x, y, color):
        p.fillRect(x, y, 1, 1, QColor(color))

    @staticmethod
    def line(p, x1, y1, x2, y2, color=FEATURE):
        pen = QPen(QColor(color))
        pen.setWidthF(1)
        pen.setCapStyle(Qt.SquareCap)
        p.setPen(pen)
        p.drawLine(x1, y1, x2, y2)

    @classmethod
    def draw_rect(cls, p, x, y, w, h, color=FEATURE, filled=True):
        if filled:
            p.fillRect(QRectF(x, y, w, h), QColor(color))
        else:
            pen = QPen(QColor(color))
            pen.setWidthF(1)
            p.setPen(pen)
            p.drawRect(QRectF(x, y, w - 1, h - 1))

    @classmethod
    def ellipse(cls, p, x, y, w, h, color=FEATURE, filled=False):
        if filled:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(color))
            p.drawEllipse(QRectF(x, y, w, h))
        else:
            pen = QPen(QColor(color))
            pen.setWidthF(1)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QRectF(x, y, w, h))

    def draw_face(self, p, emotion, eyes_closed=False):
        # Face silhouette: exactly 32x32 logical pixels.
        for y in range(3, 30):
            for x in range(4, 28):
                distance = (
                    ((x - 16) / 11) ** 2
                    + ((y - 16) / 12.5) ** 2
                )

                if distance <= 1:
                    color = FACE_EDGE if distance > 0.82 else FACE
                    self.pixel(p, x, y, color)

        # Eyebrows.
        if emotion == "anger":
            self.line(p, 8, 8, 13, 11)
            self.line(p, 18, 11, 23, 8)

        elif emotion == "sadness":
            self.line(p, 8, 10, 13, 8)
            self.line(p, 19, 8, 24, 10)

        elif emotion in ("fear", "surprise"):
            self.line(p, 8, 7, 13, 7)
            self.line(p, 19, 7, 24, 7)

        elif emotion == "disgust":
            self.line(p, 8, 9, 13, 10)
            self.line(p, 19, 8, 24, 7)

        else:
            self.line(p, 9, 9, 13, 9)
            self.line(p, 19, 9, 23, 9)

        # Eyes.
        if eyes_closed:
            self.line(p, 9, 13, 13, 13)
            self.line(p, 19, 13, 23, 13)

        elif emotion == "joy":
            self.line(p, 9, 13, 11, 15)
            self.line(p, 11, 15, 13, 13)
            self.line(p, 19, 13, 21, 15)
            self.line(p, 21, 15, 23, 13)

        elif emotion == "anger":
            self.draw_rect(p, 10, 12, 3, 2)
            self.draw_rect(p, 20, 12, 3, 2)

        elif emotion == "sadness":
            self.draw_rect(p, 10, 12, 2, 3)
            self.draw_rect(p, 20, 12, 2, 3)
            self.pixel(p, 13, 16, TEAR)

        elif emotion == "fear":
            self.draw_rect(p, 9, 10, 5, 6, filled=False)
            self.draw_rect(p, 19, 10, 5, 6, filled=False)
            self.draw_rect(p, 11, 12, 2, 2)
            self.draw_rect(p, 21, 12, 2, 2)

        elif emotion == "surprise":
            self.ellipse(p, 9, 10, 4, 6)
            self.ellipse(p, 19, 10, 4, 6)

        elif emotion == "disgust":
            self.line(p, 9, 13, 13, 13)
            self.draw_rect(p, 20, 12, 3, 3)

        else:
            self.draw_rect(p, 10, 11, 3, 4)
            self.draw_rect(p, 20, 11, 3, 4)

        # Mouth.
        if emotion == "joy":
            self.line(p, 10, 20, 13, 23)
            self.line(p, 13, 23, 19, 23)
            self.line(p, 19, 23, 22, 20)

        elif emotion == "sadness":
            self.line(p, 10, 23, 13, 21)
            self.line(p, 13, 21, 19, 21)
            self.line(p, 19, 21, 22, 23)

        elif emotion == "anger":
            self.line(p, 12, 22, 20, 22)
            self.line(p, 13, 23, 19, 23)

        elif emotion in ("fear", "surprise"):
            self.ellipse(p, 14, 19, 4, 6)

        elif emotion == "disgust":
            self.line(p, 11, 21, 15, 22)
            self.line(p, 15, 22, 20, 20)
            self.pixel(p, 21, 20, FEATURE)

        else:
            self.line(p, 12, 22, 20, 22)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        p.fillRect(self.rect(), QColor("#02070d"))

        side = min(self.width(), self.height())
        scale = side / 32
        ox = (self.width() - side) / 2
        oy = (self.height() - side) / 2

        p.translate(ox, oy)
        p.scale(scale, scale)
        p.fillRect(QRectF(0, 0, 32, 32), QColor(BACKGROUND))

        # Transition: close eyes, change expression, open eyes.
        if self.phase == 0:
            emotion, closed = self.previous, True
        elif self.phase == 1:
            emotion, closed = self.target, True
        elif self.phase == 2:
            emotion, closed = self.target, False
        else:
            emotion, closed = self.current, False

        self.draw_face(p, emotion, closed)
        p.end()


class PhysicalDisplayUploader(QObject):
    status_changed = pyqtSignal(str)

    def __init__(self, project_dir, parent=None):
        super().__init__(parent)

        self.project_dir = Path(project_dir)
        self.gif_dir = self.project_dir / "emotion_gifs"

        # Only keep the newest pending emotion.
        self.jobs = Queue(maxsize=1)

        # Uploads happen in a background thread so the
        # virtual display remains responsive.
        self.worker_thread = threading.Thread(
            target=self._run,
            daemon=True
        )
        self.worker_thread.start()

    def enqueue(self, emotion):
        if emotion not in EMOTIONS:
            return

        # Replace an older pending emotion if necessary.
        try:
            self.jobs.put_nowait(emotion)
        except Full:
            try:
                self.jobs.get_nowait()
                self.jobs.task_done()
            except Empty:
                pass

            try:
                self.jobs.put_nowait(emotion)
            except Full:
                return

        self.status_changed.emit(
            f"Physical display: queued {emotion}"
        )

    def _run(self):
        while True:
            emotion = self.jobs.get()

            try:
                gif_path = (
                    self.gif_dir /
                    f"{emotion}_transition.gif"
                )

                if not gif_path.is_file():
                    self.status_changed.emit(
                        f"Missing GIF: {gif_path.name}"
                    )
                    continue

                command = [
                    sys.executable,
                    str(self.project_dir / "app.py"),
                    "--address",
                    "auto",
                    "--set-gif",
                    str(gif_path)
                ]

                self.status_changed.emit(
                    f"Uploading {emotion} to physical display..."
                )

                result = subprocess.run(
                    command,
                    cwd=str(self.project_dir),
                    capture_output=True,
                    text=True,
                    timeout=120
                )

                if result.returncode == 0:
                    self.status_changed.emit(
                        f"Physical display updated: {emotion}"
                    )
                else:
                    details = (
                        result.stderr or result.stdout or
                        "Unknown upload error"
                    )

                    self.status_changed.emit(
                        f"Upload failed for {emotion}: "
                        f"{details[-500:]}"
                    )

            except subprocess.TimeoutExpired:
                self.status_changed.emit(
                    f"Upload timed out: {emotion}"
                )

            except Exception as exc:
                self.status_changed.emit(
                    f"Physical display error: {exc}"
                )

            finally:
                self.jobs.task_done()


class VirtualFaceWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Virtual 32x32 Emotion Face")
        self.resize(850, 650)

        root = QWidget()
        self.setCentralWidget(root)

        layout = QHBoxLayout(root)
        left = QVBoxLayout()
        right = QVBoxLayout()

        title = QLabel("Virtual Emotion Face")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")

        subtitle = QLabel(
            "32 x 32 pixels | Seven emotions | Blink transition"
        )

        self.face = PixelFace()

        left.addWidget(title)
        left.addWidget(subtitle)
        left.addWidget(self.face, 1)
        left.addWidget(QLabel(
            "Virtual preview only - no hardware connection yet."
        ))

        right.addWidget(QLabel("Test an emotion"))

        buttons = QGridLayout()
        for i, emotion in enumerate(EMOTIONS):
            button = QPushButton(emotion.title())
            button.setMinimumHeight(42)
            button.clicked.connect(
                lambda checked=False, e=emotion: self.choose(e)
            )
            buttons.addWidget(button, i // 2, i % 2)

        right.addLayout(buttons)

        self.status = QLabel("Current emotion: Neutral")
        self.status.setWordWrap(True)
        right.addWidget(self.status)

        # Initialize the physical iDotMatrix uploader.
        project_dir = Path(__file__).resolve().parent

        self.physical_uploader = PhysicalDisplayUploader(
            project_dir,
            self
        )

        self.physical_uploader.status_changed.connect(
            self.status.setText
        )

        # Listen for emotion labels from Unreal Engine.
        self.udp_socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM
        )
        self.udp_socket.bind(("127.0.0.1", 5005))
        self.udp_socket.setblocking(False)

        self.udp_timer = QTimer(self)
        self.udp_timer.setInterval(100)
        self.udp_timer.timeout.connect(self.poll_udp)
        self.udp_timer.start()

        self.status.setText(
            "Current emotion: Neutral\nListening on 127.0.0.1:5005"
        )

        right.addStretch()

        layout.addLayout(left, 3)
        layout.addLayout(right, 2)

        self.setStyleSheet("""
            QMainWindow, QWidget {
                background: #101923;
                color: #e8eef5;
                font-family: Segoe UI, Arial;
                font-size: 10pt;
            }
            QPushButton {
                background: #233447;
                color: #ffffff;
                border: 1px solid #435d77;
                border-radius: 6px;
                padding: 8px;
            }
            QPushButton:hover {
                background: #2e4964;
            }
        """)

    def poll_udp(self):
        while True:
            try:
                data, _ = self.udp_socket.recvfrom(1024)
            except BlockingIOError:
                break
            except OSError as exc:
                self.status.setText(f"UDP error: {exc}")
                return

            emotion = data.decode(
                "utf-8",
                errors="replace"
            ).strip().lower()

            if emotion in EMOTIONS:
                self.choose(emotion)
            else:
                self.status.setText(
                    f"Unknown emotion received: {emotion}"
                )

    def choose(self, emotion):
        if emotion not in EMOTIONS:
            return

        # Update the virtual face.
        self.face.set_emotion(emotion)

        # Update the physical iDotMatrix display.
        self.physical_uploader.enqueue(emotion)

        self.status.setText(
            f"Selected emotion: {emotion.title()}\n"
            "Virtual and physical displays are updating."
        )


def main():
    app = QApplication(sys.argv)
    window = VirtualFaceWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
