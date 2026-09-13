"""Region selection in source-image coordinates."""
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPen, QBrush
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QGraphicsView, QGraphicsScene


class RegionView(QGraphicsView):
    def __init__(self, pixmap, regions):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.scene().addPixmap(pixmap)
        self.setSceneRect(QRectF(pixmap.rect()))
        self.regions = [dict(r) for r in regions]
        self.mode = 'include'
        self.start = None
        self.draft = None
        self.boxes = []
        self.setMinimumSize(600, 360)
        self.redraw()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def redraw(self):
        for box in self.boxes:
            self.scene().removeItem(box)
        self.boxes = []
        w, h = self.sceneRect().width(), self.sceneRect().height()
        for region in self.regions:
            x, y, rw, rh = region['rect']
            color = QColor('#64cb91' if region['mode'] == 'include' else '#ff8069')
            pen = QPen(color, 2)
            pen.setCosmetic(True)
            color.setAlpha(35)
            self.boxes.append(self.scene().addRect(QRectF(x*w, y*h, rw*w, rh*h), pen, QBrush(color)))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            point = self.mapToScene(event.position().toPoint())
            if self.sceneRect().contains(point):
                self.start = point
                self.draft = self.scene().addRect(QRectF(point, point), QPen(QColor('#ffbf59'), 2))
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.start is not None:
            rect = QRectF(self.start, self.mapToScene(event.position().toPoint())).normalized().intersected(self.sceneRect())
            self.draft.setRect(rect)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.start is not None:
            rect = self.draft.rect()
            self.scene().removeItem(self.draft)
            self.start = self.draft = None
            if rect.width() >= 8 and rect.height() >= 8:
                w, h = self.sceneRect().width(), self.sceneRect().height()
                self.regions.append(dict(mode=self.mode, rect=[rect.x()/w, rect.y()/h, rect.width()/w, rect.height()/h]))
                self.redraw()
        else:
            super().mouseReleaseEvent(event)


class RegionDialog(QDialog):
    def __init__(self, pixmap, regions, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Selective tracing — draw regions on the first frame')
        self.resize(900, 680)
        layout = QVBoxLayout(self)
        hint = QLabel('Drag rectangles around what to keep or exclude. Regions follow motion during conversion.\nWithout an include region, the whole frame is traced. Exclusions always win. Clear to trace everything.')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.view = RegionView(pixmap, regions)
        layout.addWidget(self.view, 1)
        row = QHBoxLayout()
        mode = QComboBox()
        mode.addItems(['Include subject', 'Exclude clutter'])
        mode.currentIndexChanged.connect(lambda i: setattr(self.view, 'mode', 'include' if i == 0 else 'exclude'))
        row.addWidget(mode)
        clear = QPushButton('Clear regions')
        clear.clicked.connect(self.clear)
        row.addWidget(clear)
        row.addStretch()
        cancel = QPushButton('Cancel')
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        done = QPushButton('Use these regions')
        done.clicked.connect(self.accept)
        row.addWidget(done)
        layout.addLayout(row)

    def clear(self):
        self.view.regions = []
        self.view.redraw()
