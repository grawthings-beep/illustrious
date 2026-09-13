"""Pack verified completed LoRAs for runpodctl without images or training files."""
from __future__ import annotations

import argparse
import os
import sys
import tarfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from illustrious.models import sha256, validate_header
from illustrious.workflow import catalog


def pack(sources, destination, entries):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError("出力先が既にあります。別のファイル名を指定してください")
    roots = [Path(source).resolve() for source in sources]
    if not roots or any(not root.is_dir() for root in roots):
        raise ValueError("--sourceにはLoRAが入ったフォルダを指定してください")
    selected = []
    for entry in entries:
        candidates = (path for root in roots for path in root.rglob(entry["filename"]) if path.is_file())
        matching = next((p for p in candidates if sha256(p) == entry["sha256"]), None)
        if matching is None:
            raise ValueError(f"名前とSHA-256の一致する完成LoRAがありません: {entry['filename']}")
        validate_header(matching)
        selected.append((matching, entry))
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part-" + uuid.uuid4().hex[:8])
    try:
        with tarfile.open(partial, "w:gz", compresslevel=1, dereference=True) as archive:
            for path, entry in selected:
                archive.add(path, arcname="illustrious-loras/" + entry["filename"], recursive=False)
                print("Packed:", entry["filename"], flush=True)
        # Validate the actual archive payload, including source changes during packing.
        import hashlib
        with tarfile.open(partial, "r:gz") as archive:
            for _, entry in selected:
                with archive.extractfile("illustrious-loras/" + entry["filename"]) as stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() != entry["sha256"]:
                        raise ValueError("パックの照合に失敗しました")
        # Same-directory hard link publishes verified bytes atomically and cannot
        # overwrite an existing destination (NTFS and Linux filesystems).
        os.link(partial, destination)
        partial.unlink()
    except BaseException:
        if partial.exists():
            partial.unlink()
        raise
    print("Saved:", destination, flush=True)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--character", action="append", choices=[c["id"] for c in catalog()["characters"]])
    args = parser.parse_args()
    entries = [entry for entry in catalog()["characters"] if not args.character or entry["id"] in args.character]
    pack(args.source, args.output, entries)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as exc:
        print(f"パック作成を停止しました: {exc}", file=sys.stderr)
        raise SystemExit(1)
