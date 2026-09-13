"""Check real ComfyUI node imports and GPU computation before a large download."""
import argparse
import asyncio
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--comfy-dir", type=Path, required=True)
parser.add_argument("--cpu", action="store_true")
args = parser.parse_args()
sys.path.insert(0, str(args.comfy_dir.resolve()))
import comfy.cli_args
comfy.cli_args.args.cpu = args.cpu
import torch

if not args.cpu:
    if not torch.cuda.is_available():
        raise SystemExit("CUDAが利用できません。GPU付きPodとPyTorchを確認してください")
    x = torch.randn(32, 32, device="cuda", dtype=torch.bfloat16, requires_grad=True)
    (x @ x).float().mean().backward()
    torch.cuda.synchronize()
    print("GPU calculation OK:", torch.cuda.get_device_name(0), flush=True)
from transformers import CLIPTextConfig, CLIPTextModel
clip = CLIPTextModel(CLIPTextConfig(vocab_size=16, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, max_position_embeddings=16))
assert "text_model.embeddings.token_embedding.weight" in clip.state_dict()
import nodes
async def initialize():
    from server import PromptServer
    PromptServer(asyncio.get_running_loop())
    await nodes.init_extra_nodes(init_custom_nodes=False, init_api_nodes=False)
asyncio.run(initialize())
required = ("CreateHookLora", "PairConditioningSetProperties", "PairConditioningCombine", "PairConditioningSetDefaultCombine", "SolidMask", "FeatherMask", "MaskComposite", "KSampler")
missing = [name for name in required if name not in nodes.NODE_CLASS_MAPPINGS]
if missing:
    raise SystemExit("ComfyUI required nodes missing: " + ", ".join(missing))
print("ComfyUI native regional LoRA nodes / CLIP imports OK", flush=True)
