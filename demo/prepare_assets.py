"""Generate anonymized demo assets (brain slices) for the promo video.

Reads NIfTI files from a data directory (passed as an argument, never
hard-coded), picks a few representative subjects, and renders:
  - tri-planar thumbnails  -> assets/sub-XX_thumb.webp   (for the grid scene)
  - a series of axial slices -> assets/sub-XX_axial_NN.png (for the slider animation)

All output filenames are anonymized (sub-01, sub-02, ...); no real subject
identifiers ever appear in the generated assets.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


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


def _load_ras(nii_path: Path) -> np.ndarray:
    """Load a NIfTI volume reoriented to RAS+ (first volume if 4D)."""
    import nibabel as nib

    img = nib.as_closest_canonical(nib.load(str(nii_path)))
    data = np.asanyarray(img.dataobj)
    if data.ndim > 3:
        data = data[..., 0]
    return data


def _axial_slice(data: np.ndarray, z: int) -> np.ndarray:
    """Axial slice in standard radiological orientation (A top, R left)."""
    return np.rot90(data[:, :, z].astype(np.float32).T, 2)


def _tri_planar(data: np.ndarray) -> list[np.ndarray]:
    """Return [axial, sagittal, coronal] slices in standard orientation."""
    cx = data.shape[0] // 2
    cy = data.shape[1] // 2
    cz = data.shape[2] // 2
    return [
        np.rot90(data[:, :, cz].astype(np.float32).T, 2),
        np.rot90(data[cx, :, :].astype(np.float32).T, 2),
        np.rot90(data[:, cy, :].astype(np.float32).T, 2),
    ]


def _save_square_panel(sl: np.ndarray, out: Path, size: int) -> None:
    """Save a slice centered on a square black panel."""
    gray = _normalize_slice(sl)
    im = Image.fromarray(gray, "L").convert("RGB")
    scale = min(size / im.width, size / im.height)
    im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))),
                   Image.Resampling.BILINEAR)
    cell = Image.new("RGB", (size, size), (0, 0, 0))
    cell.paste(im, ((size - im.width) // 2, (size - im.height) // 2))
    cell.save(out, "WEBP", quality=92, method=4)


def _save_slice(sl: np.ndarray, out: Path, height: int) -> None:
    """Save a single slice at a fixed display height (keep aspect ratio)."""
    gray = _normalize_slice(sl)
    im = Image.fromarray(gray, "L").convert("RGB")
    w = max(1, round(im.width * height / im.height))
    im = im.resize((w, height), Image.Resampling.BILINEAR)
    im.save(out, "PNG")


def find_nifti(data_dir: Path) -> list[Path]:
    files = []
    for ext in ("*.nii", "*.nii.gz"):
        files.extend(data_dir.rglob(ext))
    return sorted(files)


def pick_representative(files: list[Path], n: int) -> list[Path]:
    """Evenly sample n files from the sorted list for diversity."""
    if len(files) <= n:
        return files
    idx = np.linspace(0, len(files) - 1, n).round().astype(int)
    return [files[i] for i in idx]


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate anonymized demo assets.")
    ap.add_argument("data_dir", type=Path, help="Directory containing NIfTI files (scanned recursively)")
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "assets",
                    help="Output directory for assets")
    ap.add_argument("--n-subjects", type=int, default=5, help="Number of subjects to sample")
    ap.add_argument("--thumb-size", type=int, default=360, help="Tri-planar thumbnail panel size")
    ap.add_argument("--slice-height", type=int, default=540, help="Single-slice display height")
    ap.add_argument("--slice-pcts", type=int, nargs="+", default=[35, 45, 55, 65],
                    help="Axial slice positions as percent of volume height")
    args = ap.parse_args()

    files = find_nifti(args.data_dir)
    if not files:
        raise SystemExit(f"No NIfTI files found under {args.data_dir}")
    print(f"Found {len(files)} NIfTI files")

    chosen = pick_representative(files, args.n_subjects)
    args.out.mkdir(parents=True, exist_ok=True)

    for i, f in enumerate(chosen, start=1):
        sub = f"sub-{i:02d}"
        print(f"[{sub}] <- {f.name}")
        data = _load_ras(f)

        # Tri-planar thumbnail (grid scene): three panels side by side
        panels = [_normalize_slice(sl) for sl in _tri_planar(data)]
        imgs = []
        for gray in panels:
            im = Image.fromarray(gray, "L").convert("RGB")
            scale = min(args.thumb_size / im.width, args.thumb_size / im.height)
            im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))),
                           Image.Resampling.BILINEAR)
            cell = Image.new("RGB", (args.thumb_size, args.thumb_size), (0, 0, 0))
            cell.paste(im, ((args.thumb_size - im.width) // 2, (args.thumb_size - im.height) // 2))
            imgs.append(cell)
        thumb = Image.new("RGB", (args.thumb_size * 3, args.thumb_size), (0, 0, 0))
        for j, im in enumerate(imgs):
            thumb.paste(im, (j * args.thumb_size, 0))
        thumb.save(args.out / f"{sub}_thumb.webp", "WEBP", quality=92, method=4)

        # Axial slice series (slider animation)
        sz = data.shape[2]
        for pct in args.slice_pcts:
            z = int(sz * pct / 100)
            _save_slice(_axial_slice(data, z), args.out / f"{sub}_axial_{pct}.png", args.slice_height)

    print(f"\nDone. Assets written to {args.out.resolve()}")


if __name__ == "__main__":
    main()
