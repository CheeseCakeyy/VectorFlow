"""Paper, file tabs, and graph-paper surfaces for the desktop studio."""
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QPushButton
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QComboBox, QProgressBar, QSlider, QButtonGroup, QScrollArea


class FolderButton(QPushButton):
    def __init__(self, name, number, caption, offset, tone):
        super().__init__(name)
        self.number, self.caption, self.offset, self.tone = number, caption, offset, tone
        self.active = False
        self.dark = False
        self.setFixedHeight(48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(f'{name} preview')

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        x = min(self.offset, max(8, self.width()-300))
        path = QPainterPath()
        path.moveTo(0, 35)
        path.lineTo(x, 35)
        path.lineTo(x, 13)
        path.quadTo(x, 1, x+14, 1)
        path.lineTo(x+211, 1)
        path.lineTo(x+251, 35)
        path.lineTo(self.width(), 35)
        path.lineTo(self.width(), 48)
        path.lineTo(0, 48)
        path.closeSubpath()
        bg = self.tone if not self.dark else {'#ffbf59': '#cda55f', '#b8c8bd': '#829a8a', '#dfdfd4': '#a6a799'}[self.tone]
        p.fillPath(path, QColor(bg))
        p.setPen(QPen(QColor('#171916'), 1))
        p.drawPath(path)
        p.setBrush(QColor('#171916' if self.active else bg))
        p.drawEllipse(QRectF(x+12, 9, 25, 25))
        p.setPen(QColor('#ffffff' if self.active else '#171916'))
        p.setFont(QFont('Segoe UI', 9, QFont.Weight.Bold))
        p.drawText(QRectF(x+12, 9, 25, 25), Qt.AlignmentFlag.AlignCenter, self.number)
        p.setPen(QColor('#171916'))
        p.setFont(QFont('Segoe UI', 11, QFont.Weight.Bold))
        p.drawText(QRectF(x+46, 7, 90, 28), Qt.AlignmentFlag.AlignVCenter, self.text())
        p.setFont(QFont('Segoe UI', 9))
        p.drawText(QRectF(x+124, 8, 94, 28), Qt.AlignmentFlag.AlignVCenter, self.caption)
        if self.active:
            p.fillRect(0, 44, self.width(), 4, QColor('#171916'))
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor('#171916'), 2, Qt.PenStyle.DotLine))
            p.drawRoundedRect(QRectF(x+3, 3, 221, 37), 8, 8)


def paper_grid(p, rect, dark):
    p.fillRect(rect, QColor('#20221f' if dark else '#f7f7f0'))
    cell = 72
    for x in range(0, rect.width(), cell):
        for y in range(0, rect.height(), cell):
            if (x//cell+y//cell) % 2 == 0:
                p.fillRect(x, y, cell, cell, QColor('#262924' if dark else '#eeeee7'))
    for step, color in [(12, '#2c2e28' if dark else '#e3e4dc'), (72, '#3b3e35' if dark else '#cbd0c4')]:
        p.setPen(QPen(QColor(color), .6))
        for x in range(0, rect.width(), step):
            p.drawLine(x, 0, x, rect.height())
        for y in range(0, rect.height(), step):
            p.drawLine(0, y, rect.width(), y)


def demo_points(rect):
    w, h = rect.width(), rect.height()
    y = max(175, h*.64)
    amplitude = max(15, min(78, (h-230)*.35))
    return [(w*.12, y+15), (w*.34, y-amplitude), (w*.66, y+amplitude*.8), (w*.86, y-15)]


def empty_art(p, rect, dark, points=None, active=None):
    ink = QColor('#f2f1e8' if dark else '#1b1e19')
    w, h = rect.width(), rect.height()
    p.setPen(ink)
    p.setFont(QFont('Segoe UI', 9, QFont.Weight.Bold))
    p.drawText(QRectF(25, 18, w-50, 22), 'FIG. 01     /     AUTOMATIC MOTION STUDIES')
    p.setFont(QFont('Segoe UI', 25 if h < 360 else (34 if w > 650 else 27), QFont.Weight.Bold))
    p.drawText(QRectF(25, 53, w-50, 115), 'From footage.\nTo formulas.')
    # A cubic construction diagram, drawn with the same mathematical primitive
    # used by the animation renderer; this is the empty-state illustration.
    a, b, c, d = points if points is not None else demo_points(rect)
    p.setPen(QPen(QColor('#8a9180'), 1, Qt.PenStyle.DashLine))
    p.drawLine(*map(int, (*a, *b)))
    p.drawLine(*map(int, (*c, *d)))
    path = QPainterPath()
    path.moveTo(*a)
    path.cubicTo(*b, *c, *d)
    p.setPen(QPen(ink, 4))
    p.drawPath(path)
    for i, (x, yy) in enumerate([a, b, c, d]):
        radius = 17 if i in (0, 3) else 9
        p.setBrush(QColor('#ffbf59') if i in (1, 2) else ink)
        p.setPen(QPen(ink, 1.5))
        p.drawEllipse(QRectF(x-radius, yy-radius, radius*2, radius*2))
        if i == active:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor('#ffbf59'), 2))
            p.drawEllipse(QRectF(x-radius-5, yy-radius-5, radius*2+10, radius*2+10))
        p.setPen(ink)
        p.setFont(QFont('Segoe UI', 9))
        p.drawText(QRectF(x-12, yy+radius+8, 42, 20), f'P{i}')
    p.setPen(ink)
    p.setFont(QFont('Segoe UI', 11))
    p.drawText(QRectF(25, h-44, w-50, 28), 'Drag the points to explore. Double-click to reset.')


