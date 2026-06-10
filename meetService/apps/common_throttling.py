from __future__ import annotations

from functools import wraps
from hashlib import sha256
from typing import Callable

from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext_lazy as _


def request_rate_key(request: HttpRequest, *, scope: str) -> str:
    """Строит cache key без сохранения IP или идентификатора пользователя в явном виде."""
    identity = (
        f"user:{request.user.pk}"
        if request.user.is_authenticated
        else f"ip:{request.META.get('REMOTE_ADDR', 'unknown')}"
    )
    digest = sha256(identity.encode("utf-8")).hexdigest()
    return f"rate-limit:{scope}:{digest}"


def is_rate_limited(
    request: HttpRequest,
    *,
    scope: str,
    limit: int,
    window: int,
) -> bool:
    """Атомарно увеличивает счётчик запросов в cache и проверяет лимит."""
    key = request_rate_key(request, scope=scope)
    if cache.add(key, 1, timeout=window):
        return False

    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=window)
        return False
    return count > limit


def rate_limit(*, scope: str, limit: int, window: int) -> Callable:
    """Ограничивает частоту POST-запросов к HTML endpoint."""

    def decorator(view: Callable) -> Callable:
        @wraps(view)
        def wrapped(request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
            if request.method == "POST" and is_rate_limited(
                request,
                scope=scope,
                limit=limit,
                window=window,
            ):
                return HttpResponse(
                    _("Слишком много запросов. Повтори попытку позже."),
                    status=429,
                )
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
