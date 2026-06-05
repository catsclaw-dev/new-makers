from __future__ import annotations

import importlib

from django.test import SimpleTestCase, override_settings
from django.urls import NoReverseMatch, clear_url_caches, reverse

import config.urls


def reload_urlconf() -> None:
    """
    Reload project URLs after settings overrides change conditional routes.
    """
    importlib.reload(config.urls)
    clear_url_caches()


class SilkConfigurationTests(SimpleTestCase):
    """Tests for Django Silk URL exposure."""

    @override_settings(DEBUG=True, SILK_ENABLED=True, ROOT_URLCONF="config.urls")
    def test_silk_url_is_available_when_enabled(self) -> None:
        """
        Silk index route is mounted when debug profiling is enabled.
        """
        reload_urlconf()

        self.assertEqual(reverse("silk:summary"), "/silk/")

    @override_settings(DEBUG=True, SILK_ENABLED=False, ROOT_URLCONF="config.urls")
    def test_silk_url_is_hidden_when_disabled(self) -> None:
        """
        Silk index route is not mounted when profiling flag is disabled.
        """
        reload_urlconf()

        with self.assertRaises(NoReverseMatch):
            reverse("silk:summary")

        reload_urlconf()
