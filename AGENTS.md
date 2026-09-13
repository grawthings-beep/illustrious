# Illustrious Studio maintenance

- This repository is for image generation. Preserve the separate LoRA training environment and all original images, weights and outputs.
- Use the exact Nova Anime XL IL v19.0 checkpoint and verified LoRA hashes in `config/models.json` unless the user requests a change.
- Multiple characters must have separate masked LoRA hook groups on both CFG branches. Do not replace this with globally stacked LoRA loaders. Keep one shared image and sampler.
- These four LoRAs are UNet-only; CLIP strength stays zero. Character traits belong in editable per-character prompts; do not silently reinsert removed hair, eye or outfit tags.
- Read `docs/WORKFLOWS.md` before modifying graphs or runtime setup. Pin and test against real ComfyUI, not only mock graph schemas.
- Preserve the working CUDA stack with an isolated venv and constraints. Run real imports and a GPU calculation before model downloads on RunPod.
- On 2026-09-13 the initial CUDA 13 image failed on a new Pod whose driver exposed CUDA API 12.4 (12040). Do not infer new host compatibility from the previous Blackwell training Pod. The generation image and fresh-install fallback now use PyTorch 2.11.0 / CUDA 12.8. Publish the cuda12 tag as well as latest; never recommend the original CUDA 13 digest for this host. CUDA 12 minor compatibility permits a 12.4 driver, subject to GPU/kernel support. Keep the major-family regression tests and real matmul/backward, convolution and attention startup checks. CPU builds cannot confirm live GPU compatibility.
- The pinned PyTorch Docker base requires Ubuntu's `python3-venv` package; the first image build failed without ensurepip. Keep this OS dependency and the CPU ComfyUI import check in the Docker build. Keep the verified runpodctl binary for this user's transfer workflow.
- RunPod Secrets map to CIVITAI_TOKEN and HF_TOKEN. Never print or commit values. Do not embed tokens in download URLs, Docker layers or generated workflows.
- The user starts this app from its repo/container, like Anima. The Docker ENTRYPOINT starts Studio automatically. Explain this path first; do not present terminal clone/start commands as required after deploying this container. Manual installation into an existing unrelated Pod is an optional alternative. Distinguish configured automatic startup from a verified Docker build or live Pod launch.
- Transfer LoRAs using runpodctl; the user prefers it to Jupyter GUI uploads. Never record temporary transfer codes.
- Do not commit weights, images, archives, real download logs or local absolute user paths. Put local test artifacts outside the tracked source tree.
- After functional edits, run unit tests, JS/shell syntax checks and applicable ComfyUI integration checks. Regenerate workflow exports if graph defaults change.
- Separate CPU/schema/UI checks, real GPU generation, and subjective image quality. Do not report the latter two as confirmed by the former.
