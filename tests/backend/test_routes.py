"""Detect a static mount shadowing one of the feature routes after composition."""

from pathlib import Path
import tempfile
import unittest

from backend.server import create_app


class ApplicationRoutes(unittest.TestCase):
    def test_register_features_before_static_frontend(self):
        with tempfile.TemporaryDirectory() as root:
            app = create_app(Path(root))
            paths = [route.path for route in app.routes]
            self.assertEqual(paths[-1], "")
            self.assertEqual(len(paths), len(set(paths)))
            for path in (
                "/api/health",
                "/api/inspect",
                "/api/analyze",
                "/api/detect",
                "/api/prepare-photo",
                "/api/live/frame",
                "/experiments/",
            ):
                self.assertIn(path, paths[:-1])

    def test_charts_can_be_omitted(self):
        with tempfile.TemporaryDirectory() as root:
            app = create_app(Path(root), classroom_experiments=False)
            self.assertFalse(
                any(route.path.startswith("/experiments") for route in app.routes)
            )
