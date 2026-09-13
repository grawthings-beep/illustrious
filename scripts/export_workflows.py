import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from illustrious.workflow import build_workflow, catalog


def main():
    characters = catalog()["characters"]
    for count, name in ((1, "01-single"), (2, "02-two-characters"), (3, "03-three-characters"), (4, "04-four-characters")):
        scene = {
            "width": 1024 if count == 1 else (1344 if count == 2 else 1536),
            "height": 1024 if count == 1 or count >= 3 else 896,
            "seed": 42, "steps": 28, "cfg": 5.5, "feather": 24,
            "prompt": "beach, ocean, blue sky, daylight, standing, looking at viewer",
            "characters": [{"id": item["id"], "prompt": item["prompt"], "strength": 0.8, "region": [i / count + 0.02, 0.02, 1 / count - 0.04, 0.96]} for i, item in enumerate(characters[:count])],
        }
        built = build_workflow(scene)
        for path, content in ((ROOT / f"scenes/{name}.json", built["scene"]), (ROOT / f"workflows/{name}.json", built["workflow"]), (ROOT / f"workflows/api/{name}.json", built["prompt"])):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Exported {name}: {len(built['prompt'])} native nodes")


if __name__ == "__main__":
    main()
