FROM pytorch/pytorch:2.11.0-cuda13.0-cudnn9-runtime@sha256:bfbb4a2b4fdba0fefdb428ea737e626d61bb3daf74a16e1ff935bdb03aa7c3f0
LABEL org.opencontainers.image.source="https://github.com/grawthings-beep/illustrious" \
    org.opencontainers.image.title="Illustrious Studio"
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    ILLUSTRIOUS_WORKSPACE=/workspace ILLUSTRIOUS_COMFY_DIR=/opt/ComfyUI \
    ILLUSTRIOUS_VENV=/opt/illustrious-venv PYTHONPATH=/opt/illustrious
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates libgl1 libglib2.0-0 util-linux python3-venv && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/illustrious
COPY . .
RUN python scripts/bootstrap.py --install-only
RUN /opt/illustrious-venv/bin/python scripts/check_runtime.py --comfy-dir /opt/ComfyUI --cpu
RUN python -c "from urllib.request import urlopen; from pathlib import Path; import hashlib; data=urlopen('https://github.com/runpod/runpodctl/releases/download/v2.3.0/runpodctl-linux-amd64', timeout=120).read(); assert hashlib.sha256(data).hexdigest() == 'fdac0b7a0ac4d4b5b9ef1203f9229c99313e212ac8689701a29e4ba05fae32b8', 'runpodctl checksum mismatch'; p=Path('/usr/local/bin/runpodctl'); p.write_bytes(data); p.chmod(0o755)" \
    && runpodctl --version
EXPOSE 8188
VOLUME ["/workspace"]
ENTRYPOINT ["bash", "/opt/illustrious/scripts/start.sh"]
