from __future__ import annotations

from types import ModuleType
from unittest import mock

from django.test import SimpleTestCase

from config.telemetry import (
    SentryConfig,
    build_sentry_config,
    clamp_sample_rate,
    initialize_sentry,
    sentry_init_kwargs,
)


class SentryTelemetryTests(SimpleTestCase):
    """Tests for Sentry configuration helpers."""

    def test_empty_dsn_disables_sentry(self) -> None:
        """Sentry is not initialized when DSN is empty."""
        config = build_sentry_config(
            dsn="",
            environment="production",
            traces_sample_rate=1.0,
            profiles_sample_rate=1.0,
            send_default_pii=True,
        )

        self.assertIsNone(config)

    def test_whitespace_dsn_disables_sentry(self) -> None:
        """Whitespace-only DSN is treated as missing."""
        config = build_sentry_config(
            dsn="   ",
            environment="production",
            traces_sample_rate=1.0,
            profiles_sample_rate=1.0,
            send_default_pii=True,
        )

        self.assertIsNone(config)

    def test_dsn_is_trimmed(self) -> None:
        """Sentry DSN is stripped before being stored."""
        config = build_sentry_config(
            dsn=" https://example@sentry.local/1 ",
            environment="production",
            traces_sample_rate=0.5,
            profiles_sample_rate=0.25,
            send_default_pii=False,
        )

        self.assertIsNotNone(config)
        self.assertEqual(config.dsn, "https://example@sentry.local/1")

    def test_blank_environment_defaults_to_development(self) -> None:
        """Empty Sentry environment falls back to development."""
        config = build_sentry_config(
            dsn="https://example@sentry.local/1",
            environment=" ",
            traces_sample_rate=0.5,
            profiles_sample_rate=0.25,
            send_default_pii=False,
        )

        self.assertIsNotNone(config)
        self.assertEqual(config.environment, "development")

    def test_sample_rate_below_zero_is_clamped(self) -> None:
        """Sentry sample rates cannot be lower than zero."""
        self.assertEqual(clamp_sample_rate(-1.0), 0.0)

    def test_sample_rate_above_one_is_clamped(self) -> None:
        """Sentry sample rates cannot be greater than one."""
        self.assertEqual(clamp_sample_rate(2.0), 1.0)

    def test_valid_sample_rate_is_preserved(self) -> None:
        """Valid Sentry sample rates are not changed."""
        self.assertEqual(clamp_sample_rate(0.75), 0.75)

    def test_build_config_clamps_tracing_rates(self) -> None:
        """Trace and profile rates are normalized while building config."""
        config = build_sentry_config(
            dsn="https://example@sentry.local/1",
            environment="production",
            traces_sample_rate=2.0,
            profiles_sample_rate=-1.0,
            send_default_pii=False,
        )

        self.assertIsNotNone(config)
        self.assertEqual(config.traces_sample_rate, 1.0)
        self.assertEqual(config.profiles_sample_rate, 0.0)

    def test_init_kwargs_omit_empty_release(self) -> None:
        """Sentry init kwargs do not include an empty release."""
        kwargs = sentry_init_kwargs(
            SentryConfig(
                dsn="https://example@sentry.local/1",
                environment="production",
                traces_sample_rate=0.5,
                profiles_sample_rate=0.25,
                send_default_pii=False,
                release="",
            )
        )

        self.assertNotIn("release", kwargs)

    def test_init_kwargs_include_release_when_present(self) -> None:
        """Sentry release is passed when configured."""
        kwargs = sentry_init_kwargs(
            SentryConfig(
                dsn="https://example@sentry.local/1",
                environment="production",
                traces_sample_rate=0.5,
                profiles_sample_rate=0.25,
                send_default_pii=False,
                release="meetservice@1.0.0",
            )
        )

        self.assertEqual(kwargs["release"], "meetservice@1.0.0")

    def test_initialize_sentry_returns_false_without_config(self) -> None:
        """Sentry initialization reports disabled state when config is absent."""
        self.assertFalse(initialize_sentry(None))

    def test_initialize_sentry_calls_sdk_init(self) -> None:
        """Sentry initialization delegates to sentry_sdk.init."""
        sentry_sdk = ModuleType("sentry_sdk")
        sentry_sdk.init = mock.Mock()

        django_integration_module = ModuleType("sentry_sdk.integrations.django")
        django_integration_module.DjangoIntegration = mock.Mock(
            return_value="django-integration"
        )
        logging_integration_module = ModuleType("sentry_sdk.integrations.logging")
        logging_integration_module.LoggingIntegration = mock.Mock(
            return_value="logging-integration"
        )

        config = SentryConfig(
            dsn="https://example@sentry.local/1",
            environment="production",
            traces_sample_rate=0.5,
            profiles_sample_rate=0.25,
            send_default_pii=False,
            release="meetservice@1.0.0",
        )

        with mock.patch.dict(
            "sys.modules",
            {
                "sentry_sdk": sentry_sdk,
                "sentry_sdk.integrations.django": django_integration_module,
                "sentry_sdk.integrations.logging": logging_integration_module,
            },
        ):
            enabled = initialize_sentry(config)

        self.assertTrue(enabled)
        sentry_sdk.init.assert_called_once()
        _, kwargs = sentry_sdk.init.call_args
        self.assertEqual(kwargs["dsn"], config.dsn)
        self.assertEqual(kwargs["environment"], config.environment)
        self.assertEqual(kwargs["release"], config.release)
        self.assertEqual(
            kwargs["integrations"],
            ["django-integration", "logging-integration"],
        )
