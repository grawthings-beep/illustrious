import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from illustrious.models import prepare

if __name__ == "__main__":
    try:
        prepare(os.environ.get("ILLUSTRIOUS_WORKSPACE", "/workspace"), os.environ.get("ILLUSTRIOUS_SKIP_DOWNLOAD") == "1")
    except (ValueError, OSError) as exc:
        print(f"モデルの準備で停止: {exc}", file=sys.stderr)
        raise SystemExit(1)
