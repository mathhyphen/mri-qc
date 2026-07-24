"""Flask web server for MRI QC review.

Features:
- Recursive NIfTI file scanning (multi-level subfolders)
- Background + on-demand tri-planar thumbnail generation with disk cache
- Persistent QC state (survives browser crash / server restart)
- REST API for file list, QC decisions, stats, CSV export
- Responsive web UI served at /
"""
from __future__ import annotations

import csv
import io
import json
import os
import threading
import time as _time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from flask import (Flask, jsonify, render_template, request,
                   send_file, send_from_directory)

from mri_qc.thumbnail import generate_thumbnail

# ---------------------------------------------------------------------------
# File scanning
# ---------------------------------------------------------------------------

def scan_files(folder: Path, extensions: tuple[str, ...]) -> list[dict]:
    """Recursively find all files matching *extensions* under *folder*."""
    found: list[dict] = []
    for root, dirs, filenames in os.walk(folder):
        # Skip hidden / cache directories
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in sorted(filenames):
            if fname.startswith("."):
                continue
            if any(fname.endswith(ext) for ext in extensions):
                full = Path(root) / fname
                rel = full.relative_to(folder)
                found.append({
                    "id": str(rel).replace("\\", "/"),
                    "name": fname,
                    "folder": str(rel.parent).replace("\\", "/"),
                    "path": str(full),
                    "size_mb": round(full.stat().st_size / 1048576, 2),
                })
    return found

# ---------------------------------------------------------------------------
# QC state persistence
# ---------------------------------------------------------------------------

def _load_state(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text("utf-8"))
        except Exception:
            pass
    return {"decisions": {}}


