"""Check runtime imports and the FFmpeg executable after installation."""
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    import cv2
    import numpy
    from PIL import Image
    import imageio_ffmpeg
    from PySide6 import QtCore, QtGui, QtWidgets, QtSvg
    from vectorflow import app, editor, exports, pipeline, replacement

    result = subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-version"],
        check=True, capture_output=True, text=True, timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    print("Runtime imports OK; " + result.stdout.splitlines()[0])


if __name__ == "__main__":
    main()
