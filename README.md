# VectorFlow

A local Windows desktop app that automatically redraws a video as animated cubic Bézier curves. Choose a video, click **Convert video**, and preview or export the result. No manual tracing is required. The original concept is in [idea.md](idea.md).

The studio uses layered folder tabs, graph-paper surfaces, bold typography, and amber/sage accents in both light and dark modes. The three tabs switch between Source, Vectors, and Mapping. A live counter displays the number of curves in the current frame. At smaller window sizes, the control column scrolls so all actions remain reachable.

## Start

Dependencies are already installed in this workspace. Double-click **Start VectorFlow.bat**.

On a fresh machine, install Python 3.11 or newer with Python on PATH, then run **setup.bat** once. Setup downloads the dependencies, including the bundled FFmpeg executable. Processing runs locally and does not upload the video.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m vectorflow.app
```

## Use

1. Choose or drag in a video. The first frame appears immediately.
2. Click **Convert video**. Balanced settings work without adjustment. Optional presets trade detail and frame rate against processing time. Sizes describe the longest edge, with aspect ratio preserved and no upscaling.
3. Watch the preview update as frames finish. Cancel if needed; completed frames remain in the project.
4. Use **Source**, **Vectors**, or **Mapping**, then play or scrub the timeline. **Watch mapping** pauses the frame and reveals its curves over six seconds. Amber dots and lines show the latest five curves' control points; the equations beneath describe the latest revealed curve in image coordinates.
5. Toggle **Light mode / Dark mode** in the top-right corner. This changes the interface and graph. MP4 and SVG export use the consistent dark background and mint outlines.
6. Click **Export MP4** and choose a destination. Available source audio is encoded into the export. Preview playback is silent.

Projects are automatically stored in `outputs/<video-name>-<timestamp>-<id>/`. Use **Open saved project** and select `project.json` to reopen one, including a cancelled conversion with completed frames. Cancelled jobs currently cannot resume; converting again starts a new project.

Each project contains:

- `project.json`: source, dimensions, timing, settings, completion state.
- `frames/000000.json`: explicit cubic control points for each path in that frame.
- `frames/000000.svg`: scalable vector drawing; open in a browser or vector editor.
- `frames/000000.png`: rendered vectors for MP4 encoding.
- `frames/000000.jpg`: source preview for the overlay.

The supplied example's completed demo is in `outputs/apothecary-demo/` when running in the original workspace. Open its `project.json` to explore it.

## How it works

OpenCV decodes frames at the requested output rate. Small changes in nearly stationary pixels are smoothed; moving edges and large scene changes reset or bypass blending. The backend then extracts edge contours, fits least-squares cubic Bézier curves, and recursively subdivides segments that exceed the fitting tolerance. The renderer draws those control points independently of the source image. SVGs contain actual `C` path commands, not embedded raster images.

The desktop UI uses PySide6. Conversion and FFmpeg export run outside the UI thread. Frames are written incrementally to disk rather than holding the entire video in memory. Playback follows elapsed time, skipping display frames if necessary to avoid slowing the animation.

References: [OpenCV contour extraction](https://docs.opencv.org/4.13.0/d4/d73/tutorial_py_contours_begin.html), [Pillow drawing API](https://pillow.readthedocs.io/en/stable/reference/ImageDraw.html).

## Current limits

- This first version creates outline animations. It does not reconstruct filled color regions or reproduce a hand-curated Desmos artwork exactly.
- It draws everything in the input, including subtitles, logos, and app chrome. For the cleanest result, use original footage rather than a recording containing another graphing app.
- Conservative pixel smoothing reduces small noise; it does not track curve identities across frames. Fine details may still flicker, especially in textured live-action footage.
- Variable-frame-rate sources are treated using their reported nominal frame rate. Output timing is quantized to output frames; unusual variable-rate files may need conversion to constant frame rate first.
- Large or long videos can take time and substantial disk space because previews and vector frames are retained. Delete unwanted project folders yourself when finished.
- No Desmos integration, editable pen tool, installer executable, or automatic updates are included.

## Development

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m vectorflow.pipeline "input.mp4" "outputs/my-project" --seconds 3 --export
```

Omit `--seconds` to convert the whole video. The output project directory must not already exist. Source files are never modified. Feature commits separate the concept, curve fitting, conversion/export, UI, and subsequent refinements.
