"""Tri-planar thumbnail generation for NIfTI volumes.

Generates a single WebP image containing axial, sagittal, and coronal
center slices side by side.
"""
from __future__ import annotations

import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw


def _normalize_slice(s: np.ndarray) -> np.ndarray:
    """Normalize a 2D slice to uint8 grayscale using 1st/99th percentile."""
    s = s.astype(np.float32)
    finite = s[np.isfinite(s)]
    if finite.size == 0:
        return np.zeros(s.shape, dtype=np.uint8)
    lo, hi = np.percentile(finite, [1, 99])
    if hi - lo < 1e-8:
        hi = lo + 1.0
    return np.clip((s - lo) / (hi - lo) * 255, 0, 255).astype(np.uint8)


def generate_thumbnail(nii_path: str | Path, out_path: str | Path,
                       panel_h: int = 300) -> None:
    """Generate a tri-planar WebP thumbnail for a NIfTI file.

    All volumes are reoriented to RAS+ before slicing.
    Display convention (radiological): patient Right shown on image Left.

    Parameters
    ----------
    nii_path : path to .nii or .nii.gz file
    out_path : output .webp path
    panel_h  : height of each panel in pixels
    """
    import nibabel as nib

    img = nib.load(str(nii_path))
    # Reorient to RAS+ canonical orientation
    img = nib.as_closest_canonical(img)
    data = np.asanyarray(img.dataobj)

    # 4D+ → first volume only
    if data.ndim > 3:
        data = data[..., 0]
    if data.ndim < 3:
        raise ValueError(f"Expected 3D volume, got shape {data.shape}")

    # RAS+: axis0=L→R, axis1=P→A, axis2=I→S
    cx = data.shape[0] // 2
    cy = data.shape[1] // 2
    cz = data.shape[2] // 2

    views = [
        # Standard radiological orientation (matches interactive viewer):
        # Axial: A at top, R on left | Sagittal: S at top, A on left | Coronal: S at top, R on left
        # Uniform form: rot180 of the transposed slice
        ("Axial",    np.rot90(data[:, :, cz].astype(np.float32).T, 2)),
        ("Sagittal", np.rot90(data[cx, :, :].astype(np.float32).T, 2)),
        ("Coronal",  np.rot90(data[:, cy, :].astype(np.float32).T, 2)),
    ]

    panel_w = panel_h  # each panel occupies a square cell
    panels = []
    for label, sl in views:
        gray = _normalize_slice(sl)
        im = Image.fromarray(gray, "L").convert("RGB")
        # Fit within panel_w x panel_h, keep aspect ratio
        scale = min(panel_w / max(im.width, 1), panel_h / max(im.height, 1))
        new_w = max(1, round(im.width * scale))
        new_h = max(1, round(im.height * scale))
        im = im.resize((new_w, new_h), Image.Resampling.BILINEAR)
        # Center on fixed-size black cell
        cell = Image.new("RGB", (panel_w, panel_h), (0, 0, 0))
        cell.paste(im, ((panel_w - new_w) // 2, (panel_h - new_h) // 2))
        draw = ImageDraw.Draw(cell)
        draw.rectangle([0, 0, len(label) * 7 + 8, 16], fill=(0, 0, 0))
        draw.text((4, 2), label, fill=(220, 220, 220))
        panels.append(cell)

    total_w = panel_w * len(panels)
    canvas = Image.new("RGB", (total_w, panel_h), (0, 0, 0))
    for i, p in enumerate(panels):
        canvas.paste(p, (i * panel_w, 0))

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, "WEBP", quality=92, method=4)
