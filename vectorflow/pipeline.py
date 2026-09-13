from __future__ import annotations

import json
import math
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import cv2
import numpy as np
import imageio_ffmpeg
from PIL import Image

from .curves import render, svg, trace
from .stability import Stabilizer
from .tracking import PathTracker, RegionTracker
from .color import ColorTracer


class Cancelled(Exception):
    pass


@dataclass
class Settings:
    max_width: int = 720
    fps: float = 12
    tolerance: float = 1.5
    detail: int = 70
    max_seconds: float = 0
    regions: list = field(default_factory=list)
    style: str = 'outlines'


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, value):
    target = Path(path)
    temporary = target.with_suffix(target.suffix + '.tmp')
    temporary.write_text(json.dumps(value, separators=(',', ':')), encoding='utf-8')
    # Windows can briefly deny replacement while the UI reads the old manifest.
    # Keep the file atomic and retry after that reader releases its handle.
    for attempt in range(20):
        try:
            temporary.replace(target)
            break
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(.01)


def convert(source, destination, settings=None, progress=None, cancel=None):
    settings = settings or Settings()
    cancel = cancel or threading.Event()
    progress = progress or (lambda *args: None)
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if settings.fps <= 0 or settings.max_width < 64 or settings.tolerance <= 0:
        raise ValueError('Invalid conversion settings.')
    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        raise ValueError('Cannot open this video. Try an MP4 or MOV file.')
    try:
        source_fps = cap.get(cv2.CAP_PROP_FPS)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(source_fps) or source_fps <= 0 or total <= 0:
            raise ValueError('This video does not provide usable frame timing.')
        duration = total/source_fps
        if settings.max_seconds > 0:
            duration = min(duration, settings.max_seconds)
        fps = min(source_fps, settings.fps)
        count = max(1, math.ceil(duration*fps-1e-8))
        destination.mkdir(parents=True, exist_ok=False)
        frames = destination/'frames'
        frames.mkdir()
        manifest = dict(version=1, source=str(source), fps=fps, source_fps=source_fps,
                        frames=0, planned_frames=count, duration=duration,
                        status='processing', settings=asdict(settings), width=0, height=0)
        write_json(destination/'project.json', manifest)
        decoded = -1
        stabilizer = Stabilizer()
        tracker = PathTracker()
        regions = RegionTracker(settings.regions)
        color_tracer = ColorTracer()
        if settings.style == 'color':
            # Include later scenes when learning the fixed palette.
            preview = cv2.VideoCapture(str(source))
            palette_samples = []
            try:
                for position in np.linspace(0, min(total-1, max(0, duration*source_fps-1)), 8):
                    if cancel.is_set():
                        raise Cancelled('Conversion cancelled.')
                    preview.set(cv2.CAP_PROP_POS_FRAMES, int(position))
                    ok, sample = preview.read()
                    if ok:
                        palette_samples.append(cv2.cvtColor(cv2.resize(sample, (80, 80)), cv2.COLOR_BGR2RGB))
            finally:
                preview.release()
            if palette_samples:
                color_tracer.learn_palette(np.concatenate(palette_samples))
        for i in range(count):
            if cancel.is_set():
                raise Cancelled('Conversion cancelled. Completed frames remain available.')
            wanted = min(total-1, math.floor(i*source_fps/fps))
            while decoded < wanted:
                if not cap.grab():
                    raise ValueError(f'Video decoding stopped at source frame {decoded+1}.')
                decoded += 1
            ok, bgr = cap.retrieve()
            if not ok:
                raise ValueError(f'Could not decode source frame {wanted}.')
            h, w = bgr.shape[:2]
            factor = min(1.0, settings.max_width/max(w, h))
            width, height = max(2, round(w*factor)), max(2, round(h*factor))
            rgb = cv2.cvtColor(cv2.resize(bgr, (width, height), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
            mask, region_records = regions.update(rgb)
            stable = stabilizer.apply(rgb)
            if settings.style == 'color':
                paths, styles = color_tracer.trace(stable, settings.tolerance, mask)
            else:
                paths = trace(stable, settings.tolerance, settings.detail, mask)
                styles = [{} for _ in paths]
            tracked = tracker.update(rgb, paths)
            paths = [record['path'] for record in tracked]
            stem = frames/f'{i:06d}'
            Image.fromarray(rgb).save(str(stem)+'.jpg', quality=90)
            write_json(str(stem)+'.json', dict(time=i/fps, paths=paths,
                       path_ids=[r['id'] for r in tracked], transforms=[r['transform'] for r in tracked],
                       regions=region_records, styles=styles))
            Path(str(stem)+'.svg').write_text(svg(paths, width, height, styles), encoding='utf-8')
            render(paths, (width, height), styles=styles).save(str(stem)+'.png')
            manifest.update(frames=i+1, width=width, height=height,
                            lost_regions=[r['id']+1 for r in region_records if r['lost']])
            write_json(destination/'project.json', manifest)
            progress(i+1, count, str(destination))
        manifest['status'] = 'complete'
        write_json(destination/'project.json', manifest)
        return destination
    except Exception as exc:
        if 'manifest' in locals():
            manifest['status'] = 'cancelled' if isinstance(exc, Cancelled) else 'error'
            manifest['error'] = str(exc)
            write_json(destination/'project.json', manifest)
        raise
    finally:
        cap.release()


def export_video(project, output, progress=None, cancel=None):
    """Encode rendered vector frames; copy source audio through AAC when present."""
    project, output = Path(project), Path(output)
    info = read_json(project/'project.json')
    if info['frames'] < 1:
        raise ValueError('No converted frames are available.')
    if output.resolve() == Path(info['source']).resolve():
        raise ValueError('Choose a new file; the source video cannot be overwritten.')
    cancel = cancel or threading.Event()
    from .edits import resolve_frame, operations
    from .replacement import replacements, composite
    frame_directory = project/'frames'
    has_replacements = bool(replacements(project))
    if operations(project) or has_replacements:
        frame_directory = project/'rendered-edits'
        frame_directory.mkdir(exist_ok=True)
        for index in range(info['frames']):
            if cancel.is_set():
                raise Cancelled('Export cancelled.')
            data = resolve_frame(project, index)
            image = composite(project, index) if has_replacements else render(data['paths'], (info['width'], info['height']), styles=data['styles'])
            image.save(frame_directory/f'{index:06d}.png')
    duration = min(info['duration'], info['frames']/info['fps'])
    temporary = output.with_name(output.stem+'.encoding.mp4')
    command = [imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-loglevel', 'error', '-y',
               '-framerate', str(info['fps']), '-i', str(frame_directory/'%06d.png')]
    has_source = Path(info['source']).is_file()
    if has_source:
        command += ['-i', info['source']]
    command += ['-map', '0:v:0']
    if has_source:
        command += ['-map', '1:a:0?', '-c:a', 'aac', '-b:a', '192k']
    command += ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
                '-t', str(duration), '-movflags', '+faststart', str(temporary)]
    log = project/'export.log'
    try:
        with log.open('w', encoding='utf-8') as errors:
            process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=errors,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            try:
                while True:
                    try:
                        code = process.wait(timeout=.2)
                        break
                    except subprocess.TimeoutExpired:
                        if cancel.is_set():
                            raise Cancelled('Export cancelled.')
                if code:
                    raise RuntimeError('Video export failed: ' + log.read_text(encoding='utf-8')[-2000:])
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait()
        temporary.replace(output)
        return output
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Automatically trace a video into cubic curves.')
    parser.add_argument('source')
    parser.add_argument('destination')
    parser.add_argument('--seconds', type=float, default=0)
    parser.add_argument('--width', type=int, default=720)
    parser.add_argument('--fps', type=float, default=12)
    parser.add_argument('--export', action='store_true')
    args = parser.parse_args()
    result = convert(args.source, args.destination, Settings(max_width=args.width, fps=args.fps, max_seconds=args.seconds),
                     progress=lambda i, n, _: print(f'{i}/{n}', flush=True))
    if args.export:
        export_video(result, result/'animation.mp4')