def _save_state(path: Path, state: dict) -> None:
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), "utf-8")
    tmp.replace(path)          # atomic on NTFS / ext4

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(folder: Path, port: int = 5000, cache_dir: Path | None = None,
               state_dir: Path | None = None, workers: int = 4,
               extensions: tuple[str, ...] = (".nii", ".nii.gz")) -> Flask:
    app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"))
    app.config["JSON_AS_ASCII"] = False

    cache_dir = cache_dir or (folder / ".qc_cache")
    thumbs_dir = cache_dir / "thumbs"
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    # QC state can live in a separate directory (e.g. desktop, network share)
    state_dir = state_dir or cache_dir
    state_dir.mkdir(parents=True, exist_ok=True)

    # ---- scan ----
    files = scan_files(folder, extensions)
    file_index: dict[str, dict] = {f["id"]: f for f in files}

    # ---- QC state ----
    state_path = state_dir / "qc_state.json"
    state = _load_state(state_path)
    state_lock = threading.Lock()

    # ---- background thumbnail generation ----
    gen_status: dict[str, str] = {}   # "queued" | "generating" | "done" | "error"
    gen_lock = threading.Lock()
    # Version tag to bust browser cache on restart
    _thumb_ver = int(_time.time())

    def _thumb_path(fid: str) -> Path:
        return thumbs_dir / (fid.replace("/", "__").replace("\\", "__") + ".webp")

    def _generate_one(fid: str) -> None:
        with gen_lock:
            if gen_status.get(fid) in ("generating", "done"):
                return
            gen_status[fid] = "generating"
        f = file_index.get(fid)
        if not f:
            return
        try:
            generate_thumbnail(f["path"], _thumb_path(fid))
            with gen_lock:
                gen_status[fid] = "done"
        except Exception as exc:
            with gen_lock:
                gen_status[fid] = "error"
            print(f"  [thumbnail error] {fid}: {exc}", flush=True)

    pool = ThreadPoolExecutor(max_workers=workers)
    for f in files:
        tp = _thumb_path(f["id"])
        if tp.exists():
            gen_status[f["id"]] = "done"
        else:
            gen_status[f["id"]] = "queued"
            pool.submit(_generate_one, f["id"])

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    @app.route("/")
    def index():
        html = (Path(__file__).parent / "templates" / "index.html").read_text("utf-8")
        cfg = json.dumps({
            "total": len(files),
            "folder": str(folder),
            "port": port,
        }, ensure_ascii=False)
        return html.replace('"__QC_CONFIG__"', cfg)

    @app.route("/api/stats")
    def api_stats():
        dec = state.get("decisions", {})
        n_pass = sum(1 for d in dec.values() if d.get("status") == "pass")
        n_review = sum(1 for d in dec.values() if d.get("status") == "review")
        n_exclude = sum(1 for d in dec.values() if d.get("status") == "exclude")
        n_error = sum(1 for v in gen_status.values() if v == "error")
        n_thumb_done = sum(1 for v in gen_status.values() if v == "done")
        return jsonify({
            "total": len(files),
            "pass": n_pass,
            "review": n_review,
            "exclude": n_exclude,
            "unreviewed": len(files) - n_pass - n_review - n_exclude,
            "thumb_done": n_thumb_done,
            "thumb_total": len(files),
            "errors": n_error,
        })

    @app.route("/api/files")
    def api_files():
        dec = state.get("decisions", {})
        out = []
        for f in files:
            d = dec.get(f["id"], {})
            out.append({
                "id": f["id"],
                "name": f["name"],
                "folder": f["folder"],
                "size_mb": f["size_mb"],
                "qc": d.get("status", ""),
                "note": d.get("note", ""),
                "ts": d.get("ts", ""),
                "thumb": f"/thumb/{f['id']}?v={_thumb_ver}",
                "thumb_status": gen_status.get(f["id"], "queued"),
            })
        return jsonify(out)

    @app.route("/api/files/<path:fid>")
    def api_file_detail(fid: str):
        f = file_index.get(fid)
        if not f:
            return jsonify({"error": "not found"}), 404
        d = state.get("decisions", {}).get(fid, {})
        return jsonify({**f, "qc": d.get("status", ""), "note": d.get("note", "")})

    @app.route("/api/qc/<path:fid>", methods=["POST"])
    def api_qc_set(fid: str):
        if fid not in file_index:
            return jsonify({"error": "not found"}), 404
        body = request.get_json(force=True, silent=True) or {}
        status = str(body.get("status", "")).strip()
        if status not in ("pass", "review", "exclude", ""):
            return jsonify({"error": "status must be pass|review|exclude|''"}), 400
        with state_lock:
            if status:
                state.setdefault("decisions", {})[fid] = {
                    "status": status,
                    "note": str(body.get("note", "")),
                    "ts": datetime.now(timezone.utc).isoformat(),
                }
            else:
                state.get("decisions", {}).pop(fid, None)
            _save_state(state_path, state)
        return jsonify({"ok": True, "id": fid, "qc": status})

    @app.route("/api/export")
    def api_export():
        dec = state.get("decisions", {})
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["file", "folder", "size_mb", "qc_status", "note", "timestamp"])
        for f in files:
            d = dec.get(f["id"], {})
            w.writerow([
                f["name"], f["folder"], f["size_mb"],
                d.get("status", "unreviewed"),
                d.get("note", ""), d.get("ts", ""),
            ])
        return send_file(
            io.BytesIO(buf.getvalue().encode("utf-8-sig")),
            mimetype="text/csv",
            as_attachment=True,
            download_name="qc_results.csv",
        )

    @app.route("/thumb/<path:fid>")
    def thumb(fid: str):
        tp = _thumb_path(fid)
        if tp.exists():
            resp = send_file(str(tp), mimetype="image/webp")
            resp.headers["Cache-Control"] = "max-age=86400"
            return resp
        # On-demand generation if not yet started
        with gen_lock:
            st = gen_status.get(fid, "queued")
        if st not in ("generating", "done"):
            pool.submit(_generate_one, fid)
        return "", 202

    @app.route("/api/health")
    def health():
        return jsonify({"ok": True, "files": len(files)})

    # ------------------------------------------------------------------
    # Interactive volume viewer endpoint
    # ------------------------------------------------------------------
    volumes_dir = cache_dir / "volumes"
    volumes_dir.mkdir(parents=True, exist_ok=True)

    def _vol_path(fid: str) -> Path:
        return volumes_dir / (fid.replace("/", "__").replace("\\", "__") + ".npy")

    @app.route("/volume/<path:fid>")
    def volume(fid: str):
        """Return the full-resolution 3D volume as raw bytes.

        Format: 12-byte header (3 x int32 LE = shape) + uint8 data.
        The volume is sent at its original resolution (no downsampling)
        so the interactive viewer shows full detail.
        """
        import numpy as np

        f = file_index.get(fid)
        if not f:
            return jsonify({"error": "not found"}), 404

        vp = _vol_path(fid)
        if not vp.exists():
            try:
                import nibabel as nib
                img = nib.as_closest_canonical(nib.load(f["path"]))
                data = np.asanyarray(img.dataobj).astype(np.float32)
                if data.ndim > 3:
                    data = data[..., 0]
                data = data[:, :, :]
                # Normalize to uint8 (full resolution preserved)
                finite = data[np.isfinite(data)]
                if finite.size > 0:
                    lo, hi = np.percentile(finite, [1, 99])
                    if hi - lo < 1e-8:
                        hi = lo + 1.0
                    data = np.clip((data - lo) / (hi - lo) * 255, 0, 255)
                else:
                    data = np.zeros_like(data)
                data = data.astype(np.uint8)
                np.save(str(vp), data)
            except Exception as exc:
                return jsonify({"error": str(exc)}), 500

        data = np.load(str(vp))
        # Header: 3 x int32 LE (shape)
        header = np.array(data.shape[:3], dtype=np.int32).tobytes()
        resp = app.response_class(
            header + data.tobytes(),
            mimetype="application/octet-stream",
        )
        resp.headers["Cache-Control"] = "max-age=86400"
        resp.headers["X-Volume-Shape"] = ",".join(str(s) for s in data.shape[:3])
        return resp

    return app
