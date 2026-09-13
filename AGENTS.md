# Illustrious Studio maintenance

- This repository is for image generation. Preserve the separate LoRA training environment and all original images, weights and outputs.
- Use the exact Nova Anime XL IL v19.0 checkpoint and verified LoRA hashes in `config/models.json` unless the user requests a change.
- Multiple characters must have separate masked LoRA hook groups on both CFG branches. Do not replace this with globally stacked LoRA loaders. Keep one shared image and sampler.
- These four LoRAs are UNet-only; CLIP strength stays zero. Character traits belong in editable per-character prompts; do not silently reinsert removed hair, eye or outfit tags.
- Read `docs/WORKFLOWS.md` before modifying graphs or runtime setup. Pin and test against real ComfyUI, not only mock graph schemas.
- Preserve the working CUDA stack with an isolated venv and constraints. Run real imports and a GPU calculation before model downloads on RunPod.
- RunPod Secrets map to CIVITAI_TOKEN and HF_TOKEN. Never print or commit values. Do not embed tokens in download URLs, Docker layers or generated workflows.
- Transfer LoRAs using runpodctl; the user prefers it to Jupyter GUI uploads. Never record temporary transfer codes.
- Do not commit weights, images, archives, real download logs or local absolute user paths. Put local test artifacts outside the tracked source tree.
- After functional edits, run unit tests, JS/shell syntax checks and applicable ComfyUI integration checks. Regenerate workflow exports if graph defaults change.
- Separate CPU/schema/UI checks, real GPU generation, and subjective image quality. Do not report the latter two as confirmed by the former.
