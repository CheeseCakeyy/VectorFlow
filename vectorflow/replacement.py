"""Tracked, non-destructive text replacement and compositing."""
import base64
import io
import uuid
from pathlib import Path
from xml.sax.saxutils import escape
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from .pipeline import read_json, write_json, Cancelled
from .tracking import RegionTracker
from .curves import render
from .edits import resolve_frame


def replacements(project):
    path = Path(project)/'replacements.json'
    return read_json(path) if path.exists() else []


def text_asset(text, size, color):
    if not text.strip():
        raise ValueError('Enter replacement text.')
    font_file = Path('C:/Windows/Fonts/segoeui.ttf')
    width, height = size
    for font_size in range(max(6, int(height*.85)), 5, -1):
        font = ImageFont.truetype(str(font_file) if font_file.exists() else 'DejaVuSans.ttf', font_size)
        bounds = font.getbbox(text)
        if bounds[2]-bounds[0] <= width-4 and bounds[3]-bounds[1] <= height-4:
            break
    else:
        raise ValueError('The text does not fit this region. Use a larger region or shorter text.')
    image = Image.new('RGBA', size)
    ImageDraw.Draw(image).text((width/2, height/2), text, font=font, fill=color, anchor='mm')
    return image, font_size


def create_text(project, rect, start, end, text, color, progress, cancel):
    project = Path(project)
    info = read_json(project/'project.json')
    width, height = info['width'], info['height']
    x, y, w, h = np.array(rect)*[width, height, width, height]
    if w < 8 or h < 8 or start < 0 or end < start or end >= info['frames']:
        raise ValueError('Choose a valid region and frame range.')
    asset, font_size = text_asset(text, (round(w), round(h)), color)
    record = dict(id=uuid.uuid4().hex, type='text', text=text, color=color, font_size=font_size,
                  rect=[float(x), float(y), float(w), float(h)], start=start, end=end, frames={})
    tracker = RegionTracker([dict(rect=rect, mode='include')])
    for index in range(start, end+1):
        if cancel.is_set():
            raise Cancelled('Replacement tracking cancelled.')
        with Image.open(project/'frames'/f'{index:06d}.jpg') as image:
            rgb = np.array(image.convert('RGB'))
        _, regions = tracker.update(rgb)
        record['frames'][str(index)] = dict(matrix=regions[0]['transform'], lost=regions[0]['lost'])
        progress(index-start+1, end-start+1, str(project))
    folder = project/'assets'
    folder.mkdir(exist_ok=True)
    relative = f'assets/{record["id"]}.png'
    asset.save(project/relative)
    record['asset'] = relative
    records = replacements(project)
    records.append(record)
    write_json(project/'replacements.json', records)
    return project


def active_replacements(project, index):
    return [record for record in replacements(project)
            if str(index) in record['frames'] and not record['frames'][str(index)]['lost']]


def cleaned_background(project, index, records, background='source'):
    project = Path(project)
    info = read_json(project/'project.json')
    if background == 'vectors':
        data = resolve_frame(project, index)
        image = render(data['paths'], (info['width'], info['height']), styles=data['styles'])
    else:
        with Image.open(project/'frames'/f'{index:06d}.jpg') as source:
            image = source.convert('RGB')
    rgb = np.array(image)
    mask = np.zeros(rgb.shape[:2], np.uint8)
    for record in records:
        x, y, w, h = record['rect']
        matrix = np.array(record['frames'][str(index)]['matrix'])
        corners = np.array([[x, y, 1], [x+w, y, 1], [x+w, y+h, 1], [x, y+h, 1]]) @ matrix[:2].T
        cv2.fillPoly(mask, [np.int32(corners)], 255)
    # Local reconstruction, not a generative model: textured backgrounds may need cleanup.
    if mask.any():
        rgb = cv2.inpaint(rgb, mask, 3, cv2.INPAINT_TELEA)
    return Image.fromarray(rgb).convert('RGBA')


def composite(project, index, background='source'):
    records = active_replacements(project, index)
    result = cleaned_background(project, index, records, background)
    for record in records:
        x, y, _, _ = record['rect']
        motion = np.array(record['frames'][str(index)]['matrix'])
        matrix = motion @ np.array([[1, 0, x], [0, 1, y], [0, 0, 1]])
        with Image.open(Path(project)/record['asset']) as image:
            overlay = np.array(image.convert('RGBA'))
        warped = cv2.warpAffine(overlay, matrix[:2], result.size, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        result = Image.alpha_composite(result, Image.fromarray(warped))
    return result


def composite_svg(project, index):
    records = active_replacements(project, index)
    background = cleaned_background(project, index, records)
    buffer = io.BytesIO()
    background.save(buffer, format='PNG')
    encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
    w, h = background.size
    elements = [f'<image width="{w}" height="{h}" href="data:image/png;base64,{encoded}"/>']
    for record in records:
        matrix = np.array(record['frames'][str(index)]['matrix'])
        a, c, e = matrix[0]
        b, d, f = matrix[1]
        x, y, rw, rh = record['rect']
        elements.append(f'<text transform="matrix({a} {b} {c} {d} {e} {f})" x="{x+rw/2}" y="{y+rh/2}" '
                        f'text-anchor="middle" dominant-baseline="central" font-family="Segoe UI" font-size="{record["font_size"]}" '
                        f'fill="{escape(record["color"])}">{escape(record["text"])}</text>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">' + ''.join(elements) + '</svg>'
