import sys
import socket

import subprocess
import threading

from pathlib import Path
from queue import Queue, Empty, Full

from PyQt5.QtCore import QObject, pyqtSignal

from PyQt5.QtCore import Qt, QTimer, QRectF
from PyQt5.QtGui import QColor, QPainter, QImage
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
    """Displays custom 32x32 faces with a blink transition."""

    def __init__(self):
        super().__init__()

        self.setMinimumSize(480, 480)

        self.image_dir = (
            Path(__file__).resolve().parent / "emotion_faces"
        )

        self.images = {}

        # Load all seven custom emotion faces.
        for emotion in EMOTIONS:
            image_path = self.image_dir / f"{emotion}.png"
            image = QImage(str(image_path))

            if image.isNull():
                raise FileNotFoundError(
                    f"Could not load: {image_path}"
                )

            if image.width() != 32 or image.height() != 32:
                raise ValueError(
                    f"{emotion}.png must be exactly 32x32."
                )

            self.images[emotion] = image

        # Load the custom transparent blink overlay.
        blink_path = self.image_dir / "blink_overlay.png"
        self.blink_overlay = QImage(str(blink_path))

        if self.blink_overlay.isNull():
            raise FileNotFoundError(
                f"Could not load blink overlay: {blink_path}"
            )

        if (
            self.blink_overlay.width() != 32
            or self.blink_overlay.height() != 32
        ):
            raise ValueError(
                "blink_overlay.png must be exactly 32x32."
            )

        if not self.blink_overlay.hasAlphaChannel():
            raise ValueError(
                "blink_overlay.png must have transparency (RGBA)."
            )

        # Current expression.
        self.current = "neutral"
        self.previous = "neutral"
        self.target = "neutral"

        # -1 means no transition.
        # 0 = previous face
        # 1 = eyes closed
        # 2 = eyes remain closed
        # 3 = new face appears
        self.phase = -1

        self.timer = QTimer(self)
        self.timer.setInterval(120)
        self.timer.timeout.connect(self.advance_transition)

    def set_emotion(self, emotion):
        if emotion not in self.images:
            return

        if self.phase == -1 and emotion == self.current:
            return

        # If another emotion arrives during a transition,
        # use the previous target as the starting expression.
        starting_emotion = (
            self.target if self.phase != -1 else self.current
        )

        if starting_emotion == emotion:
            return

        self.previous = starting_emotion
        self.target = emotion
        self.phase = 0

        self.timer.start()
        self.update()

    def advance_transition(self):
        if self.phase < 3:
            self.phase += 1
            self.update()
        else:
            self.current = self.target
            self.phase = -1
            self.timer.stop()
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.SmoothPixmapTransform,
            False
        )

        painter.fillRect(
            self.rect(),
            QColor("#02070d")
        )

        side = min(self.width(), self.height())

        offset_x = (self.width() - side) / 2
        offset_y = (self.height() - side) / 2

        destination = QRectF(
            offset_x,
            offset_y,
            side,
            side
        )

        if self.phase == -1:
            # Normal expression.
            painter.drawImage(
                destination,
                self.images[self.current]
            )

        elif self.phase == 0:
            # Show the previous expression.
            painter.drawImage(
                destination,
                self.images[self.previous]
            )

        elif self.phase in (1, 2):
            # Close the eyes using your custom overlay.
            painter.drawImage(
                destination,
                self.images[self.previous]
            )

            painter.drawImage(
                destination,
                self.blink_overlay
            )

        elif self.phase == 3:
            # Open the eyes with the new expression.
            painter.drawImage(
                destination,
                self.images[self.target]
            )

        painter.end()


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
