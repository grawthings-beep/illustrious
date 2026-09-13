"""Build native ComfyUI graphs with separate masked LoRA hooks per character."""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_NAME = "novaAnimeXL_ilV190.safetensors"
DEFAULT_NEGATIVE = "worst quality, low quality, lowres, bad anatomy, bad hands, extra fingers, missing fingers, extra limbs, text, watermark, signature"


def catalog():
    return json.loads((ROOT / "config/models.json").read_text(encoding="utf-8"))


def number(value, name, low, high, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name}: 数値を指定してください")
    if value < low or value > high or (integer and value != int(value)):
        raise ValueError(f"{name}: {low}〜{high}の範囲で指定してください")
    return int(value) if integer else float(value)


def prompt_text(value, name):
    if not isinstance(value, str) or len(value) > 5000:
        raise ValueError(f"{name}: 5000文字以内のテキストを指定してください")
    return value.strip()


def validate_scene(scene):
    scene = copy.deepcopy(scene)
    if not isinstance(scene, dict):
        raise ValueError("シーンはJSONオブジェクトで指定してください")
    chars = scene.get("characters")
    if not isinstance(chars, list) or not 1 <= len(chars) <= 4:
        raise ValueError("キャラ数は1〜4人です")
    for dimension in ("width", "height"):
        scene[dimension] = number(scene.get(dimension, 1024), dimension, 512, 2048, True)
        if scene[dimension] % 8:
            raise ValueError(f"{dimension}は8の倍数にしてください")
    if scene["width"] * scene["height"] > 2048 * 1536:
        raise ValueError("画像サイズは合計3,145,728画素以下にしてください")
    scene["seed"] = number(scene.get("seed", 42), "seed", 0, 2**53 - 1, True)
    scene["steps"] = number(scene.get("steps", 28), "steps", 1, 80, True)
    scene["cfg"] = number(scene.get("cfg", 5.5), "CFG", 1, 15)
    scene["feather"] = number(scene.get("feather", 24), "境界ぼかし", 0, 128, True)
    scene["prompt"] = prompt_text(scene.get("prompt", "beach, ocean, blue sky, daylight, standing"), "全体プロンプト")
    scene["negative"] = prompt_text(scene.get("negative", DEFAULT_NEGATIVE), "ネガティブ")
    known = {item["id"]: item for item in catalog()["characters"]}
    for index, char in enumerate(chars):
        if not isinstance(char, dict) or char.get("id") not in known:
            raise ValueError(f"キャラ{index + 1}: カタログから選んでください")
        char["strength"] = number(char.get("strength", 0.8), "LoRA強度", 0, 1.5)
        char["prompt"] = prompt_text(char.get("prompt", known[char["id"]]["prompt"]), "キャラプロンプト")
        char["negative"] = prompt_text(char.get("negative", ""), "キャラのネガティブ")
        region = char.get("region", [index / len(chars), 0, 1 / len(chars), 1])
        if not isinstance(region, list) or len(region) != 4:
            raise ValueError("領域は[x, y, 幅, 高さ]の配列です")
        x, y, w, h = [number(v, "領域", 0, 1) for v in region]
        if w < 0.08 or h < 0.08 or x + w > 1.000001 or y + h > 1.000001:
            raise ValueError("各領域は画像内に収め、幅・高さは8%以上にしてください")
        char["region"] = [x, y, w, h]
    return scene


class Graph:
    def __init__(self):
        self.api = {}
        self.nodes = []
        self.links = []
        self.groups = []

    def add(self, node_type, inputs, title, pos, outputs, widgets=(), types=None, size=None):
        node_id = len(self.nodes) + 1
        key = str(node_id)
        self.api[key] = {"class_type": node_type, "inputs": inputs, "_meta": {"title": title}}
        node = {"id": node_id, "type": node_type, "pos": list(pos), "size": size or [300, 160],
                "flags": {}, "order": node_id - 1, "mode": 0, "title": title,
                "inputs": [], "outputs": [{"name": t, "type": t, "links": []} for t in outputs],
                "properties": {"Node name for S&R": node_type}, "widgets_values": list(widgets)}
        for name, value in inputs.items():
            if not isinstance(value, list):
                continue
            source_id, slot = value
            source = self.nodes[int(source_id) - 1]
            data_type = source["outputs"][slot]["type"]
            if types and name in types and types[name] != data_type:
                raise ValueError(f"Node link type mismatch: {name}")
            link_id = len(self.links) + 1
            self.links.append([link_id, int(source_id), slot, node_id, len(node["inputs"]), data_type])
            source["outputs"][slot]["links"].append(link_id)
            node["inputs"].append({"name": name, "type": data_type, "link": link_id})
        self.nodes.append(node)
        return key

    def ui(self, scene):
        return {"last_node_id": len(self.nodes), "last_link_id": len(self.links), "nodes": self.nodes,
                "links": self.links, "groups": self.groups, "config": {},
                "extra": {"ds": {"scale": 0.5, "offset": [80, 80]}, "illustrious_scene": scene}, "version": 0.4}


