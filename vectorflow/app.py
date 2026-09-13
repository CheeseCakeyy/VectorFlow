from __future__ import annotations

import json
import sys
import threading
import time
import uuid
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QFontDatabase
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QComboBox, QFileDialog, QMessageBox,
    QProgressBar, QSlider, QFrame, QButtonGroup)

from .pipeline import Settings, Cancelled, convert, export_video, read_json


ROOT = Path(__file__).resolve().parent.parent


class Worker(QThread):
    progress = Signal(int, int, str)
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, action):
        super().__init__()
        self.cancel = threading.Event()
        self.action = action

    def run(self):
        try:
            self.completed.emit(str(self.action(self.progress.emit, self.cancel)))
        except Cancelled as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(f'{type(exc).__name__}: {exc}')


class Canvas(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(440, 300)
        self.dark = True
        self.mode = 'Vectors'
        self.paths = []
        self.source = QPixmap()
        self.dimensions = (720, 405)
        self.reveal = 1.0

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor('#111823' if self.dark else '#f5f8fc'))
        if self.source.isNull():
            painter.setPen(QColor('#93a4ba' if self.dark else '#53647a'))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             'Your video, redrawn with mathematics.\n\nChoose a video or drop it here to begin.')
            return
        w, h = self.dimensions
        scale = min((self.width()-36)/w, (self.height()-36)/h)
        painter.translate((self.width()-w*scale)/2, (self.height()-h*scale)/2)
        painter.scale(scale, scale)
        painter.setClipRect(QRectF(0, 0, w, h))
        if self.mode != 'Source':
            painter.setPen(QPen(QColor('#202d3c' if self.dark else '#dfe6ef'), .6/scale))
            for x in range(0, w, 40):
                painter.drawLine(x, 0, x, h)
            for y in range(0, h, 40):
                painter.drawLine(0, y, w, y)
            painter.setPen(QPen(QColor('#3b4a60' if self.dark else '#b0bfce'), 1/scale))
            painter.drawLine(w//2, 0, w//2, h)
            painter.drawLine(0, h//2, w, h//2)
        if self.mode in ('Source', 'Mapping'):
            painter.setOpacity(.35 if self.mode == 'Mapping' else 1)
            painter.drawPixmap(QRectF(0, 0, w, h), self.source, QRectF(self.source.rect()))
            painter.setOpacity(1)
        if self.mode == 'Source':
            return
        curves = [c for path in self.paths for c in path]
        count = min(len(curves), int(len(curves)*self.reveal))
        shape = QPainterPath()
        for curve in curves[:count]:
            shape.moveTo(*curve[0])
            shape.cubicTo(*curve[1], *curve[2], *curve[3])
        painter.setPen(QPen(QColor('#75e5cc' if self.dark else '#087e70'), 1.2))
        painter.drawPath(shape)
        if self.mode == 'Mapping':
            for curve in curves[max(0, count-5):count]:
                painter.setPen(QPen(QColor('#efb46b' if self.dark else '#a65712'), .85))
                painter.drawLine(QPointF(*curve[0]), QPointF(*curve[1]))
                painter.drawLine(QPointF(*curve[2]), QPointF(*curve[3]))
                for point in curve:
                    painter.setBrush(QColor('#efb46b' if self.dark else '#a65712'))
                    painter.drawEllipse(QPointF(*point), 2.4/scale, 2.4/scale)


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        # Explicit registration also supports Qt's offscreen platform on Windows.
        font_path = Path('C:/Windows/Fonts/segoeui.ttf')
        if font_path.exists():
            QFontDatabase.addApplicationFont(str(font_path))
        self.setWindowTitle('VectorFlow — video into curves')
        self.resize(1280, 820)
        self.setMinimumSize(1020, 700)
        self.setAcceptDrops(True)
        self.source = None
        self.project = None
        self.info = None
        self.worker = None
        self.closing = False
        self.playing = False
        self.mapping = False
        self.dark = True
        base = QWidget()
        self.setCentralWidget(base)
        layout = QVBoxLayout(base)
        layout.setContentsMargins(26, 20, 26, 18)
        layout.setSpacing(18)
        top = QHBoxLayout()
        brand = QLabel('VectorFlow')
        brand.setObjectName('brand')
        top.addWidget(brand)
        top.addWidget(QLabel('VIDEO → CURVES → MOTION'))
        top.addStretch()
        self.theme = QPushButton('Light mode')
        self.theme.clicked.connect(self.toggle_theme)
        top.addWidget(self.theme)
        layout.addLayout(top)
        content = QHBoxLayout()
        content.setSpacing(22)
        side = QFrame()
        side.setObjectName('panel')
        side.setFixedWidth(274)
        sidebar = QVBoxLayout(side)
        sidebar.setContentsMargins(20, 22, 20, 22)
        sidebar.setSpacing(14)
        title = QLabel('Make motion\nmathematical.')
        title.setObjectName('headline')
        sidebar.addWidget(title)
        subtitle = QLabel('One video in. Thousands of curves out.\nNo tracing required.')
        subtitle.setWordWrap(True)
        sidebar.addWidget(subtitle)
        sidebar.addSpacing(8)
        sidebar.addWidget(QLabel('01   SOURCE VIDEO'))
        self.file_label = QLabel('Choose a video to get started')
        self.file_label.setWordWrap(True)
        sidebar.addWidget(self.file_label)
        self.choose = QPushButton('+  Choose video')
        self.choose.clicked.connect(self.choose_video)
        sidebar.addWidget(self.choose)
        sidebar.addSpacing(12)
        sidebar.addWidget(QLabel('02   AUTOMATIC CONVERSION'))
        self.quality = QComboBox()
        self.quality.addItems(['Balanced · 720 px / 12 fps', 'Detailed · 1080 px / 24 fps', 'Quick · 480 px / 8 fps'])
        self.quality.setToolTip('Maximum longest edge in pixels. Frame rate never exceeds the source.')
        sidebar.addWidget(self.quality)
        self.convert_button = QPushButton('Convert video  →')
        self.convert_button.setObjectName('primary')
        self.convert_button.clicked.connect(self.start_conversion)
        self.convert_button.setEnabled(False)
        sidebar.addWidget(self.convert_button)
        self.cancel_button = QPushButton('Cancel processing')
        self.cancel_button.clicked.connect(self.cancel)
        self.cancel_button.hide()
        sidebar.addWidget(self.cancel_button)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        sidebar.addWidget(self.progress)
        self.status = QLabel('Everything runs locally on your computer.')
        self.status.setWordWrap(True)
        sidebar.addWidget(self.status)
        sidebar.addStretch()
        self.open_button = QPushButton('Open saved project')
        self.open_button.clicked.connect(self.open_project)
        sidebar.addWidget(self.open_button)
        self.export_button = QPushButton('Export MP4  ↗')
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export)
        sidebar.addWidget(self.export_button)
        content.addWidget(side)
        main = QVBoxLayout()
        heading = QHBoxLayout()
        label = QLabel('Animation studio')
        label.setObjectName('section')
        heading.addWidget(label)
        heading.addStretch()
        self.badge = QLabel('READY WHEN YOU ARE')
        heading.addWidget(self.badge)
        main.addLayout(heading)
        modes = QHBoxLayout()
        self.mode_buttons = QButtonGroup(self)
        for name in ['Source', 'Vectors', 'Mapping']:
            button = QPushButton(name)
            button.clicked.connect(lambda checked=False, mode=name: self.set_mode(mode))
            self.mode_buttons.addButton(button)
            modes.addWidget(button)
        modes.addStretch()
        self.map_button = QPushButton('Watch mapping')
        self.map_button.clicked.connect(self.watch_mapping)
        self.map_button.setEnabled(False)
        modes.addWidget(self.map_button)
        main.addLayout(modes)
        self.canvas = Canvas()
        main.addWidget(self.canvas, 1)
        transport = QHBoxLayout()
        self.play = QPushButton('Play')
        self.play.setEnabled(False)
        self.play.clicked.connect(self.toggle_play)
        transport.addWidget(self.play)
        self.timeline = QSlider(Qt.Orientation.Horizontal)
        self.timeline.setRange(0, 0)
        self.timeline.valueChanged.connect(self.load_frame)
        transport.addWidget(self.timeline, 1)
        self.time_label = QLabel('00:00 / 00:00')
        transport.addWidget(self.time_label)
        main.addLayout(transport)
        self.equation = QLabel('THE MATH BEHIND THE MOTION\nB(t) = (1−t)³P₀ + 3(1−t)²tP₁ + 3(1−t)t²P₂ + t³P₃    ·    0 ≤ t ≤ 1')
        self.equation.setObjectName('equation')
        self.equation.setWordWrap(True)
        self.equation.setMinimumHeight(100)
        main.addWidget(self.equation)
        content.addLayout(main, 1)
        layout.addLayout(content, 1)
        footer = QLabel('AUTOMATIC BÉZIER TRACING     /     LOCAL PROCESSING     /     SVG + JSON + MP4')
        layout.addWidget(footer)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)
        self.apply_theme()
        self.set_mode('Vectors')

    def apply_theme(self):
        bg, panel, fg, muted, border = ('#0b1018', '#151e2b', '#edf3fa', '#94a6bd', '#29384d') if self.dark else ('#eaf0f6', '#ffffff', '#172b42', '#50657d', '#cbd7e4')
        self.setStyleSheet(f'''
            QWidget {{ background: {bg}; color: {fg}; font-family: 'Segoe UI'; font-size: 13px; }}
            QLabel {{ background: transparent; }}
            QFrame#panel, QLabel#equation {{ background: {panel}; border: 1px solid {border}; border-radius: 14px; }}
            QLabel#equation {{ padding: 15px; color: {muted}; }}
            QLabel#brand {{ font-size: 25px; font-weight: 700; padding-right: 24px; }}
            QLabel#headline {{ font-size: 25px; font-weight: 650; }}
            QLabel#section {{ font-size: 20px; font-weight: 600; }}
            QPushButton, QComboBox {{ background: {panel}; border: 1px solid {border}; border-radius: 8px; padding: 10px 12px; }}
            QPushButton:hover {{ border-color: #36b99e; }}
            QPushButton:checked {{ background: #164b46; color: #91f4dc; border-color: #36b99e; }}
            QPushButton#primary {{ background: #75e5cc; color: #102822; font-weight: 700; border: none; }}
            QPushButton:disabled {{ color: {muted}; background: {bg}; }}
            QComboBox QAbstractItemView {{ background: {panel}; color: {fg}; selection-background-color: #287768; }}
            QProgressBar {{ border: none; background: {bg}; height: 7px; border-radius: 3px; text-align: center; }}
            QProgressBar::chunk {{ background: #39bca1; border-radius: 3px; }}
            QSlider::groove:horizontal {{ height: 5px; background: {border}; border-radius: 2px; }}
            QSlider::handle:horizontal {{ background: #39bca1; width: 14px; margin: -5px 0; border-radius: 7px; }}
        ''')
        self.canvas.dark = self.dark
        self.canvas.update()
        self.theme.setText('Light mode' if self.dark else 'Dark mode')

    def toggle_theme(self):
        self.dark = not self.dark
        self.apply_theme()

    def choose_video(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Choose a video', '', 'Videos (*.mp4 *.mov *.mkv *.avi *.webm *.m4v);;All files (*)')
        if path:
            self.set_source(path)

    def set_source(self, path):
        if self.worker is not None:
            return
        import cv2
        cap = cv2.VideoCapture(str(path))
        ok, frame = cap.read()
        cap.release()
        if not ok:
            QMessageBox.warning(self, 'Cannot open video', 'Choose a readable video file.')
            return
        from PySide6.QtGui import QImage
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        self.source = Path(path)
        self.project = self.info = None
        self.stop_playback()
        self.timeline.setRange(0, 0)
        self.canvas.source = QPixmap.fromImage(QImage(rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888).copy())
        self.canvas.dimensions = (w, h)
        self.canvas.paths = []
        self.set_mode('Source')
        self.file_label.setText(self.source.name)
        self.file_label.setToolTip(str(self.source))
        self.convert_button.setEnabled(True)
        for button in [self.play, self.map_button, self.export_button]:
            button.setEnabled(False)
        self.status.setText('Ready. Conversion is automatic from here.')
        self.badge.setText('VIDEO LOADED')
        self.progress.setValue(0)

    def set_mode(self, name):
        self.canvas.mode = name
        for button in self.mode_buttons.buttons():
            button.setStyleSheet('background: #164b46; color: #91f4dc; border-color: #36b99e;'
                                if button.text() == name else '')
        self.canvas.update()

    def stop_playback(self):
        self.playing = self.mapping = False
        self.canvas.reveal = 1
        self.play.setText('Play')

    def start_conversion(self):
        if not self.source or self.worker:
            return
        self.stop_playback()
        settings = [Settings(), Settings(max_width=1080, fps=24, tolerance=1, detail=50),
                    Settings(max_width=480, fps=8, tolerance=2, detail=90)][self.quality.currentIndex()]
        destination = ROOT/'outputs'/f'{self.source.stem[:45]}-{time.strftime("%Y%m%d-%H%M%S")}-{uuid.uuid4().hex[:6]}'
        self.project = None
        self.info = None
        self.set_mode('Mapping')
        self.progress.setRange(0, 100)
        self.status.setText('Finding outlines and fitting curves…')
        self.run_worker(lambda progress, cancel: convert(self.source, destination, settings, progress, cancel), 'convert')

    def run_worker(self, action, kind):
        self.worker_kind = kind
        self.choose.setEnabled(False)
        self.open_button.setEnabled(False)
        self.convert_button.setEnabled(False)
        self.quality.setEnabled(False)
        self.export_button.setEnabled(False)
        self.cancel_button.show()
        self.cancel_button.setEnabled(True)
        self.worker = Worker(action)
        self.worker.progress.connect(self.on_progress)
        self.worker.completed.connect(self.on_completed)
        self.worker.failed.connect(self.on_failure)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_progress(self, done, total, path):
        self.project = Path(path)
        self.info = read_json(self.project/'project.json')
        self.progress.setValue(round(done/total*100))
        self.status.setText(f'Tracing frame {done:,} of {total:,}…')
        self.badge.setText(f'{done:,} FRAMES MAPPED')
        self.timeline.setMaximum(done-1)
        if done == 1 or done % 6 == 0:
            self.timeline.setValue(done-1)
            self.load_frame(done-1)

    def on_completed(self, path):
        if self.worker_kind == 'convert':
            self.load_project(path)
            self.status.setText('Conversion complete. Play the animation or watch the mapping.')
        else:
            self.status.setText(f'Export saved to {path}')
            self.status.setToolTip(path)
        self.progress.setRange(0, 100)
        self.progress.setValue(100)

    def on_failure(self, message):
        self.status.setText(message)
        self.progress.setRange(0, 100)
        if self.project and (self.project/'project.json').exists():
            self.info = read_json(self.project/'project.json')
        if not message.startswith(('Conversion cancelled', 'Export cancelled')):
            QMessageBox.warning(self, 'Processing stopped', message)

    def on_finished(self):
        self.worker.deleteLater()
        self.worker = None
        self.choose.setEnabled(True)
        self.open_button.setEnabled(True)
        self.quality.setEnabled(True)
        self.convert_button.setEnabled(bool(self.source))
        self.cancel_button.hide()
        available = bool(self.info and self.info['frames'])
        for button in [self.play, self.map_button, self.export_button]:
            button.setEnabled(available)
        if self.closing:
            self.close()

    def cancel(self):
        if self.worker:
            self.worker.cancel.set()
            self.cancel_button.setEnabled(False)
            self.status.setText('Stopping after the current frame…')

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Open vector project', str(ROOT/'outputs'), 'VectorFlow project (project.json)')
        if path:
            try:
                self.load_project(Path(path).parent)
            except Exception as exc:
                QMessageBox.warning(self, 'Cannot open project', str(exc))

    def load_project(self, path):
        info = read_json(Path(path)/'project.json')
        if info.get('version') != 1 or info.get('frames', 0) < 1 or info.get('fps', 0) <= 0:
            raise ValueError('This is not a usable VectorFlow project.')
        self.stop_playback()
        self.project, self.info = Path(path), info
        self.source = Path(info['source'])
        self.file_label.setText(self.source.name)
        self.timeline.setRange(0, info['frames']-1)
        self.timeline.setValue(0)
        self.load_frame(0)
        self.set_mode('Vectors')
        self.badge.setText(f'{info["frames"]:,} FRAMES · {info["fps"]:g} FPS')
        self.progress.setRange(0, 100)
        self.progress.setValue(round(info['frames']/info.get('planned_frames', info['frames'])*100))
        self.status.setText(f'Project opened · {info["status"]}')
        for button in [self.play, self.map_button, self.export_button]:
            button.setEnabled(True)
        self.convert_button.setEnabled(self.source.is_file() and self.worker is None)

    def load_frame(self, index):
        if not self.project or not self.info:
            return
        stem = self.project/'frames'/f'{index:06d}'
        try:
            paths = read_json(str(stem)+'.json')['paths']
            source = QPixmap(str(stem)+'.jpg')
            if source.isNull():
                raise ValueError('Missing source preview')
        except (OSError, ValueError, KeyError) as exc:
            self.status.setText(f'Cannot load frame {index}: {exc}')
            self.stop_playback()
            return
        self.canvas.paths = paths
        self.canvas.source = source
        self.canvas.dimensions = (self.info['width'], self.info['height'])
        self.canvas.reveal = 1
        self.time_label.setText(f'{index/self.info["fps"]:.1f}s / {self.info["frames"]/self.info["fps"]:.1f}s')
        self.update_equation()
        self.canvas.update()

    def update_equation(self):
        curves = [c for path in self.canvas.paths for c in path]
        count = int(len(curves)*self.canvas.reveal)
        if count:
            c = curves[count-1]
            x = ' + '.join([f'{c[0][0]:.1f}(1−t)³', f'{3*c[1][0]:.1f}(1−t)²t', f'{3*c[2][0]:.1f}(1−t)t²', f'{c[3][0]:.1f}t³'])
            y = ' + '.join([f'{c[0][1]:.1f}(1−t)³', f'{3*c[1][1]:.1f}(1−t)²t', f'{3*c[2][1]:.1f}(1−t)t²', f'{c[3][1]:.1f}t³'])
            self.equation.setText(f'CURVE {count:,} / {len(curves):,}   ·   0 ≤ t ≤ 1   ·   image coordinates (y downward)\nx(t) = {x}\ny(t) = {y}')
        else:
            self.equation.setText('No curves visible yet.\nB(t) = (1−t)³P₀ + 3(1−t)²tP₁ + 3(1−t)t²P₂ + t³P₃')

    def toggle_play(self):
        self.mapping = False
        self.canvas.reveal = 1
        self.playing = not self.playing
        self.play.setText('Pause' if self.playing else 'Play')
        self.play_start = time.monotonic()-self.timeline.value()/self.info['fps']

    def watch_mapping(self):
        self.stop_playback()
        self.set_mode('Mapping')
        self.mapping = True
        self.map_start = time.monotonic()
        self.canvas.reveal = 0

    def tick(self):
        if self.mapping:
            self.canvas.reveal = min(1, (time.monotonic()-self.map_start)/6)
            self.update_equation()
            self.canvas.update()
            if self.canvas.reveal >= 1:
                self.mapping = False
        elif self.playing and self.info:
            index = int((time.monotonic()-self.play_start)*self.info['fps']) % self.info['frames']
            self.timeline.setValue(index)

    def export(self):
        if self.worker or not self.project:
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Export vector animation', str(self.project/'animation.mp4'), 'MP4 video (*.mp4)')
        if path:
            if not Path(path).suffix:
                path += '.mp4'
            self.stop_playback()
            self.progress.setRange(0, 0)
            self.status.setText('Encoding vector animation and preserving available source audio…')
            self.run_worker(lambda progress, cancel: export_video(self.project, path, progress, cancel), 'export')

    def dragEnterEvent(self, event):
        if self.worker is None and event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            self.set_source(urls[0].toLocalFile())

    def closeEvent(self, event):
        if self.worker is not None:
            self.closing = True
            self.cancel()
            event.ignore()
        else:
            event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = Window()
    window.show()
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        if path.is_dir():
            window.load_project(path)
        else:
            window.set_source(path)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
