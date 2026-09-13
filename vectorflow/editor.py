"""A separate workspace for path cleanup and later compositing tools."""
import copy
from pathlib import Path
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainterPath, QPen, QBrush, QPixmap, QPainter
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QDoubleSpinBox, QGraphicsView, QGraphicsScene, QGraphicsItem,
    QSlider, QTabWidget, QWidget, QMessageBox)
from .pipeline import read_json
from .edits import resolve_frame, add_edit, undo


def qt_path(path):
    shape = QPainterPath()
    if path:
        shape.moveTo(*path[0][0])
        for curve in path:
            shape.cubicTo(*curve[1], *curve[2], *curve[3])
    return shape


class EditView(QGraphicsView):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setMinimumSize(500, 300)
        self.handles = []

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def mousePressEvent(self, event):
        item = self.itemAt(event.position().toPoint())
        if item is not None and item.data(0) is not None:
            self.owner.path_choice.setCurrentIndex(int(item.data(0)))
        super().mousePressEvent(event)


class Editor(QDialog):
    def __init__(self, project, index=0, parent=None):
        super().__init__(parent)
        self.project = Path(project)
        self.info = read_json(self.project/'project.json')
        self.setWindowTitle('VectorFlow — editing workspace')
        self.resize(1100, 820)
        self.data = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('EDITING WORKSPACE  /  Changes are saved as reversible project edits.'))
        self.tabs = QTabWidget()
        cleanup = QWidget()
        controls = QVBoxLayout(cleanup)
        hint = QLabel('Choose a path, then a curve. Drag its four amber handles and save the shape.\nUse “Whole tracked segment” to carry an edit with the path’s motion. Undo removes the most recent cleanup operation.')
        hint.setWordWrap(True)
        controls.addWidget(hint)
        row = QHBoxLayout()
        self.path_choice = QComboBox()
        self.path_choice.setMinimumWidth(200)
        self.path_choice.currentIndexChanged.connect(self.select_path)
        row.addWidget(self.path_choice)
        row.addWidget(QLabel('Curve'))
        self.curve = QSpinBox()
        self.curve.setMinimum(1)
        self.curve.valueChanged.connect(self.show_handles)
        row.addWidget(self.curve)
        self.scope = QComboBox()
        self.scope.addItems(['This frame', 'Whole tracked segment'])
        row.addWidget(self.scope)
        controls.addLayout(row)
        actions = QHBoxLayout()
        for title, action in [('Delete path', 'delete'), ('Save shape', 'shape'), ('Simplify', 'simplify')]:
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, action=action: self.apply_edit(action))
            actions.addWidget(button)
        self.tolerance = QDoubleSpinBox()
        self.tolerance.setRange(.5, 20)
        self.tolerance.setValue(3)
        self.tolerance.setSuffix(' px tolerance')
        actions.addWidget(self.tolerance)
        undo_button = QPushButton('Undo last edit')
        undo_button.clicked.connect(self.undo)
        actions.addWidget(undo_button)
        controls.addLayout(actions)
        self.tabs.addTab(cleanup, 'Cleanup')
        layout.addWidget(self.tabs)
        self.view = EditView(self)
        layout.addWidget(self.view, 1)
        row = QHBoxLayout()
        self.timeline = QSlider(Qt.Orientation.Horizontal)
        self.timeline.setRange(0, self.info['frames']-1)
        self.timeline.setValue(index)
        self.timeline.valueChanged.connect(self.load)
        row.addWidget(self.timeline, 1)
        self.frame_label = QLabel()
        row.addWidget(self.frame_label)
        layout.addLayout(row)
        self.notice = QLabel('')
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        done = QPushButton('Done — return to studio')
        done.clicked.connect(self.accept)
        layout.addWidget(done)
        self.load(index)

    def load(self, index):
        self.data = resolve_frame(self.project, index)
        self.path_choice.blockSignals(True)
        self.path_choice.clear()
        for i, identity in enumerate(self.data['path_ids']):
            self.path_choice.addItem(f'Path {i+1} · track {identity}')
        self.path_choice.blockSignals(False)
        self.frame_label.setText(f'Frame {index+1} / {self.info["frames"]} · {index/self.info["fps"]:.2f}s')
        self.select_path(0)

    def select_path(self, index):
        self.view.handles = []
        scene = self.view.scene()
        scene.clear()
        pixmap = QPixmap(str(self.project/'frames'/f'{self.timeline.value():06d}.jpg'))
        scene.addPixmap(pixmap).setOpacity(.25)
        self.view.setSceneRect(QRectF(0, 0, self.info['width'], self.info['height']))
        self.path_items = []
        for i, path in enumerate(self.data['paths']):
            shape = qt_path(path)
            style = self.data['styles'][i]
            if style.get('fill'):
                shape.closeSubpath()
                for hole in style.get('holes', []):
                    inner = qt_path(hole)
                    inner.closeSubpath()
                    shape.addPath(inner)
                shape.setFillRule(Qt.FillRule.OddEvenFill)
            item = scene.addPath(shape, QPen(QColor('#ffbf59' if i == index else '#80bba0'), 1.4),
                                 QBrush(QColor(style['fill'])) if style.get('fill') else QBrush(Qt.BrushStyle.NoBrush))
            item.setData(0, i)
            self.path_items.append(item)
        self.curve.blockSignals(True)
        self.curve.setRange(1, len(self.data['paths'][index]) if 0 <= index < len(self.data['paths']) else 1)
        self.curve.setValue(1)
        self.curve.blockSignals(False)
        self.show_handles()
        self.view.fitInView(self.view.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def show_handles(self):
        for handle in self.view.handles:
            self.view.scene().removeItem(handle)
        self.view.handles = []
        index = self.path_choice.currentIndex()
        if index < 0 or not self.data['paths']:
            return
        for point in self.data['paths'][index][self.curve.value()-1]:
            item = Handle(self, point)
            self.view.scene().addItem(item)
            self.view.handles.append(item)

    def edited_path(self):
        path = copy.deepcopy(self.data['paths'][self.path_choice.currentIndex()])
        segment = self.curve.value()-1
        edited = [[h.pos().x(), h.pos().y()] for h in self.view.handles]
        # Shared endpoints move together to keep the outline continuous.
        old = copy.deepcopy(path[segment])
        for c in path:
            if c[0] == old[0]:
                c[0] = edited[0].copy()
            if c[3] == old[0]:
                c[3] = edited[0].copy()
            if c[0] == old[3]:
                c[0] = edited[3].copy()
            if c[3] == old[3]:
                c[3] = edited[3].copy()
        path[segment] = edited
        return path

    def preview_shape(self):
        if len(self.view.handles) == 4:
            self.path_items[self.path_choice.currentIndex()].setPath(qt_path(self.edited_path()))

    def apply_edit(self, action):
        try:
            add_edit(self.project, self.timeline.value(), self.path_choice.currentIndex(), action,
                     self.scope.currentIndex() == 1,
                     self.edited_path() if action == 'shape' else None, self.tolerance.value())
            self.load(self.timeline.value())
            self.notice.setText('Saved. Preview and exports use this edit. Original tracing data is unchanged.')
        except Exception as exc:
            QMessageBox.warning(self, 'Edit could not be saved', str(exc))

    def undo(self):
        undo(self.project)
        self.load(self.timeline.value())


from PySide6.QtWidgets import QGraphicsEllipseItem


class Handle(QGraphicsEllipseItem):
    def __init__(self, editor, point):
        super().__init__(-4, -4, 8, 8)
        self.editor = editor
        self.setBrush(QColor('#ffbf59'))
        self.setPen(QPen(QColor('#1b2118'), 1))
        self.setPos(*point)
        self.setZValue(10)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.editor.preview_shape()
        return super().itemChange(change, value)
