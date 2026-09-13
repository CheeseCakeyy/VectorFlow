"""Manual integration fixture: generate a demo and render all workspace tabs."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import time
import threading
import cv2
import numpy as np
from PIL import Image
from PySide6.QtWidgets import QApplication
from vectorflow.pipeline import convert, Settings, export_video
from vectorflow.replacement import create_text, create_artwork, composite
from vectorflow.exports import export_assets
from vectorflow.editor import Editor
from vectorflow.app import Window


root = Path('test-output')
root.mkdir(exist_ok=True)
source = root/'studio-fixture.avi'
writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*'MJPG'), 12, (480, 320))
base = np.full((320, 480, 3), (220, 229, 235), np.uint8)
cv2.putText(base, 'OLD TITLE', (65, 75), cv2.FONT_HERSHEY_SIMPLEX, 1.05, (30, 35, 25), 2)
cv2.rectangle(base, (175, 130), (285, 270), (70, 140, 235), -1)
cv2.circle(base, (230, 145), 42, (190, 210, 230), -1)
for x in [215, 245]:
    cv2.circle(base, (x, 140), 5, (20, 30, 20), -1)
cv2.line(base, (215, 158), (245, 158), (30, 30, 30), 3)
for i in range(24):
    matrix = cv2.getRotationMatrix2D((230, 160), i*.2, 1+i*.001)
    matrix[:, 2] += [i*.8, i*.3]
    writer.write(cv2.warpAffine(base, matrix, (480, 320), borderValue=(220, 229, 235)))
writer.release()
project = Path('outputs')/f'feature-demo-{int(time.time())}'
convert(source, project, Settings(style='color', fps=12), lambda i, n, _: print(f'convert {i}/{n}', flush=True))
cancel = threading.Event()
create_text(project, [55/480, 40/320, 210/480, 46/320], 0, 23, 'VECTORFLOW', '#243b24', lambda *_: None, cancel)
art = root/'replacement.svg'
art.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="120"><path d="M50 5 L95 115 L5 115 Z" fill="#ba54d0"/><circle cx="35" cy="78" r="6"/><circle cx="65" cy="78" r="6"/><path d="M35 95 Q50 109 65 95" fill="none" stroke="black" stroke-width="4"/></svg>')
app = QApplication.instance() or QApplication([])
create_artwork(project, [168/480, 95/320, 126/480, 182/320], 0, 23, art, lambda *_: None, cancel)
composite(project, 12).save(root/'feature-composite.png')
export_video(project, project/'replacement-demo.mp4')
export_assets(project, project/'replacement-demo.svg', 'Animated SVG (.svg)', lambda *_: None, cancel, True)
window = Window()
window.load_project(project)
window.show()
app.processEvents()
window.grab().save(str(root/'feature-studio.png'))
editor = Editor(project, 12, window)
editor.show()
app.processEvents()
for i in range(editor.tabs.count()):
    editor.tabs.setCurrentIndex(i)
    app.processEvents()
    editor.grab().save(str(root/f'feature-tab-{i}.png'))
editor.close()
window.close()
print(f'PASS: {project.resolve()}', flush=True)
