from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.db import transaction


logger = logging.getLogger(__name__)


def enqueue_welcome_email(user_id: int | None) -> None:
    """
    Ставит в очередь приветственное письмо пользователю.
    Args:
        user_id: Идентификатор пользователя
    """
    if not _can_enqueue(user_id):
        return

    from apps.interactions.tasks import send_welcome_email

    transaction.on_commit(lambda: _safe_delay(send_welcome_email, user_id))


def enqueue_application_created_email(application_id: int | None) -> None:
    """
    Ставит в очередь письмо владельцу проекта о новом отклике.
    Args:
        application_id: Идентификатор отклика
    """
    if not _can_enqueue(application_id):
        return

    from apps.interactions.tasks import send_application_created_email

    transaction.on_commit(lambda: _safe_delay(send_application_created_email, application_id))


def enqueue_application_status_email(application_id: int | None) -> None:
    """
    Ставит в очередь письмо специалисту о решении по отклику.
    Args:
        application_id: Идентификатор отклика
    """
    if not _can_enqueue(application_id):
        return

    from apps.interactions.tasks import send_application_status_email

    transaction.on_commit(lambda: _safe_delay(send_application_status_email, application_id))


def enqueue_invitation_created_email(invitation_id: int | None) -> None:
    """
    Ставит в очередь письмо специалисту о новом приглашении.
    Args:
        invitation_id: Идентификатор приглашения
    """
    if not _can_enqueue(invitation_id):
        return

    from apps.interactions.tasks import send_invitation_created_email

    transaction.on_commit(lambda: _safe_delay(send_invitation_created_email, invitation_id))


def enqueue_invitation_status_email(invitation_id: int | None) -> None:
    """
    Ставит в очередь письмо владельцу проекта об ответе на приглашение.
    Args:
        invitation_id: Идентификатор приглашения
    """
    if not _can_enqueue(invitation_id):
        return

    from apps.interactions.tasks import send_invitation_status_email

    transaction.on_commit(lambda: _safe_delay(send_invitation_status_email, invitation_id))


def _can_enqueue(object_id: int | None) -> bool:
    """
    Проверяет, можно ли ставить email-уведомление в очередь.
    Args:
        object_id: Идентификатор объекта уведомления
    """
    return bool(object_id and settings.EMAIL_NOTIFICATIONS_ENABLED)


def _safe_delay(task: Any, object_id: int | None) -> None:
    """
    Безопасно отправляет Celery-задачу без поломки пользовательского запроса.
    Args:
        task: Celery-задача отправки письма
        object_id: Идентификатор объекта уведомления
    """
    try:
        task.delay(object_id)
    except Exception:
        logger.exception("Не удалось поставить email-уведомление в очередь.")
