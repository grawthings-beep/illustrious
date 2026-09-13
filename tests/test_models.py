import hashlib
import tempfile
import unittest
from pathlib import Path
from illustrious.models import auth_headers, download


class Response:
    def __init__(self, payload, status=200, headers=None):
        self.payload, self.status_code, self.headers = payload, status, headers or {}
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def iter_content(self, size): yield self.payload


class Session:
    def __init__(self, response): self.response = response; self.calls = []
    def get(self, url, **kwargs): self.calls.append((url,kwargs)); return self.response


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name) / "model.safetensors"
        self.payload = b"fixture model bytes"
        self.entry = {"url":"https://civitai.com/api/download/models/2940478?fileId=2819621", "sha256":hashlib.sha256(self.payload).hexdigest()}

    def test_secret_host_scoping(self):
        env = {"CIVITAI_TOKEN":"fixture-civitai", "HF_TOKEN":"fixture-hf"}
        self.assertEqual(auth_headers(self.entry["url"], env), {"Authorization":"Bearer fixture-civitai"})
        self.assertEqual(auth_headers("https://huggingface.co/owner/repo/resolve/main/model", env), {"Authorization":"Bearer fixture-hf"})
        self.assertEqual(auth_headers("https://cdn.example.org/model", env), {})
        with self.assertRaises(ValueError): auth_headers("http://civitai.com/model", env)
        with self.assertRaises(ValueError): auth_headers(self.entry["url"], {"CIVITAI_TOKEN":"{{ RUNPOD_SECRET_CIVITAI_TOKEN }}"})

    def test_success_and_existing_reuse(self):
        session = Session(Response(self.payload))
        download(self.entry, self.target, session)
        self.assertEqual(self.target.read_bytes(), self.payload)
        download(self.entry, self.target, session)
        self.assertEqual(len(session.calls), 1)

    def test_ignored_range_restarts_instead_of_appending(self):
        self.target.with_suffix(".safetensors.part").write_bytes(b"partial")
        session = Session(Response(self.payload, 200))
        download(self.entry, self.target, session)
        self.assertEqual(self.target.read_bytes(), self.payload)
        self.assertEqual(session.calls[0][1]["headers"]["Range"], "bytes=7-")

    def test_valid_resume(self):
        self.target.with_suffix(".safetensors.part").write_bytes(self.payload[:7])
        session = Session(Response(self.payload[7:], 206, {"Content-Range":f"bytes 7-{len(self.payload)-1}/{len(self.payload)}"}))
        download(self.entry, self.target, session)
        self.assertEqual(self.target.read_bytes(), self.payload)

    def test_checksum_failure_does_not_replace_existing_output(self):
        with self.assertRaises(ValueError): download(self.entry, self.target, Session(Response(b"wrong")))
        self.assertFalse(self.target.exists())
        self.target.write_bytes(b"keep existing")
        with self.assertRaises(ValueError): download(self.entry, self.target, Session(Response(self.payload)))
        self.assertEqual(self.target.read_bytes(), b"keep existing")

    def test_auth_error_is_sanitized(self):
        with self.assertRaises(ValueError) as result: download(self.entry, self.target, Session(Response(b"private body", 403)))
        self.assertNotIn("private body", str(result.exception))


if __name__ == "__main__": unittest.main()
