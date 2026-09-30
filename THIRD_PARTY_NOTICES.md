# Third-party dependencies

The MIT license in `LICENSE` covers VectorFlow's own code and documentation.
Third-party dependencies remain under their respective licenses. This source
repository does not distribute the installed virtual environment or dependency
binaries. Setup downloads packages from PyPI onto the user's computer.

| Dependency | Version | Upstream license / reference |
| --- | --- | --- |
| NumPy | 2.4.6 | BSD-3-Clause; bundled components have additional notices. [Licensing](https://numpy.org/doc/stable/license.html) |
| opencv-python-headless | 5.0.0.93 | Wrapper: MIT; OpenCV: Apache-2.0; wheels include additional components. [Licensing](https://github.com/opencv/opencv-python#licensing) |
| Pillow | 12.3.0 | MIT-CMU (Historical Permission Notice and Disclaimer); bundled components have additional notices. [License](https://github.com/python-pillow/Pillow/blob/main/LICENSE) |
| imageio-ffmpeg | 0.6.0 | Python wrapper: BSD-2-Clause. FFmpeg binaries have separate licenses. [Upstream](https://github.com/imageio/imageio-ffmpeg) |
| PySide6-Essentials / Shiboken6 / Qt | 6.11.2 | LGPL-3.0 / GPL alternatives, with module-specific and third-party terms. [Licenses](https://doc.qt.io/qtforpython-6/licenses.html) |

Consult the license files in the exact installed wheels for complete copyright
notices and terms, including transitive dependencies. This table is an index,
not a replacement for those license texts.

## Binary distribution

An installer or executable bundling dependencies needs a separate review of all
included components and must include their required license texts and notices.
For LGPL Qt components, preserve users' ability to replace the libraries and
meet the applicable source and installation-information requirements. Do not
assume that all Qt modules have the same license.

The Windows FFmpeg executable inspected during release verification is version
7.1 from gyan.dev, configured with `--enable-gpl --enable-version3` and libx264.
It is not MIT-licensed. If redistributing this executable, meet the applicable
GPL requirements, including corresponding source and build information. Check
the actual binary being shipped because builds and platforms can differ.
See [FFmpeg's legal page](https://ffmpeg.org/legal.html).

VectorFlow invokes FFmpeg as a separate command-line process. This release
publishes VectorFlow source and installation instructions, not a bundled binary.

## Fonts and media

VectorFlow uses Segoe UI from the user's Windows installation; the repository
does not include that font. Source videos, imported artwork, audio, and generated
projects are not covered by VectorFlow's MIT license. Use and redistribute those
materials only with appropriate rights. Demo output folders are excluded from Git.
