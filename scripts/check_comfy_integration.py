"""Validate exported graphs and actual masked hook aggregation without GPU weights."""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMFY = Path(os.environ["COMFYUI_PATH"]).resolve()
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(COMFY))
import comfy.cli_args
comfy.cli_args.args.cpu = True
import torch
import nodes
import folder_paths
import execution
from server import PromptServer
from illustrious.workflow import build_workflow, catalog


async def main():
    PromptServer(asyncio.get_running_loop())
    await nodes.init_extra_nodes(init_custom_nodes=False, init_api_nodes=False)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for kind in ("checkpoints", "loras"):
            (root / kind).mkdir()
            folder_paths.folder_names_and_paths[kind] = ([str(root / kind)], {".safetensors"})
        # Only file-name validation is exercised here; never queue these fixtures.
        (root / "checkpoints" / catalog()["checkpoint"]["filename"]).write_bytes(b"NOT A REAL MODEL")
        for char in catalog()["characters"]:
            (root / "loras" / char["filename"]).write_bytes(b"NOT A REAL LORA")
        for path in sorted((ROOT / "scenes").glob("*.json")):
            scene = json.loads(path.read_text(encoding="utf-8"))
            built = build_workflow(scene)
            result = await execution.validate_prompt("schema-check", built["prompt"], None)
            assert result[0], (path.name, result)
            print("ComfyUI validate_prompt PASS:", path.name)

    import comfy.samplers
    from comfy.hooks import HookGroup
    # Exercise the real sampler aggregation with a small deterministic model.
    # The model returns a distinct value for each hook group. Its masked output
    # must stay in the corresponding region, including both CFG branches.
    left_hook, right_hook = HookGroup(), HookGroup()
    class Patcher:
        selected = None
        def prepare_hook_patches_current_keyframe(self, *args): pass
        def prepare_state(self, *args): pass
        def get_free_memory(self, device): return 10**9
        def apply_hooks(self, hooks): self.selected = hooks; return {}
    class Model:
        current_patcher = Patcher()
        def memory_required(self, *args, **kwargs): return 1
        def apply_model(self, x, timestep, **kwargs):
            hook = self.current_patcher.selected
            return torch.full_like(x, 10 if hook is left_hook else 20 if hook is right_hook else 3)
    latent = torch.zeros(1, 4, 8, 12)
    left = torch.zeros(1, 8, 12); left[:, :, :4] = 1
    right = torch.zeros_like(left); right[:, :, 8:] = 1
    def cond(mask=None, hooks=None, default=False):
        result = {"model_conds": {}, "uuid": "test"}
        if mask is not None: result["mask"] = mask
        if hooks is not None: result["hooks"] = hooks
        if default: result["default"] = True
        return result
    conditions = [cond(left, left_hook), cond(right, right_hook), cond(default=True)]
    positive, negative = comfy.samplers.calc_cond_batch(Model(), [conditions, conditions], latent, torch.ones(1), {})
    for result in (positive, negative):
        assert torch.all(result[:, :, :, :4] == 10)
        assert torch.all(result[:, :, :, 4:8] == 3)
        assert torch.all(result[:, :, :, 8:] == 20)
    print("Real ComfyUI masked hooks / positive-negative branches / background aggregation PASS")


asyncio.run(main())
