"""A separate workspace for path cleanup and later compositing tools."""
import copy
from pathlib import Path
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainterPath, QPen, QBrush, QPixmap, QPainter
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QDoubleSpinBox, QGraphicsView, QGraphicsScene, QGraphicsItem,
    QSlider, QTabWidget, QWidget, QMessageBox, QFileDialog, QProgressBar, QLineEdit, QCheckBox)
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
        self.export_worker = None
        self.replace_rect = None
        self.add_replacement_tab()
        self.art_rect = None
        self.artwork = None
        self.add_artwork_tab()
        self.add_export_tab()
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
        self.range_start.setValue(index+1)
        self.art_start.setValue(index+1)
        self.tabs.currentChanged.connect(lambda _: self.load(self.timeline.value()))

    def add_replacement_tab(self):
        page = QWidget()
        self.replacement_page = page
        layout = QVBoxLayout(page)
        hint = QLabel('Mark the original text at the start frame. The replacement follows position, scale and rotation.\nThe original region is reconstructed with local inpainting. Detailed backgrounds may smear. Tracking stops at cuts or loss of the region.')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        row = QHBoxLayout()
        self.range_start = QSpinBox()
        self.range_end = QSpinBox()
        for spin in [self.range_start, self.range_end]:
            spin.setRange(1, self.info['frames'])
        self.range_end.setValue(self.info['frames'])
        row.addWidget(QLabel('Start frame'))
        row.addWidget(self.range_start)
        row.addWidget(QLabel('End frame'))
        row.addWidget(self.range_end)
        choose = QPushButton('Mark text region…')
        choose.clicked.connect(self.pick_replacement_region)
        row.addWidget(choose)
        layout.addLayout(row)
        row = QHBoxLayout()
        self.replacement_text = QLineEdit()
        self.replacement_text.setPlaceholderText('Your replacement words')
        row.addWidget(self.replacement_text, 1)
        self.text_color = QLineEdit('#ffffff')
        self.text_color.setMaximumWidth(100)
        row.addWidget(self.text_color)
        run = QPushButton('Track & replace text')
        run.clicked.connect(self.replace_text)
        row.addWidget(run)
        clear = QPushButton('Remove last replacement')
        clear.clicked.connect(self.remove_replacement)
        row.addWidget(clear)
        layout.addLayout(row)
        self.tabs.addTab(page, 'Replace text')

    def pick_replacement_region(self, checked=False, artwork=False):
        from .selection import RegionDialog
        frame = (self.art_start if artwork else self.range_start).value()-1
        pixmap = QPixmap(str(self.project/'frames'/f'{frame:06d}.jpg'))
        dialog = RegionDialog(pixmap, [], self)
        dialog.setWindowTitle('Mark the text or object to replace — one include rectangle')
        if dialog.exec() and dialog.view.regions:
            includes = [r for r in dialog.view.regions if r['mode'] == 'include']
            if len(includes) != 1:
                self.notice.setText('Select exactly one include rectangle for replacement.')
                return
            if artwork:
                self.art_rect = includes[0]['rect']
                self.art_anchor = frame
            else:
                self.replace_rect = includes[0]['rect']
                self.replace_anchor = frame
            self.notice.setText(f'Region marked at frame {frame+1}. Configure the replacement, then track it.')

    def add_artwork_tab(self):
        self.artwork_page = QWidget()
        layout = QVBoxLayout(self.artwork_page)
        hint = QLabel('Replace a marked object with your PNG, WebP or SVG artwork. Transparency and aspect ratio are preserved.\nArtwork follows position, rotation and uniform scale. This version does not transfer body poses, expressions or foreground occlusion.')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        row = QHBoxLayout()
        self.art_start, self.art_end = QSpinBox(), QSpinBox()
        for spin in [self.art_start, self.art_end]:
            spin.setRange(1, self.info['frames'])
        self.art_end.setValue(self.info['frames'])
        row.addWidget(QLabel('Start frame'))
        row.addWidget(self.art_start)
        row.addWidget(QLabel('End frame'))
        row.addWidget(self.art_end)
        region = QPushButton('Mark object region…')
        region.clicked.connect(lambda: self.pick_replacement_region(artwork=True))
        row.addWidget(region)
        layout.addLayout(row)
        row = QHBoxLayout()
        choose = QPushButton('Choose artwork…')
        choose.clicked.connect(self.choose_artwork)
        row.addWidget(choose)
        self.art_label = QLabel('No artwork selected')
        row.addWidget(self.art_label, 1)
        run = QPushButton('Track & replace object')
        run.clicked.connect(self.replace_artwork)
        row.addWidget(run)
        remove = QPushButton('Remove last replacement')
        remove.clicked.connect(self.remove_replacement)
        row.addWidget(remove)
        layout.addLayout(row)
        self.tabs.addTab(self.artwork_page, 'Replace artwork')

    def choose_artwork(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Choose replacement artwork', '', 'Artwork (*.png *.webp *.svg *.jpg *.jpeg)')
        if path:
            self.artwork = path
            self.art_label.setText(Path(path).name)

    def replace_artwork(self):
        from .replacement import create_artwork
        if not self.artwork or not self.art_rect or self.art_anchor != self.art_start.value()-1:
            self.notice.setText('Choose artwork and mark an object at the selected start frame first.')
            return
        start, end = self.art_start.value()-1, self.art_end.value()-1
        self.start_job(lambda progress, cancel: create_artwork(self.project, self.art_rect, start, end,
                                                             self.artwork, progress, cancel))

    def replace_text(self):
        from .replacement import create_text
        if not self.replace_rect or self.replace_anchor != self.range_start.value()-1:
            self.notice.setText('Mark a region at the selected start frame first.')
            return
        if not QColor(self.text_color.text()).isValid():
            self.notice.setText('Enter a color such as #ffffff.')
            return
        text = self.replacement_text.text()
        color = QColor(self.text_color.text()).name()
        start, end = self.range_start.value()-1, self.range_end.value()-1
        self.start_job(lambda progress, cancel: create_text(self.project, self.replace_rect, start, end, text, color, progress, cancel))

    def start_job(self, action):
        from .app import Worker
        self.tabs.setEnabled(False)
        self.timeline.setEnabled(False)
        self.notice.setText('Tracking replacement… Close this workspace to cancel.')
        self.export_worker = Worker(action)
        self.export_worker.progress.connect(lambda i, n, _: self.notice.setText(f'Tracking frame {i} / {n}…'))
        self.export_worker.completed.connect(lambda _: self.notice.setText('Replacement saved. Scrub the timeline here to review tracking. Studio MP4 export includes the composite.'))
        self.export_worker.failed.connect(lambda message: self.notice.setText(message))
        self.export_worker.finished.connect(self.replacement_finished)
        self.export_worker.start()

    def replacement_finished(self):
        self.export_finished()
        self.load(self.timeline.value())

    def remove_replacement(self):
        from .replacement import replacements
        from .pipeline import write_json
        records = replacements(self.project)
        if records:
            records.pop()
            write_json(self.project/'replacements.json', records)
            self.load(self.timeline.value())
            self.notice.setText('Last replacement removed.')

    def add_export_tab(self):
        from .exports import FORMATS
        page = QWidget()
        layout = QVBoxLayout(page)
        hint = QLabel('Export the resolved vector animation, including cleanup edits.\nPNG and ProRes exports carry transparency. SVG animation support varies by design tool. ProRes is video-only; use the studio MP4 export for source audio.')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.export_format = QComboBox()
        self.export_format.addItems(FORMATS)
        layout.addWidget(self.export_format)
        self.include_replacements = QCheckBox('Include replacements and original footage (opaque background)')
        self.include_replacements.setChecked(True)
        layout.addWidget(self.include_replacements)
        self.asset_export = QPushButton('Export animation…')
        self.asset_export.clicked.connect(self.export_assets)
        layout.addWidget(self.asset_export)
        self.export_progress = QProgressBar()
        self.export_progress.setValue(0)
        layout.addWidget(self.export_progress)
        self.tabs.addTab(page, 'Export')

    def export_assets(self):
        from .exports import export_assets, FORMATS
        from .app import Worker
        kind = self.export_format.currentText()
        suffix = FORMATS[kind]
        path, _ = QFileDialog.getSaveFileName(self, 'Export animation', str(self.project/('animation'+suffix)), f'Output (*{suffix})')
        if not path:
            return
        if not Path(path).suffix:
            path += suffix
        self.tabs.setEnabled(False)
        self.timeline.setEnabled(False)
        self.notice.setText('Exporting… Close this workspace to cancel the export.')
        include = self.include_replacements.isChecked()
        self.export_worker = Worker(lambda progress, cancel: export_assets(self.project, path, kind, progress, cancel, include))
        self.export_worker.progress.connect(lambda i, n, _: self.export_progress.setValue(round(100*i/n)))
        self.export_worker.completed.connect(lambda result: self.notice.setText(f'Export saved: {result}'))
        self.export_worker.failed.connect(lambda message: self.notice.setText(message))
        self.export_worker.finished.connect(self.export_finished)
        self.export_worker.start()

    def export_finished(self):
        self.export_worker.deleteLater()
        self.export_worker = None
        self.tabs.setEnabled(True)
        self.timeline.setEnabled(True)

    def done(self, result):
        if self.export_worker is not None:
            self.export_worker.cancel.set()
            self.notice.setText('Cancelling export; close again after it stops.')
            return
        super().done(result)

    def closeEvent(self, event):
        if self.export_worker is not None:
            self.export_worker.cancel.set()
            event.ignore()
        else:
            super().closeEvent(event)

    def load(self, index):
        self.data = resolve_frame(self.project, index)
        tracked = all(isinstance(identity, int) for identity in self.data['path_ids'])
        self.scope.model().item(1).setEnabled(tracked)
        if not tracked:
            self.scope.setCurrentIndex(0)
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
        if self.tabs.currentWidget() in (self.replacement_page, self.artwork_page):
            from .replacement import composite, replacements
            from PySide6.QtGui import QImage
            image = composite(self.project, self.timeline.value())
            rgba = image.tobytes()
            pixmap = QPixmap.fromImage(QImage(rgba, image.width, image.height, image.width*4, QImage.Format.Format_RGBA8888).copy())
            scene.addPixmap(pixmap)
            self.view.setSceneRect(QRectF(pixmap.rect()))
            self.view.fitInView(self.view.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
            lost = sum(r['frames'].get(str(self.timeline.value()), {}).get('lost', False) for r in replacements(self.project))
            if lost:
                self.notice.setText(f'{lost} replacement track(s) lost at this frame. Re-mark a region to start a new segment.')
            return
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
