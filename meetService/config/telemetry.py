from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SentryConfig:
    """Runtime options used to initialize Sentry."""

    dsn: str
    environment: str
    traces_sample_rate: float
    profiles_sample_rate: float
    send_default_pii: bool
    release: str


def clamp_sample_rate(value: float) -> float:
    """
    Return a Sentry sample rate constrained to the valid 0..1 interval.
    Args:
        value: Проверяемое значение
    """
    return max(0.0, min(value, 1.0))


def build_sentry_config(
    *,
    dsn: str,
    environment: str,
    traces_sample_rate: float,
    profiles_sample_rate: float,
    send_default_pii: bool,
    release: str = "",
) -> SentryConfig | None:
    """
    Build Sentry configuration or return None when DSN is empty.
    Args:
        dsn: DSN проекта Sentry
        environment: Название окружения Sentry
        traces_sample_rate: Доля трассируемых запросов
        profiles_sample_rate: Доля профилируемых запросов
        send_default_pii: Признак отправки персональных данных
        release: Версия релиза приложения
    """
    dsn = dsn.strip()

    if not dsn:
        return None

    return SentryConfig(
        dsn=dsn,
        environment=environment.strip() or "development",
        traces_sample_rate=clamp_sample_rate(traces_sample_rate),
        profiles_sample_rate=clamp_sample_rate(profiles_sample_rate),
        send_default_pii=send_default_pii,
        release=release.strip(),
    )


def sentry_init_kwargs(config: SentryConfig) -> dict[str, Any]:
    """
    Convert SentryConfig into keyword arguments accepted by sentry_sdk.init.
    Args:
        config: Конфигурация Sentry
    """
    kwargs: dict[str, Any] = {
        "dsn": config.dsn,
        "environment": config.environment,
        "traces_sample_rate": config.traces_sample_rate,
        "profiles_sample_rate": config.profiles_sample_rate,
        "send_default_pii": config.send_default_pii,
    }

    if config.release:
        kwargs["release"] = config.release

    return kwargs


def initialize_sentry(config: SentryConfig | None) -> bool:
    """
    Initialize Sentry when config is present and report whether it was enabled.
    Args:
        config: Конфигурация Sentry
    """
    if config is None:
        return False

    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_sdk.init(
        integrations=[
            DjangoIntegration(),
            LoggingIntegration(),
        ],
        **sentry_init_kwargs(config),
    )
    return True