def build_layout(window, canvas_type):
    s = window
    base = QWidget()
    s.setCentralWidget(base)
    layout = QVBoxLayout(base)
    layout.setContentsMargins(22, 16, 22, 14)
    layout.setSpacing(0)

    def label(text, name=None):
        item = QLabel(text)
        if name:
            item.setObjectName(name)
        return item

    def button(text, callback, name=None):
        item = QPushButton(text)
        item.clicked.connect(callback)
        item.setCursor(Qt.CursorShape.PointingHandCursor)
        if name:
            item.setObjectName(name)
        return item

    header = QWidget()
    header.setObjectName('header')
    header.setFixedHeight(64)
    top = QHBoxLayout(header)
    top.setContentsMargins(0, 4, 0, 4)
    top.setSpacing(0)
    top.addWidget(label('VectorFlow', 'brand'), 0, Qt.AlignmentFlag.AlignVCenter)
    top.addSpacing(32)
    top.addWidget(label('A TOOL FOR\nMATHEMATICAL MOTION', 'tagline'), 0, Qt.AlignmentFlag.AlignVCenter)
    top.addStretch()
    top.addWidget(label('LOCAL STUDIO   /   01', 'studio'), 0, Qt.AlignmentFlag.AlignVCenter)
    top.addSpacing(24)
    s.theme = button('Light mode', s.toggle_theme, 'theme')
    s.theme.setFixedSize(116, 38)
    top.addWidget(s.theme, 0, Qt.AlignmentFlag.AlignVCenter)
    layout.addWidget(header)
    layout.addSpacing(16)

    tabs = QVBoxLayout()
    tabs.setSpacing(-1)
    s.mode_buttons = QButtonGroup(s)
    for name, number, caption, offset, tone in [
        ('Source', '01', 'The footage', 28, '#ffbf59'),
        ('Vectors', '02', 'The curves', 242, '#dfdfd4'),
        ('Mapping', '03', 'The making', 453, '#b8c8bd')]:
        tab = FolderButton(name, number, caption, offset, tone)
        tab.clicked.connect(lambda checked=False, mode=name: s.set_mode(mode))
        s.mode_buttons.addButton(tab)
        tabs.addWidget(tab)
    layout.addLayout(tabs)

    content = QHBoxLayout()
    content.setSpacing(0)
    stage = QFrame()
    stage.setObjectName('stage')
    main = QVBoxLayout(stage)
    main.setContentsMargins(0, 0, 0, 0)
    main.setSpacing(0)
    heading = QHBoxLayout()
    heading.setContentsMargins(16, 10, 16, 10)
    heading.addWidget(label('●  LIVE WORKSPACE', 'micro'))
    heading.addStretch()
    s.badge = label('WAITING FOR FOOTAGE', 'micro')
    heading.addWidget(s.badge)
    main.addLayout(heading)
    s.canvas = canvas_type()
    main.addWidget(s.canvas, 1)
    transport = QHBoxLayout()
    transport.setContentsMargins(14, 10, 14, 10)
    s.play = button('Play', s.toggle_play, 'transport')
    s.play.setEnabled(False)
    transport.addWidget(s.play)
    s.timeline = QSlider(Qt.Orientation.Horizontal)
    s.timeline.setRange(0, 0)
    s.timeline.valueChanged.connect(s.load_frame)
    transport.addWidget(s.timeline, 1)
    s.time_label = label('0.0s / 0.0s', 'micro')
    transport.addWidget(s.time_label)
    main.addLayout(transport)
    s.equation = label('THE MATHEMATICS\nB(t) = (1−t)³P₀ + 3(1−t)²tP₁ + 3(1−t)t²P₂ + t³P₃', 'equation')
    s.equation.setWordWrap(True)
    s.equation.setMinimumHeight(88)
    main.addWidget(s.equation)
    content.addWidget(stage, 1)

    panel = QFrame()
    panel.setObjectName('panel')
    side = QVBoxLayout(panel)
    side.setContentsMargins(22, 18, 22, 18)
    side.setSpacing(12)
    side.addWidget(label('THE CONTROL ROOM', 'micro'))
    side.addWidget(label('Press play\non an idea.', 'headline'))
    copy = label('One video. A different perspective.\nNo tracing. Just making.', 'muted')
    copy.setWordWrap(True)
    side.addWidget(copy)
    s.file_label = label('No video selected', 'filename')
    s.file_label.setWordWrap(True)
    side.addWidget(s.file_label)
    s.choose = button('+   Choose video', s.choose_video, 'choose')
    side.addWidget(s.choose)
    s.quality = QComboBox()
    s.quality.addItems(['Balanced · 720 px / 12 fps', 'Detailed · 1080 px / 24 fps', 'Quick · 480 px / 8 fps'])
    s.quality.setToolTip('Maximum longest edge. Frame rate never exceeds the source.')
    side.addWidget(s.quality)
    s.convert_button = button('Convert video    ↗', s.start_conversion, 'primary')
    s.convert_button.setEnabled(False)
    side.addWidget(s.convert_button)
    s.progress = QProgressBar()
    s.progress.setValue(0)
    s.progress.setTextVisible(False)
    side.addWidget(s.progress)
    s.cancel_button = button('Cancel processing', s.cancel)
    s.cancel_button.hide()
    side.addWidget(s.cancel_button)
    s.status = label('Ready when you are.\nEverything stays on this computer.', 'muted')
    s.status.setWordWrap(True)
    side.addWidget(s.status)
    side.addStretch()
    s.map_button = button('Watch mapping    ↗', s.watch_mapping, 'mapping')
    s.map_button.setEnabled(False)
    side.addWidget(s.map_button)
    s.open_button = button('Open saved project', s.open_project)
    side.addWidget(s.open_button)
    s.export_button = button('Export MP4    ↓', s.export, 'export')
    s.export_button.setEnabled(False)
    side.addWidget(s.export_button)
    scroll = QScrollArea()
    scroll.setObjectName('controls')
    scroll.setFixedWidth(302)
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidget(panel)
    content.addWidget(scroll)
    layout.addLayout(content, 1)

    footer = QHBoxLayout()
    footer.setContentsMargins(0, 8, 0, 0)
    s.curve_count = label('000', 'count')
    footer.addWidget(s.curve_count)
    footer.addWidget(label('CURVES\nIN THIS FRAME', 'micro'))
    footer.addStretch()
    footer.addWidget(label('FOOTAGE → EQUATIONS → MOTION\nSVG / JSON / MP4', 'micro'))
    footer.addSpacing(28)
    footer.addWidget(label('Made of\npossibilities.', 'signature'))
    layout.addLayout(footer)


