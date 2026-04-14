"""Tests for download.py"""

import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from download import download_all, parse_url_file, safe_filename  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _SimpleHandler(BaseHTTPRequestHandler):
    """A minimal HTTP server that serves fixed responses for testing."""

    ROUTES: dict[str, bytes] = {}

    def log_message(self, *_):  # silence access log
        pass

    def do_GET(self):  # noqa: N802
        body = self.ROUTES.get(self.path)
        if body is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _start_server(routes: dict[str, bytes]) -> tuple[HTTPServer, str]:
    """Start a local HTTP server serving *routes*, return (server, base_url)."""
    _SimpleHandler.ROUTES = routes
    server = HTTPServer(("127.0.0.1", 0), _SimpleHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}"


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestSafeFilename(unittest.TestCase):
    def test_normal_path(self):
        self.assertEqual(safe_filename("http://example.com/foo/bar.zip", 1), "bar.zip")

    def test_no_path(self):
        self.assertEqual(safe_filename("http://example.com/", 5), "file_5")

    def test_root_only(self):
        self.assertEqual(safe_filename("http://example.com", 3), "file_3")

    def test_query_stripped(self):
        name = safe_filename("http://example.com/file.txt?token=abc", 1)
        self.assertEqual(name, "file.txt")


class TestParseUrlFile(unittest.TestCase):
    def _write(self, tmp_path: Path, content: str) -> Path:
        p = tmp_path / "urls.txt"
        p.write_text(content, encoding="utf-8")
        return str(p)

    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_basic(self):
        path = self._write(self._tmp, "http://a.com/1.txt\nhttp://b.com/2.txt\n")
        self.assertEqual(parse_url_file(path), ["http://a.com/1.txt", "http://b.com/2.txt"])

    def test_skips_blank_and_comments(self):
        content = "\n# this is a comment\nhttp://x.com/f.zip\n\n"
        path = self._write(self._tmp, content)
        self.assertEqual(parse_url_file(path), ["http://x.com/f.zip"])

    def test_empty_file(self):
        path = self._write(self._tmp, "")
        self.assertEqual(parse_url_file(path), [])


class TestDownloadAll(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.TemporaryDirectory()
        self._out = Path(self._tmpdir.name) / "out"

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_successful_download(self):
        server, base = _start_server({"/hello.txt": b"hello world"})
        try:
            download_all([f"{base}/hello.txt"], self._out, workers=1, timeout=5)
            self.assertTrue((self._out / "hello.txt").exists())
            self.assertEqual((self._out / "hello.txt").read_bytes(), b"hello world")
        finally:
            server.shutdown()

    def test_collision_avoidance(self):
        """Two different URLs that resolve to the same filename must not collide."""
        server, base = _start_server({
            "/a/file.txt": b"first",
            "/b/file.txt": b"second",
        })
        try:
            download_all(
                [f"{base}/a/file.txt", f"{base}/b/file.txt"],
                self._out,
                workers=1,
                timeout=5,
            )
            files = list(self._out.iterdir())
            self.assertEqual(len(files), 2)
        finally:
            server.shutdown()

    def test_failed_download_exits_nonzero(self):
        server, base = _start_server({})  # 404 for everything
        try:
            with self.assertRaises(SystemExit) as cm:
                download_all([f"{base}/missing.txt"], self._out, workers=1, timeout=5)
            self.assertEqual(cm.exception.code, 1)
        finally:
            server.shutdown()

    def test_creates_output_dir(self):
        server, base = _start_server({"/x.bin": b"\x00\x01"})
        nested = self._out / "a" / "b" / "c"
        try:
            download_all([f"{base}/x.bin"], nested, workers=1, timeout=5)
            self.assertTrue(nested.is_dir())
        finally:
            server.shutdown()


class TestCLI(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.TemporaryDirectory()
        self._tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_missing_url_file(self):
        from download import main
        with self.assertRaises(SystemExit):
            main(["nonexistent_file.txt"])

    def test_empty_url_file(self):
        from download import main
        url_file = self._tmp / "empty.txt"
        url_file.write_text("# just a comment\n", encoding="utf-8")
        # Should print "nothing to do" and return without error
        main([str(url_file)])

    def test_end_to_end(self):
        from download import main
        server, base = _start_server({"/data.bin": b"data"})
        url_file = self._tmp / "urls.txt"
        url_file.write_text(f"{base}/data.bin\n", encoding="utf-8")
        out_dir = str(self._tmp / "output")
        try:
            main([str(url_file), "-o", out_dir, "-w", "2", "-t", "5"])
            self.assertTrue((Path(out_dir) / "data.bin").exists())
        finally:
            server.shutdown()


if __name__ == "__main__":
    unittest.main()
