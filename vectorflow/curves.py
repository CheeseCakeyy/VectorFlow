"""Real cubic curve fitting and source-independent vector rendering."""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageDraw


def evaluate(curve, t):
    p = np.asarray(curve, dtype=float)
    t = np.asarray(t, dtype=float)[..., None]
    return (1-t)**3*p[0] + 3*(1-t)**2*t*p[1] + 3*(1-t)*t*t*p[2] + t**3*p[3]


def fit(points, tolerance=1.5):
    """Least-squares cubic fitting, recursively split at worst sample error."""
    p = np.asarray(points, dtype=float)
    if len(p) < 2:
        return []
    if len(p) == 2:
        d = (p[1]-p[0])/3
        return [np.array([p[0], p[0]+d, p[1]-d, p[1]]).tolist()]
    lengths = np.r_[0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
    if lengths[-1] < 1e-8:
        return []
    t = lengths/lengths[-1]
    a = np.column_stack([3*(1-t)**2*t, 3*(1-t)*t*t])
    rhs = p - (1-t[:, None])**3*p[0] - t[:, None]**3*p[-1]
    handles = np.linalg.lstsq(a, rhs, rcond=None)[0]
    curve = np.array([p[0], handles[0], handles[1], p[-1]])
    errors = np.linalg.norm(evaluate(curve, t)-p, axis=1)
    split = int(np.argmax(errors))
    # Restrict huge excursions from underdetermined or ill-conditioned fits.
    span = max(1.0, float(lengths[-1]))
    stable = np.max(np.linalg.norm(handles-p[0], axis=1)) <= span*2
    if errors[split] <= tolerance and stable:
        return [curve.round(3).tolist()]
    split = min(len(p)-2, max(1, split))
    return fit(p[:split+1], tolerance) + fit(p[split:], tolerance)


def trace(rgb, tolerance=1.5, detail=70, mask=None):
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0.8)
    edges = cv2.Canny(gray, detail, detail*2)
    if mask is not None:
        edges = cv2.bitwise_and(edges, mask)
    contours, hierarchy = cv2.findContours(edges, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    # CCOMP preserves disconnected details inside a larger outline, such as eyes,
    # while skipping the reverse boundary of the same thin edge component.
    contours = [c for i, c in enumerate(contours) if hierarchy[0][i][3] == -1]
    paths = []
    for contour in sorted(contours, key=lambda c: cv2.arcLength(c, True), reverse=True):
        if cv2.arcLength(contour, True) < 12:
            continue
        p = contour[:, 0, :].astype(float)
        # Keep original ordered samples; split closed loops into manageable arcs.
        p = np.vstack([p, p[0]])
        segments = []
        for start in range(0, len(p)-1, 48):
            segments.extend(fit(p[start:start+49], tolerance))
        if segments:
            paths.append(segments)
    return paths


def path_d(path):
    if not path:
        return ''
    return f'M {path[0][0][0]:.3f} {path[0][0][1]:.3f} ' + ' '.join('C ' + ' '.join(f'{v:.3f}' for point in c[1:] for v in point) for c in path)


def svg(paths, width, height, styles=None, transparent=False):
    items = []
    for i, path in enumerate(paths):
        if not path:
            continue
        d = path_d(path)
        style = styles[i] if styles else {}
        if style.get('fill'):
            d += ' Z ' + ' '.join(path_d(hole)+' Z' for hole in style.get('holes', []))
            items.append(f'<path d="{d}" fill="{style["fill"]}" stroke="none" fill-rule="evenodd"/>')
        else:
            items.append(f'<path d="{d}"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">' + ('' if transparent else '<rect width="100%" height="100%" fill="#10151f"/>') +
            '<g fill="none" stroke="#75e5cc" stroke-width="1.2" stroke-linecap="round" '
            'stroke-linejoin="round">' + ''.join(items) + '</g></svg>')


def render(paths, size, scale=2, styles=None, transparent=False):
    image = Image.new('RGBA', (size[0]*scale, size[1]*scale), (0, 0, 0, 0) if transparent else '#10151f')
    draw = ImageDraw.Draw(image)
    def polygon(path):
        points = []
        for curve in path:
            length = np.linalg.norm(np.diff(curve, axis=0), axis=1).sum()
            samples = evaluate(curve, np.linspace(0, 1, max(4, min(100, int(length/2)+1))))
            points.extend(tuple(p*scale) for p in samples)
        return points
    for i, path in enumerate(paths):
        points = polygon(path)
        style = styles[i] if styles else {}
        if style.get('fill') and len(points) >= 3:
            mask = Image.new('L', image.size)
            region = ImageDraw.Draw(mask)
            region.polygon(points, fill=255)
            for hole in style.get('holes', []):
                region.polygon(polygon(hole), fill=0)
            image.paste(Image.new('RGBA', image.size, style['fill']), (0, 0), mask)
            continue
        if len(points) >= 2:
            draw.line(points, fill='#75e5cc', width=max(1, round(1.2*scale)), joint='curve')
    result = image.resize(size, Image.Resampling.LANCZOS)
    return result if transparent else result.convert('RGB')
