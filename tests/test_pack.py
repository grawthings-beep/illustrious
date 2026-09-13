import hashlib
import json
import struct
import tarfile
import tempfile
import unittest
from pathlib import Path

from scripts.pack_loras import pack


class PackTests(unittest.TestCase):
    def test_verified_weight_only_and_existing_archive_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            header = json.dumps({"lora_unet_test.lora_down.weight": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]}}).encode()
            payload = struct.pack("<Q", len(header)) + header + struct.pack("<f", 1.0)
            (root / "model.safetensors").write_bytes(payload)
            (root / "sample.png").write_bytes(b"unrelated image")
            entry = {"filename": "model.safetensors", "sha256": hashlib.sha256(payload).hexdigest()}
            destination = root / "pack.tar.gz"
            pack([root], destination, [entry])
            with tarfile.open(destination) as archive:
                self.assertEqual(archive.getnames(), ["illustrious-loras/model.safetensors"])
                self.assertEqual(archive.extractfile(archive.getnames()[0]).read(), payload)
            saved = destination.read_bytes()
            with self.assertRaises(ValueError): pack([root], destination, [entry])
            self.assertEqual(destination.read_bytes(), saved)
            self.assertEqual((root / "model.safetensors").read_bytes(), payload)
            entry["sha256"] = "0" * 64
            with self.assertRaises(ValueError): pack([root], root / "bad.tar.gz", [entry])
            self.assertFalse((root / "bad.tar.gz").exists())


if __name__ == "__main__": unittest.main()
