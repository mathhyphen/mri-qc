"""CLI entry point for mri-qc."""
from __future__ import annotations

import argparse
import os
import socket
import sys
from pathlib import Path


def _local_ip() -> str:
    """Best-effort detection of the machine's LAN IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="mri-qc",
        description="Recursively scan a folder for MRI images and launch a web-based QC review server.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Keyboard shortcuts (in browser):\n"
            "  ← →  select image    1  pass\n"
            "  2  review            3  exclude\n"
            "  0  clear mark        N  jump to next unreviewed\n"
            "  PgUp/PgDn  page      Esc  close lightbox\n"
            "\n"
            "QC state is saved to <folder>/.qc_cache/qc_state.json\n"
            "Thumbnail cache is saved to <folder>/.qc_cache/thumbs/\n"
            "Both persist across server restarts.\n"
            "\n"
            "Environment variables for --tunnel:\n"
            "  NGROK_TOKEN    ngrok auth token\n"
            "  NGROK_DOMAIN   (optional) fixed ngrok domain\n"
        ),
    )
    ap.add_argument("folder", type=Path,
                    help="Root folder containing MRI images (scanned recursively)")
    ap.add_argument("--port", "-p", type=int, default=5000,
                    help="Web server port (default: 5000)")
    ap.add_argument("--host", default="0.0.0.0",
                    help="Bind address (default: 0.0.0.0)")
    ap.add_argument("--cache-dir", type=Path, default=None,
                    help="Thumbnail cache directory (default: <folder>/.qc_cache)")
    ap.add_argument("--state-dir", type=Path, default=None,
                    help="QC state file directory (default: same as --cache-dir)")
    ap.add_argument("--workers", "-w", type=int, default=4,
                    help="Number of background thumbnail generation threads (default: 4)")
    ap.add_argument("--ext", nargs="+", default=[".nii", ".nii.gz"],
                    help="File extensions to scan (default: .nii .nii.gz)")
    ap.add_argument("--tunnel", action="store_true",
                    help="Enable ngrok public tunnel (requires: pip install pyngrok)")
    ap.add_argument("--ngrok-token", type=str, default=None,
                    help="ngrok auth token (or set NGROK_TOKEN env var)")
    ap.add_argument("--ngrok-domain", type=str, default=None,
                    help="ngrok fixed domain (or set NGROK_DOMAIN env var)")
    args = ap.parse_args()

    folder = args.folder.resolve()
    if not folder.is_dir():
        print(f"Error: folder does not exist → {folder}", file=sys.stderr)
        sys.exit(1)

    ip = _local_ip()
    cache = args.cache_dir or (folder / ".qc_cache")
    state_dir = args.state_dir or cache

    print()
    print("  ╔══════════════════════════════════════════════╗")
    print("  ║          🧠  MRI QC Review Server           ║")
    print("  ╚══════════════════════════════════════════════╝")
    print()
    print(f"  📂  Data folder : {folder}")
    print(f"  🌐  Local       : http://127.0.0.1:{args.port}")
    print(f"  📱  LAN         : http://{ip}:{args.port}")
    print(f"  💾  Thumb cache : {cache}")
    print(f"  📝  QC state    : {state_dir}")
    print(f"  🔧  Workers     : {args.workers}")
    print(f"  📋  Extensions  : {', '.join(args.ext)}")
    print()
    print("  Open the LAN address in any browser (phone/tablet/PC) to start QC.")
    print("  QC progress is saved in real-time. Press Ctrl+C to stop.")
    print()

    # ---- ngrok tunnel ----
    if args.tunnel:
        token = args.ngrok_token or os.environ.get("NGROK_TOKEN", "")
        domain = args.ngrok_domain or os.environ.get("NGROK_DOMAIN", "")
        if not token:
            print("  ⚠️  --tunnel requires an ngrok token.", file=sys.stderr)
            print("      Set NGROK_TOKEN env var or pass --ngrok-token <token>", file=sys.stderr)
            print("      Get one free at https://dashboard.ngrok.com/get-started/your-authtoken", file=sys.stderr)
            sys.exit(1)
        try:
            from pyngrok import conf, ngrok as _ngrok
            conf.get_default().auth_token = token
            kwargs = {}
            if domain:
                kwargs["domain"] = domain
            tunnel = _ngrok.connect(args.port, **kwargs)
            print(f"  🌍  Public URL  : {tunnel.public_url}")
            print(f"      (share this link for remote QC access)")
            print()
        except ImportError:
            print("  ⚠️  pyngrok not installed. Run: pip install pyngrok", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"  ⚠️  ngrok tunnel failed: {e}", file=sys.stderr)
            sys.exit(1)

    from mri_qc.server import create_app
    app = create_app(
        folder,
        port=args.port,
        cache_dir=args.cache_dir,
        state_dir=args.state_dir,
        workers=args.workers,
        extensions=tuple(args.ext),
    )
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
