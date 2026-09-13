# VectorFlow

A local Windows desktop app that automatically redraws a video as animated cubic Bézier curves. Choose a video, click **Convert video**, and preview or export the result. No manual tracing is required. The original concept is in [idea.md](idea.md).

The studio uses layered folder tabs, graph-paper surfaces, bold typography, and amber/sage accents in both light and dark modes. The three tabs switch between Source, Vectors, and Mapping. A live counter displays the number of curves in the current frame. At smaller window sizes, the control column scrolls so all actions remain reachable.

Before loading a video, drag any of the four points in the Bézier playground to reshape the curve and see its coordinates update. Double-click the playground to reset it. This interactive illustration is separate from automatically converted video paths.

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
2. Click **Convert video** for automatic outline tracing, or choose **Filled-color vectors** first. **Selective tracing** lets you draw include/exclude rectangles on the first frame; they follow motion during conversion. Without selections, the whole frame is traced. Presets trade detail and frame rate against processing time. Sizes describe the longest edge, with aspect ratio preserved and no upscaling.
3. Watch the preview update as frames finish. Cancel if needed; completed frames remain in the project.
4. Use **Source**, **Vectors**, or **Mapping**, then play or scrub the timeline. **Watch mapping** pauses the frame and reveals its curves over six seconds. Amber dots and lines show the latest five curves' control points; the equations beneath describe the latest revealed curve in image coordinates.
5. Toggle **Light mode / Dark mode** in the top-right corner. This changes the interface and graph. Outline exports use mint lines on a dark background; color exports retain their traced colors.
6. Open **Editing workspace** in the header for Cleanup, Replace text, Replace artwork, and Export tabs.
7. Click **Export MP4** in the studio for a video with available source audio. When replacements exist, this exports the composite over the original footage. Otherwise it exports the edited vector animation. Preview playback is silent.

## Editing workspace

- **Cleanup:** pick a path by clicking it or using the path list. Choose a curve and drag its four handles, then **Save shape**. **Delete path** removes unwanted geometry. **Simplify** refits it at your chosen pixel tolerance. Choose **This frame** or **Whole tracked segment**. Shape edits are stored in the path's anchor coordinates and follow its recorded motion. **Undo last edit** reverses the latest cleanup operation. Changing frames without saving discards an unsaved handle adjustment. Hole contours are preserved but do not have independent handles in this editor yet.
- **Replace text:** set start/end frames, mark one include rectangle around the original text at the start frame, enter your words and a color, then **Track & replace text**. Text is fitted into the original region and follows its motion. Scrub to review the composite. No OCR is needed: you choose the text region.
- **Replace artwork:** choose PNG, WebP, JPEG, or SVG artwork, set a frame range, mark the object, and run **Track & replace object**. The aspect ratio and transparency are preserved. SVG artwork is rasterized for compositing; the imported asset is copied into the project. **Remove last replacement** reverses the latest text or artwork replacement.
- **Export:** SVG sequence ZIP, transparent PNG sequence ZIP, animated SVG, vector-animation JSON, and ProRes 4444 MOV with alpha. Cleanup edits are resolved into exports. With **Include replacements and original footage** checked, exports include the composite and have an opaque footage background. SVG composites embed a reconstructed raster background plus editable text or embedded artwork; they are not entirely vector. JSON can include per-frame composite SVGs. ProRes exports are video-only; studio MP4 retains available source audio.

Old projects remain readable. Reconvert an old video to create path IDs needed for edits across tracked segments; those edits are disabled for legacy frames without IDs. Text/artwork tracking works from saved source previews even on older projects.

Projects are automatically stored in `outputs/<video-name>-<timestamp>-<id>/`. Use **Open saved project** and select `project.json` to reopen one, including a cancelled conversion with completed frames. Cancelled jobs currently cannot resume; converting again starts a new project.

Each project contains:

- `project.json`: source, dimensions, timing, settings, completion state.
- `frames/000000.json`: cubic control points, stable path IDs, motion transforms, region tracking, and fill styles.
- `frames/000000.svg`: scalable vector drawing; open in a browser or vector editor.
- `frames/000000.png`: rendered vectors for MP4 encoding.
- `frames/000000.jpg`: source preview for the overlay.
- `edits.json`: reversible cleanup operations; original frame data is not overwritten.
- `replacements.json` and `assets/`: replacement timing, motion, and copied artwork/text assets.

Raw SVG/PNG files in `frames/` represent the initial conversion. Use the Export tab to export subsequent edits and replacements.

The supplied example's completed demo is in `outputs/apothecary-demo/` when running in the original workspace. Open its `project.json` to explore it.

## How it works

OpenCV decodes frames at the requested output rate. Nearly stationary pixels are smoothed. Optical flow and conservative shape matching assign persistent path IDs; confident fits reuse curve topology. Tracked selections use affine motion estimation with local image-alignment refinement. Uncertain paths receive new IDs, and lost selected regions stop tracing instead of jumping to unrelated subjects. Filled-color mode learns a distinct palette from samples across the clip, then fits closed contours and holes. Pure vector SVGs contain actual `C` path commands.

The desktop UI uses PySide6. Conversion and FFmpeg export run outside the UI thread. Frames are written incrementally to disk rather than holding the entire video in memory. Playback follows elapsed time, skipping display frames if necessary to avoid slowing the animation.

References: [OpenCV contour extraction](https://docs.opencv.org/4.13.0/d4/d73/tutorial_py_contours_begin.html), [OpenCV optical flow](https://docs.opencv.org/4.7.0/dc/d6b/group__video__track.html), [Pillow drawing API](https://pillow.readthedocs.io/en/stable/reference/ImageDraw.html).

## Current limits

- Tracking is geometric, not semantic character recognition. Fast deformation, occlusion, low texture, or cuts can break tracks. Lost regions need a newly marked segment; automatic reacquisition and body-pose/expression transfer are not implemented.
- Selected rectangles are not pixel-perfect subject segmentation. A moving box can include some background. If an exclusion track is lost, tracing pauses to avoid accidentally including excluded content.
- Color tracing is palette-based stylization. Small details and gradients can be lost, and fine contour topology can still change. It does not reproduce hand-curated Desmos artwork exactly.
- Replacement removes the marked region with local inpainting. Textured backgrounds may smear. Replacements do not pass behind foreground occluders automatically. Imported artwork follows affine motion rather than articulated poses.
- Replacements currently composite over the original source previews. To export pure transparent vectors, turn off the replacement/footage checkbox. Replacement placement, font, and artwork are set when creating the operation; remove and recreate it to change those settings.
- Variable-frame-rate sources are treated using their reported nominal frame rate. Output timing is quantized to output frames; unusual variable-rate files may need conversion to constant frame rate first.
- Large or long videos can take time and substantial disk space because previews and vector frames are retained. Delete unwanted project folders yourself when finished.
- No Desmos integration, freehand pen tool, installer executable, or automatic updates are included.

## Development

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m vectorflow.pipeline "input.mp4" "outputs/my-project" --seconds 3 --export
.venv\Scripts\python.exe tests/verify_studio.py
```

Omit `--seconds` to convert the whole video. The output project directory must not already exist. Source files are never modified. Feature commits separate the concept, curve fitting, conversion/export, UI, and subsequent refinements.
