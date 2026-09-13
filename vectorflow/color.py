"""Trace closed color regions using a fixed clip palette and compound paths."""
import cv2
import numpy as np
from PIL import Image
from .curves import fit


def fit_ring(contour, tolerance):
    points = contour[:, 0].astype(float)
    points = np.vstack([points, points[0]])
    return [curve for start in range(0, len(points)-1, 48) for curve in fit(points[start:start+49], tolerance)]


class ColorTracer:
    def __init__(self, colors=12):
        self.colors = colors
        self.palette = None

    def trace(self, rgb, tolerance=1.5, mask=None):
        if self.palette is None:
            image = Image.fromarray(rgb).resize((160, 160)).quantize(colors=self.colors)
            palette = np.array(image.getpalette(), dtype=np.uint8).reshape(-1, 3)
            self.palette = palette[np.unique(np.asarray(image))]
        pixels = cv2.GaussianBlur(rgb, (3, 3), .7).astype(np.float32)
        labels = np.argmin(((pixels[:, :, None]-self.palette.astype(np.float32))**2).sum(axis=3), axis=2).astype(np.uint8)
        labels = cv2.medianBlur(labels, 3)
        paths, styles = [], []
        for index, color in enumerate(self.palette):
            region = np.uint8(labels == index)*255
            if mask is not None:
                region = cv2.bitwise_and(region, mask)
            contours, hierarchy = cv2.findContours(region, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
            for i, contour in enumerate(contours):
                if hierarchy[0][i][3] != -1 or cv2.contourArea(contour) < 16:
                    continue
                outer = fit_ring(contour, tolerance)
                if not outer:
                    continue
                holes = []
                child = hierarchy[0][i][2]
                while child != -1:
                    ring = fit_ring(contours[child], tolerance)
                    if ring:
                        holes.append(ring)
                    child = hierarchy[0][child][0]
                paths.append(outer)
                styles.append(dict(fill='#' + ''.join(f'{v:02x}' for v in color), holes=holes))
        return paths, styles
