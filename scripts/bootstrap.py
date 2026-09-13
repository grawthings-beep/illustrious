"""Install into an isolated venv, preserve CUDA torch, prepare models, start ComfyUI."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def command(args, **kwargs):
    subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def install(workspace, comfy):
    lock = json.loads((ROOT / "comfy.lock.json").read_text())
    if not comfy.exists():
        comfy.mkdir(parents=True)
        command(["git", "init", comfy])
        command(["git", "-C", comfy, "remote", "add", "origin", lock["repository"]])
        command(["git", "-C", comfy, "fetch", "--depth", "1", "origin", lock["commit"]])
        command(["git", "-C", comfy, "checkout", "--detach", "FETCH_HEAD"])
    commit = subprocess.check_output(["git", "-C", str(comfy), "rev-parse", "HEAD"], text=True).strip()
    if commit != lock["commit"]:
        raise ValueError("ComfyUIのcommitが一致しません。ILLUSTRIOUS_COMFY_DIRに専用の新しいディレクトリを指定してください")
    venv = Path(os.environ.get("ILLUSTRIOUS_VENV", workspace / "illustrious-runtime/venv"))
    python = venv / "bin/python"
    if not python.exists():
        command([sys.executable, "-m", "venv", "--system-site-packages", venv])
    fingerprint = hashlib.sha256((ROOT / "requirements.txt").read_bytes() + (comfy / "requirements.txt").read_bytes() + commit.encode()).hexdigest()
    marker = venv / "illustrious-install.json"
    if not marker.exists() or json.loads(marker.read_text()).get("fingerprint") != fingerprint:
        # Freeze only the inherited GPU/numerical stack; no training venv writes.
        freeze_script = 'import importlib.metadata as m; names={d.metadata["Name"].lower().replace("_","-") for d in m.distributions()}; print("\\n".join(n+"=="+m.version(n) for n in ("torch","torchvision","torchaudio","numpy","triton","xformers") if n in names))'
        protected = subprocess.check_output([str(python), "-c", freeze_script], text=True)
        constraints = venv / "cuda-constraints.txt"
        constraints.write_text(protected, encoding="utf-8")
        if not any(line.startswith("torch==") for line in protected.splitlines()):
            command([python, "-m", "pip", "install", "torch==2.11.0", "torchvision==0.26.0", "torchaudio==2.11.0", "--index-url", "https://download.pytorch.org/whl/cu128"])
            protected = subprocess.check_output([str(python), "-c", freeze_script], text=True)
            constraints.write_text(protected, encoding="utf-8")
        command([python, "-m", "pip", "install", "-c", constraints, "-r", comfy / "requirements.txt", "-r", ROOT / "requirements.txt"])
        after = subprocess.check_output([str(python), "-c", freeze_script], text=True)
        if not set(protected.splitlines()).issubset(after.splitlines()):
            raise ValueError("GPUスタックが変化したため起動を停止しました")
        marker.write_text(json.dumps({"fingerprint": fingerprint, "comfy_commit": commit}), encoding="utf-8")
    return python


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-only", action="store_true")
    parser.add_argument("--cpu", action="store_true", help="CPU validation only; not recommended for image generation")
    args = parser.parse_args()
    workspace = Path(os.environ.get("ILLUSTRIOUS_WORKSPACE", "/workspace")).resolve()
    port = int(os.environ.get("ILLUSTRIOUS_PORT", "8188"))
    listen = os.environ.get("ILLUSTRIOUS_LISTEN", "0.0.0.0")
    if not 1 <= port <= 65535:
        raise ValueError("ILLUSTRIOUS_PORTが不正です")
    if not args.install_only:
        try:
            with socket.socket(socket.AF_INET6 if ":" in listen else socket.AF_INET) as probe:
                probe.bind((listen, port))
        except OSError:
            raise ValueError(f"port {port}を使用できません。既存のComfyUIを停止するか、ILLUSTRIOUS_PORT=8189など別のポートを指定しRunPodのHTTP公開ポートにも追加してください") from None
    commit = json.loads((ROOT / "comfy.lock.json").read_text())["commit"]
    comfy = Path(os.environ.get("ILLUSTRIOUS_COMFY_DIR", workspace / f"illustrious-runtime/ComfyUI-{commit[:12]}"))
    python = install(workspace, comfy)
    if args.install_only:
        return
    command([python, ROOT / "scripts/check_runtime.py", "--comfy-dir", comfy] + (["--cpu"] if args.cpu else []))
    command([python, ROOT / "scripts/prepare_models.py"])
    data = workspace / "illustrious-data"
    for directory in ("input", "output", "user/default/workflows", "custom_nodes", "temp"):
        (data / directory).mkdir(parents=True, exist_ok=True)
    for directory in ("checkpoints", "loras"):
        (workspace / "models" / directory).mkdir(parents=True, exist_ok=True)
    extension = data / "custom_nodes/illustrious_studio"
    target = ROOT / "custom_nodes/illustrious_studio"
    if not extension.exists():
        extension.symlink_to(target, target_is_directory=True)
    elif extension.resolve() != target.resolve():
        raise ValueError("別のStudio拡張が配置されています。ILLUSTRIOUS_WORKSPACEを確認してください")
    for source in (ROOT / "workflows").glob("*.json"):
        destination = data / "user/default/workflows" / source.name
        if not destination.exists():
            shutil.copyfile(source, destination)
    print(f"Illustrious Studio: port {port} /illustrious/", flush=True)
    print(f"Images: {data / 'output/illustrious'}", flush=True)
    launch = [str(python), str(comfy / "main.py"), "--listen", listen, "--port", str(port),
              "--base-directory", str(data), "--models-directory", str(workspace / "models"),
              "--user-directory", str(data / "user"), "--fp32-vae", "--preview-method", "latent2rgb",
              "--disable-api-nodes", "--disable-all-custom-nodes", "--whitelist-custom-nodes", "illustrious_studio"]
    if args.cpu:
        launch.append("--cpu")
    os.chdir(comfy)
    os.execv(str(python), launch)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f"起動を停止しました: {exc}", file=sys.stderr)
        raise SystemExit(1)
