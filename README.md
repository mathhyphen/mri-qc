# mri-qc

Web-based MRI quality control review tool. Recursively scans a folder for NIfTI images, generates tri-planar thumbnails (Axial / Sagittal / Coronal), and serves a responsive web UI for manual QC on any device.

## Features

- **Recursive scanning** — finds all `.nii` / `.nii.gz` files in nested subfolders
- **Tri-planar thumbnails** — RAS+ reoriented, radiological convention (R on left)
- **Responsive web UI** — works on phone, tablet, and desktop
- **Persistent QC state** — decisions saved in real-time to JSON (survives crash/restart)
- **Thumbnail caching** — generated once, reused on restart
- **Keyboard shortcuts** — `1/2/3` for pass/review/exclude, `N` for next unreviewed
- **CSV export** — one-click download of all QC decisions
- **Public tunnel** — optional ngrok integration for remote access

## Installation

```bash
pip install .
# or for development:
pip install -e .
# with ngrok tunnel support:
pip install -e ".[tunnel]"
```

## Usage

```bash
# Basic — scan a folder and start the server
mri-qc /path/to/mri/data

# Custom port and workers
mri-qc /path/to/data --port 8080 --workers 8

# Separate QC state location
mri-qc /path/to/data --state-dir /path/to/results

# Enable public access via ngrok tunnel
export NGROK_TOKEN=your_token_here
export NGROK_DOMAIN=your-name.ngrok-free.dev   # optional fixed domain
mri-qc /path/to/data --tunnel
```

Open the printed URL in any browser to start reviewing.

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `← →` | Select image |
| `1` | Pass |
| `2` | Review |
| `3` | Exclude |
| `0` | Clear mark |
| `N` | Jump to next unreviewed |
| `PgUp/PgDn` | Change page |
| `Esc` | Close lightbox |

## CLI Options

```
mri-qc --help
```

| Option | Default | Description |
|--------|---------|-------------|
| `folder` | (required) | Root folder to scan recursively |
| `--port, -p` | 5000 | Web server port |
| `--host` | 0.0.0.0 | Bind address |
| `--cache-dir` | `<folder>/.qc_cache` | Thumbnail cache directory |
| `--state-dir` | same as cache-dir | QC state JSON location |
| `--workers, -w` | 4 | Thumbnail generation threads |
| `--ext` | `.nii .nii.gz` | File extensions to scan |
| `--tunnel` | off | Enable ngrok public tunnel |
| `--ngrok-token` | `$NGROK_TOKEN` | ngrok auth token |
| `--ngrok-domain` | `$NGROK_DOMAIN` | Fixed ngrok domain |

## Requirements

- Python ≥ 3.9
- Flask, nibabel, numpy, Pillow
- (optional) pyngrok for `--tunnel`

## License

MIT