def build_workflow(scene):
    scene = validate_scene(scene)
    chars = {item["id"]: item for item in catalog()["characters"]}
    g = Graph()
    width, height = scene["width"], scene["height"]
    base = g.add("CheckpointLoaderSimple", {"ckpt_name": MODEL_NAME}, "学習と同じ Nova Anime XL IL v19.0", (0, 0), ["MODEL", "CLIP", "VAE"], [MODEL_NAME])
    common = ", ".join(filter(None, ["masterpiece, best quality, very aesthetic", scene["prompt"]]))
    global_pos = g.add("CLIPTextEncode", {"clip": [base, 1], "text": common}, "共通の背景・画風（空いた領域）", (0, 230), ["CONDITIONING"], [common], size=[330, 190])
    global_neg = g.add("CLIPTextEncode", {"clip": [base, 1], "text": scene["negative"]}, "共通ネガティブ", (0, 470), ["CONDITIONING"], [scene["negative"]], size=[330, 190])
    empty = g.add("SolidMask", {"value": 0.0, "width": width, "height": height}, "領域の土台", (0, 720), ["MASK"], [0, width, height])
    combined = None
    for index, character in enumerate(scene["characters"]):
        preset = chars[character["id"]]
        y_pos = index * 900
        label = f"{index + 1}: {preset['label']}"
        text = ", ".join(filter(None, [common, "1girl", preset["trigger"], character["prompt"]]))
        negative = ", ".join(filter(None, [scene["negative"], character["negative"]]))
        positive_node = g.add("CLIPTextEncode", {"clip": [base, 1], "text": text}, label + " / 髪・目・衣装・ポーズ", (400, y_pos), ["CONDITIONING"], [text], size=[350, 240])
        negative_node = g.add("CLIPTextEncode", {"clip": [base, 1], "text": negative}, label + " / ネガティブ", (400, y_pos + 290), ["CONDITIONING"], [negative], size=[350, 190])
        # Each character has its OWN hook group. Never chain these LoRAs globally.
        hook = g.add("CreateHookLora", {"lora_name": preset["filename"], "strength_model": character["strength"], "strength_clip": 0.0}, label + " / 専用LoRA", (800, y_pos), ["HOOKS"], [preset["filename"], character["strength"], 0.0])
        x, y, w, h = character["region"]
        left, top = round(x * width), round(y * height)
        rw, rh = min(width - left, max(1, round(w * width))), min(height - top, max(1, round(h * height)))
        solid = g.add("SolidMask", {"value": 1.0, "width": rw, "height": rh}, label + " / 領域サイズ", (400, y_pos + 540), ["MASK"], [1, rw, rh])
        feather = min(scene["feather"], rw // 2, rh // 2)
        smooth = g.add("FeatherMask", {"mask": [solid, 0], "left": feather, "top": feather, "right": feather, "bottom": feather}, label + " / 境界", (800, y_pos + 250), ["MASK"], [feather] * 4)
        mask = g.add("MaskComposite", {"destination": [empty, 0], "source": [smooth, 0], "x": left, "y": top, "operation": "add"}, label + " / 位置", (800, y_pos + 510), ["MASK"], [left, top, "add"])
        pair = g.add("PairConditioningSetProperties", {"positive_NEW": [positive_node, 0], "negative_NEW": [negative_node, 0], "strength": 1.0, "set_cond_area": "default", "mask": [mask, 0], "hooks": [hook, 0]}, label + " / この領域だけに適用", (1190, y_pos), ["CONDITIONING", "CONDITIONING"], [1.0, "default"])
        if combined is None:
            combined = pair
        else:
            combined = g.add("PairConditioningCombine", {"positive_A": [combined, 0], "negative_A": [combined, 1], "positive_B": [pair, 0], "negative_B": [pair, 1]}, "キャラの領域を統合", (1560, y_pos), ["CONDITIONING", "CONDITIONING"])
        g.groups.append({"title": label, "bounding": [370, y_pos - 40, 1160, 860], "color": ["#476c9b", "#a85f70", "#8b783c", "#548976"][index], "font_size": 24, "flags": {}})
    bg = g.add("PairConditioningSetDefaultCombine", {"positive": [combined, 0], "negative": [combined, 1], "positive_DEFAULT": [global_pos, 0], "negative_DEFAULT": [global_neg, 0]}, "キャラ以外の領域を共通背景で補完", (1940, 0), ["CONDITIONING", "CONDITIONING"])
    latent = g.add("EmptyLatentImage", {"width": width, "height": height, "batch_size": 1}, "1枚の画像を同時生成", (1940, 240), ["LATENT"], [width, height, 1])
    sampler = g.add("KSampler", {"model": [base, 0], "positive": [bg, 0], "negative": [bg, 1], "latent_image": [latent, 0], "seed": scene["seed"], "steps": scene["steps"], "cfg": scene["cfg"], "sampler_name": "dpmpp_2m_sde", "scheduler": "karras", "denoise": 1.0}, "複数キャラを同じ画像で生成", (2320, 0), ["LATENT"], [scene["seed"], "fixed", scene["steps"], scene["cfg"], "dpmpp_2m_sde", "karras", 1.0], size=[330, 320])
    decode = g.add("VAEDecode", {"samples": [sampler, 0], "vae": [base, 2]}, "画像に変換", (2700, 0), ["IMAGE"])
    g.add("SaveImage", {"images": [decode, 0], "filename_prefix": f"illustrious/{len(scene['characters'])}characters"}, "保存（PNGにワークフローも記録）", (3050, 0), [], [f"illustrious/{len(scene['characters'])}characters"], size=[390, 450])
    return {"prompt": g.api, "workflow": g.ui(scene), "scene": scene}
