# Video to mathematical vector animation

## The idea

A Windows desktop application that takes a video and automatically turns it into an animated drawing made of mathematical Bézier curves. The only required creative input is the video: no manual tracing, placing points, or editing individual frames. Inspired by animations drawn with equations in Desmos, the application uses its own renderer rather than requiring Desmos.

## User experience

1. Choose a video and start conversion with useful defaults.
2. Watch progress while the application detects outlines and fits actual cubic Bézier paths.
3. Preview the source, the vector animation, or a mapping overlay showing how curves and control points correspond to the source image. Pause and scrub through frames to inspect equations.
4. Export the animation as MP4 and retain vector data and SVG frames for reuse.

The mapping view should make the mathematics tangible: reveal paths progressively, display control points and handles, and show the parametric equation for a selected/generated curve. Viewing the mapping is optional and must never require manual tracing.

## Technical direction

- Python backend, with OpenCV and NumPy for video decoding, outline extraction, and numerical curve fitting.
- Python desktop interface initially, using Tkinter and Pillow to keep installation approachable.
- Fit cubic curves to ordered contours, with an error threshold and subdivision; do not merely label a raster edge filter as vectorization.
- Render curves independently of the source pixels. Store explicit control points per frame; export SVG paths and a reusable JSON project format.
- Process in a background worker with progress, cancellation, clear errors, and bounded memory through files on disk.
- Preserve source timing; retain audio in video export when FFmpeg is available.
- Reduce temporal instability conservatively without blurring motion or mixing unrelated shapes across cuts. Fully consistent topology across frames remains a challenging quality improvement.

For a cubic curve with points P0, P1, P2, P3:

    B(t) = (1-t)^3 P0 + 3(1-t)^2 t P1 + 3(1-t)t^2 P2 + t^3 P3, 0 <= t <= 1

## Implementation milestones

1. Commit this idea before implementation.
2. Build and test automatic frame tracing, cubic fitting, and vector serialization.
3. Build automatic video processing, progress/cancellation, and export.
4. Build the desktop input, playback, timeline, and mapping visualization.
5. Validate against synthetic fixtures and the supplied example video; document setup, operation, and current limitations.

Commit each working feature separately. Prefer an honest, usable implementation with measurable conversion quality over claims of perfect tracing. The supplied Desmos video is a visual reference and test input; arbitrary original footage, especially anime and high-contrast artwork, is the intended input.

## Later improvements

Color-region tracing, stronger motion-aware path tracking, GPU acceleration, packaged Windows installer, and optional Desmos equation export. These are extensions beyond the initial outline-animation application.
