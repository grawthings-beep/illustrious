import unittest
from illustrious.workflow import build_workflow, catalog, validate_scene


def scene(count=2):
    return {"characters": [{"id": item["id"]} for item in catalog()["characters"][:count]]}


class WorkflowTests(unittest.TestCase):
    def test_one_shared_sampler_and_separate_masked_hooks(self):
        for count in (1, 2, 3, 4):
            graph = build_workflow(scene(count))["prompt"]
            nodes = list(graph.values())
            self.assertEqual(sum(n["class_type"] == "KSampler" for n in nodes), 1)
            self.assertEqual(sum(n["class_type"] == "CreateHookLora" for n in nodes), count)
            self.assertFalse(any(n["class_type"] == "LoraLoader" for n in nodes))
            hooks = set()
            masks = set()
            for node in nodes:
                if node["class_type"] == "PairConditioningSetProperties":
                    inputs = node["inputs"]
                    hooks.add(inputs["hooks"][0]); masks.add(inputs["mask"][0])
                    hook = graph[inputs["hooks"][0]]["inputs"]
                    self.assertEqual(hook["strength_clip"], 0)
                    self.assertNotIn("prev_hooks", hook)
                    self.assertIn("positive_NEW", inputs); self.assertIn("negative_NEW", inputs)
            self.assertEqual(len(hooks), count); self.assertEqual(len(masks), count)
            self.assertEqual(sum(n["class_type"] == "PairConditioningSetDefaultCombine" for n in nodes), 1)

    def test_colors_and_clothes_are_not_hardcoded_overrides(self):
        request = scene()
        request["characters"][0]["prompt"] = "blue hair, green eyes, red dress"
        request["characters"][1]["prompt"] = "black hair, yellow eyes, white jacket"
        graph = build_workflow(request)["prompt"]
        texts = [n["inputs"]["text"] for n in graph.values() if n["class_type"] == "CLIPTextEncode"]
        first = next(t for t in texts if "sw1melegg" in t)
        second = next(t for t in texts if "sw1mrapi" in t)
        self.assertIn("blue hair", first); self.assertNotIn("blonde hair", first)
        self.assertNotIn("yellow bikini", first); self.assertNotIn("black hair", first)
        self.assertIn("black hair", second); self.assertNotIn("blue hair", second)

    def test_seed_and_ui_links_roundtrip(self):
        request = scene(3); request["seed"] = 123456
        built = build_workflow(request)
        for link_id, source, slot, target, input_slot, data_type in built["workflow"]["links"]:
            source_node = built["workflow"]["nodes"][source - 1]
            target_node = built["workflow"]["nodes"][target - 1]
            self.assertEqual(source_node["outputs"][slot]["type"], data_type)
            self.assertEqual(target_node["inputs"][input_slot]["link"], link_id)
            name = target_node["inputs"][input_slot]["name"]
            self.assertEqual(built["prompt"][str(target)]["inputs"][name], [str(source), slot])
        self.assertEqual(build_workflow(built["workflow"]["extra"]["illustrious_scene"])["prompt"], built["prompt"])

    def test_invalid_geometry_and_nonfinite_values_rejected(self):
        for bad in (float("nan"), float("inf"), -1, 1.1):
            request = scene(); request["characters"][0]["region"] = [bad, 0, 0.5, 1]
            with self.assertRaises(ValueError): validate_scene(request)
        for width in (True, 1001, 64, 4096):
            request = scene(); request["width"] = width
            with self.assertRaises(ValueError): validate_scene(request)
        request = scene(); request["characters"][0]["region"] = [0.8,0,0.5,1]
        with self.assertRaises(ValueError): validate_scene(request)

    def test_unknown_char_and_oversized_prompt_rejected(self):
        request = scene(); request["characters"][0]["id"] = "../../secret"
        with self.assertRaises(ValueError): validate_scene(request)
        request = scene(); request["prompt"] = "x" * 5001
        with self.assertRaises(ValueError): validate_scene(request)


if __name__ == "__main__": unittest.main()
