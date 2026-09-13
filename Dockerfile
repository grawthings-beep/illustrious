FROM pytorch/pytorch:2.11.0-cuda13.0-cudnn9-runtime@sha256:bfbb4a2b4fdba0fefdb428ea737e626d61bb3daf74a16e1ff935bdb03aa7c3f0
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 \
    ILLUSTRIOUS_WORKSPACE=/workspace ILLUSTRIOUS_COMFY_DIR=/opt/ComfyUI \
    ILLUSTRIOUS_VENV=/opt/illustrious-venv PYTHONPATH=/opt/illustrious
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates libgl1 libglib2.0-0 util-linux && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/illustrious
COPY . .
RUN python scripts/bootstrap.py --install-only
EXPOSE 8188
VOLUME ["/workspace"]
ENTRYPOINT ["bash", "/opt/illustrious/scripts/start.sh"]
