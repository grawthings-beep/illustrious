"""Verified, resumable model downloads; credentials never enter URLs or logs."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import struct
import uuid
from pathlib import Path
from urllib.parse import urlparse

from .workflow import catalog


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_header(path, checkpoint=False):
    with Path(path).open("rb") as stream:
        raw = stream.read(8)
        if len(raw) != 8:
            raise ValueError("safetensorsヘッダーが短すぎます")
        length = struct.unpack("<Q", raw)[0]
        if not 0 < length < 100_000_000:
            raise ValueError("safetensorsヘッダーが不正です")
        header = json.loads(stream.read(length))
    keys = [key for key in header if key != "__metadata__"]
    if checkpoint and not (any(k.startswith("conditioner.embedders.1.") for k in keys) and any(k.startswith("model.diffusion_model.") for k in keys)):
        raise ValueError("完全なSDXLチェックポイントではありません")
    if not checkpoint and not any("lora" in k.lower() for k in keys):
        raise ValueError("LoRAの重みではありません")


def auth_headers(url, environ=None):
    env = os.environ if environ is None else environ
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise ValueError("モデルURLは認証情報を含まないHTTPSで指定してください")
    if parsed.hostname in {"civitai.com", "www.civitai.com"}:
        token = next((env[name] for name in ("CIVITAI_TOKEN", "CIVITAI_API_TOKEN", "CIVITAI_API_KEY") if env.get(name)), "")
    elif parsed.hostname in {"huggingface.co", "www.huggingface.co"}:
        token = env.get("HF_TOKEN", "")
    else:
        token = ""
    if "RUNPOD_SECRET_" in token:
        raise ValueError("RunPod Secretが展開されていません。環境変数への割り当てを確認してください")
    return {"Authorization": "Bearer " + token} if token else {}


def download(entry, destination, session=None):
    import requests

    destination = Path(destination)
    expected = entry["sha256"].lower()
    if not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise ValueError("SHA-256は64文字の16進数で指定してください")
    if destination.is_file():
        if sha256(destination) != expected:
            raise ValueError(f"既存ファイルのSHA-256が異なります: {destination.name}")
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    size = partial.stat().st_size if partial.exists() else 0
    headers = {"User-Agent": "Illustrious-Studio/1.0", **auth_headers(entry["url"])}
    if size:
        headers["Range"] = f"bytes={size}-"
    client = session or requests.Session()
    # requests removes Authorization on cross-host redirects, including CDN links.
    try:
        with client.get(entry["url"], headers=headers, stream=True, timeout=(30, 180)) as response:
            if response.status_code == 416 and partial.exists() and sha256(partial) == expected:
                partial.replace(destination)
                return destination
            if response.status_code in (401, 403):
                raise ValueError("モデル取得の認証に失敗しました。CIVITAI_TOKEN / HF_TOKENの割り当てを確認してください")
            if response.status_code not in (200, 206):
                raise ValueError(f"モデル取得に失敗しました（HTTP {response.status_code}）")
            append = response.status_code == 206 and size > 0
            if response.status_code == 206:
                content_range = response.headers.get("Content-Range", "")
                if not content_range.startswith(f"bytes {size}-"):
                    raise ValueError("再開位置が一致しません。部分ファイルを確認してください")
            received = size if append else 0
            next_progress = received + 256 * 1024 * 1024
            with partial.open("ab" if append else "wb") as stream:
                for chunk in response.iter_content(8 * 1024 * 1024):
                    if chunk:
                        stream.write(chunk)
                        received += len(chunk)
                        if received >= next_progress:
                            print(f"{destination.name}: {received // (1024 * 1024)} MiB", flush=True)
                            next_progress = received + 256 * 1024 * 1024
    except requests.RequestException:
        raise ValueError("モデルの通信が中断されました。同じ起動コマンドで再開できます") from None
    finally:
        if session is None:
            client.close()
    if sha256(partial) != expected:
        # Keep the bad download separately so a retry cannot append to it forever.
        failed = partial.with_name(partial.name + ".invalid-" + uuid.uuid4().hex[:8])
        partial.rename(failed)
        raise ValueError(f"ダウンロードしたファイルのSHA-256が異なります: {destination.name}")
    partial.replace(destination)
    return destination


def import_lora(source, destination, entry):
    source, destination = Path(source), Path(destination)
    if sha256(source) != entry["sha256"]:
        raise ValueError(f"LoRAのSHA-256が異なります: {source.name}")
    validate_header(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha256(destination) != entry["sha256"]:
            raise ValueError(f"異なる重みが配置されています: {destination.name}")
        return
    try:
        destination.symlink_to(source.resolve())
    except OSError:
        partial = destination.with_name(destination.name + ".part")
        shutil.copyfile(source, partial)
        if sha256(partial) != entry["sha256"]:
            raise ValueError("LoRAコピーの照合に失敗しました")
        partial.replace(destination)


def prepare(workspace, skip_download=False):
    workspace = Path(workspace)
    data = catalog()
    checkpoint = workspace / "models/checkpoints" / data["checkpoint"]["filename"]
    if skip_download and not checkpoint.exists():
        print("チェックポイントのダウンロードをスキップしました")
    else:
        download(data["checkpoint"], checkpoint)
        validate_header(checkpoint, checkpoint=True)
        print("チェックポイント SHA-256 / SDXL形式 OK", flush=True)
    for entry in data["characters"]:
        destination = workspace / "models/loras" / entry["filename"]
        candidates = [destination, workspace / "illustrious-loras" / entry["filename"]]
        candidates += sorted((workspace / "illustrious-nikke-lora/runs" / entry["id"]).glob(f"*/checkpoints/{entry['filename']}"), reverse=True)
        candidate = next((p for p in candidates if p.is_file()), None)
        if candidate:
            import_lora(candidate, destination, entry)
            print(f"LoRA OK: {entry['label']}", flush=True)
        else:
            print(f"未配置: {entry['label']} → {destination}", flush=True)
    extra = os.environ.get("ILLUSTRIOUS_LORA_MANIFEST")
    if extra:
        entries = json.loads(Path(extra).read_text(encoding="utf-8"))
        for entry in entries:
            name = entry["filename"]
            if Path(name).name != name or "/" in name or "\\" in name or not name.endswith(".safetensors"):
                raise ValueError("LoRA manifestのfilenameが不正です")
            target = workspace / "models/loras" / name
            download(entry, target)
            validate_header(target)
