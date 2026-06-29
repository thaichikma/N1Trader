"""Launch the N1Trading backtest API server.

Usage:
    python scripts/start_api.py           # default port 8000
    python scripts/start_api.py --port 8080
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev mode)")
    args = parser.parse_args()

    try:
        import uvicorn  # noqa: F401
    except ImportError:
        print("Installing uvicorn + fastapi …")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "uvicorn[standard]", "fastapi", "-q"])

    import uvicorn
    print(f"\n  N1Trading Backtest API")
    print(f"  http://{args.host}:{args.port}\n")
    uvicorn.run(
        "n1trading.api.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        app_dir=str(PROJECT_ROOT),
        timeout_keep_alive=300,
    )


if __name__ == "__main__":
    main()