def style_window(s):
    bg, panel, fg, muted, border = ('#161813', '#24271f', '#f0f0e5', '#acb1a1', '#515748') if s.dark else ('#eeeee6', '#f7f7f0', '#1b1e19', '#626959', '#292e24')
    s.setStyleSheet(f'''
        QWidget {{ background: {bg}; color: {fg}; font-family: 'Segoe UI'; font-size: 13px; }}
        QLabel {{ background: transparent; }}
        QFrame#panel {{ background: {panel}; border: 1px solid {border}; border-left: 0; }}
        QFrame#stage {{ background: {panel}; border: 1px solid {border}; }}
        QLabel#brand {{ font-size: 34px; font-weight: 700; letter-spacing: -1px; padding-right: 3px; }}
        QLabel#tagline {{ font-size: 11px; font-weight: 500; color: {muted}; border-left: 1px solid {border}; padding: 3px 0 3px 20px; }}
        QLabel#studio {{ font-size: 11px; font-weight: 500; color: {muted}; }}
        QLabel#micro {{ font-size: 10px; font-weight: 600; }}
        QLabel#headline {{ font-size: 32px; font-weight: 750; letter-spacing: -1px; }}
        QLabel#muted {{ color: {muted}; font-size: 12px; }}
        QLabel#filename {{ color: {muted}; font-size: 11px; padding-top: 5px; }}
        QLabel#equation {{ border-top: 1px solid {border}; padding: 12px 16px; font-size: 11px; }}
        QLabel#count {{ font-size: 63px; font-weight: 400; letter-spacing: -4px; padding-right: 16px; }}
        QLabel#signature {{ font-size: 19px; font-weight: 700; letter-spacing: -1px; }}
        QPushButton, QComboBox {{ background: {panel}; border: 1px solid {border}; border-radius: 0; padding: 10px 12px; text-align: left; }}
        QPushButton:hover {{ background: {'#394031' if s.dark else '#e1e5d7'}; }}
        QPushButton:focus {{ border: 2px solid #9b7638; }}
        QPushButton#theme {{ border-radius: 19px; padding: 0; text-align: center; }}
        QPushButton#primary {{ background: #ffbf59; color: #191d16; font-weight: 750; border-color: #191d16; padding: 14px 12px; }}
        QPushButton#primary:hover {{ background: #ffd58c; }}
        QPushButton#mapping {{ background: #b8c8bd; color: #191d16; border-color: #191d16; }}
        QPushButton#export {{ background: {fg}; color: {bg}; font-weight: 700; }}
        QPushButton#transport {{ border-radius: 18px; min-width: 48px; padding: 6px 12px; }}
        QPushButton:disabled {{ color: {muted}; background: {bg}; border-color: {'#444a3d' if s.dark else '#c5c9bc'}; }}
        QPushButton#primary:disabled, QPushButton#mapping:disabled, QPushButton#export:disabled {{ color: {muted}; background: {bg}; border-color: {'#444a3d' if s.dark else '#c5c9bc'}; }}
        QComboBox QAbstractItemView {{ background: {panel}; color: {fg}; selection-background-color: #829a8a; }}
        QProgressBar {{ border: 0; background: {'#42483a' if s.dark else '#dadfd0'}; min-height: 4px; max-height: 4px; }}
        QProgressBar::chunk {{ background: {'#b8c8bd' if s.dark else '#252b20'}; }}
        QSlider::groove:horizontal {{ height: 3px; background: {'#59604e' if s.dark else '#bec6b2'}; }}
        QSlider::handle:horizontal {{ background: {fg}; width: 15px; margin: -6px 0; border-radius: 7px; }}
        QScrollBar:vertical {{ background: {panel}; width: 9px; margin: 0; }}
        QScrollBar::handle:vertical {{ background: {muted}; min-height: 30px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    ''')
    s.canvas.dark = s.dark
    s.canvas.update()
    s.theme.setText('Light mode' if s.dark else 'Dark mode')
    for tab in s.mode_buttons.buttons():
        tab.dark = s.dark
        tab.update()
