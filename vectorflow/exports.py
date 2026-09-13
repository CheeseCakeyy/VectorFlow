"""Export resolved edits as reusable vectors or transparent compositing assets."""
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
import imageio_ffmpeg
from .pipeline import read_json, Cancelled
from .edits import resolve_frame
from .curves import render, svg


FORMATS = {
    'SVG sequence (.zip)': '.zip',
    'Transparent PNG sequence (.zip)': '.zip',
    'Animated SVG (.svg)': '.svg',
    'Vector animation data (.json)': '.json',
    'ProRes 4444 with alpha (.mov)': '.mov',
}


def export_assets(project, output, kind, progress, cancel):
    project, output = Path(project), Path(output)
    info = read_json(project/'project.json')
    if not info['frames']:
        raise ValueError('This project has no frames.')
    if output.resolve() == Path(info['source']).resolve():
        raise ValueError('The source video cannot be overwritten.')
    if kind not in FORMATS:
        raise ValueError('Unknown export format.')
    with tempfile.TemporaryDirectory(prefix='vectorflow-export-', dir=output.parent) as directory:
        root = Path(directory)
        destination = root/('result'+FORMATS[kind])
        archive = zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) if kind.endswith('(.zip)') else None
        frames = []
        animated = []
        try:
            for i in range(info['frames']):
                if cancel.is_set():
                    raise Cancelled('Export cancelled.')
                data = resolve_frame(project, i)
                if kind.startswith('SVG sequence'):
                    archive.writestr(f'{i:06d}.svg', svg(data['paths'], info['width'], info['height'], data['styles'], True))
                elif kind.startswith(('Transparent PNG', 'ProRes')):
                    file = root/f'{i:06d}.png'
                    render(data['paths'], (info['width'], info['height']), styles=data['styles'], transparent=True).save(file)
                    if archive:
                        archive.write(file, file.name)
                        file.unlink()
                elif kind.startswith('Vector animation'):
                    frames.append(data)
                elif kind.startswith('Animated SVG'):
                    parsed = ET.fromstring(svg(data['paths'], info['width'], info['height'], data['styles'], True))
                    group = ET.Element('g', visibility='hidden')
                    for child in parsed:
                        group.append(child)
                    n = info['frames']
                    times, values = ([0], ['visible']) if i == 0 else ([0, i/n], ['hidden', 'visible'])
                    if i < n-1:
                        times.append((i+1)/n)
                        values.append('hidden')
                    times.append(1)
                    values.append('hidden')
                    ET.SubElement(group, 'animate', attributeName='visibility', calcMode='discrete',
                                  dur=f'{n/info["fps"]}s', repeatCount='indefinite',
                                  keyTimes=';'.join(map(str, times)), values=';'.join(values))
                    animated.append(group)
                progress(i+1, info['frames'], str(output))
        finally:
            if archive:
                archive.writestr('timing.json', json.dumps(dict(fps=info['fps'], frames=info['frames'], width=info['width'], height=info['height'])))
                archive.close()
        if kind.startswith('Vector animation'):
            destination.write_text(json.dumps(dict(version=1, fps=info['fps'], width=info['width'], height=info['height'], frames=frames)), encoding='utf-8')
        elif kind.startswith('Animated SVG'):
            ET.register_namespace('', 'http://www.w3.org/2000/svg')
            doc = ET.Element('{http://www.w3.org/2000/svg}svg', width=str(info['width']), height=str(info['height']), viewBox=f'0 0 {info["width"]} {info["height"]}')
            doc.extend(animated)
            destination.write_text(ET.tostring(doc, encoding='unicode'), encoding='utf-8')
        elif kind.startswith('ProRes'):
            command = [imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-loglevel', 'error', '-framerate', str(info['fps']),
                       '-i', str(root/'%06d.png'), '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2:color=black@0',
                       '-c:v', 'prores_ks', '-profile:v', '4', '-pix_fmt', 'yuva444p10le', str(destination)]
            with (root/'encoder.log').open('w') as log:
                process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=log,
                                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                try:
                    while process.poll() is None:
                        if cancel.wait(.1):
                            raise Cancelled('Export cancelled.')
                    if process.returncode:
                        raise RuntimeError('ProRes export failed: '+(root/'encoder.log').read_text()[-1000:])
                finally:
                    if process.poll() is None:
                        process.terminate()
                        process.wait()
        if cancel.is_set():
            raise Cancelled('Export cancelled.')
        destination.replace(output)
    return output
