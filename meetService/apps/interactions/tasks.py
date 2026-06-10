from __future__ import annotations

from datetime import timedelta
import logging
import smtplib
from typing import Any

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.db.models import Count, QuerySet
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils import timezone
from django.utils.translation import gettext as _, ngettext

from apps.interactions.models import Application, Invitation


User = get_user_model()
logger = logging.getLogger(__name__)
EMAIL_TASK_OPTIONS = {
    "autoretry_for": (OSError, smtplib.SMTPException),
    "retry_backoff": True,
    "retry_jitter": True,
    "retry_kwargs": {"max_retries": 5},
}


@shared_task(**EMAIL_TASK_OPTIONS)
def send_welcome_email(user_id: int) -> int:
    """
    Отправляет приветственное письмо новому пользователю.
    Args:
        user_id: Идентификатор пользователя
    """
    user = User.objects.filter(pk=user_id).first()

    if not user or not user.email:
        return 0

    return _send_theme_email(
        subject=_("Добро пожаловать в New-Makers"),
        recipient=user.email,
        context={
            "title": _("Добро пожаловать в New-Makers"),
            "preheader": _("Аккаунт создан, можно искать команду и проекты."),
            "greeting": _("Здравствуйте, %(name)s.") % {"name": _display_user(user)},
            "intro": (
                _(
                    "Ваш аккаунт создан. Теперь можно оформить профиль специалиста, "
                    "откликаться на проекты или собрать команду для своей идеи."
                )
            ),
            "details": [
                (_("Аккаунт"), user.username),
                (_("Роль по умолчанию"), user.get_dynamic_role_display()),
            ],
            "action_url": _absolute_url(reverse("accounts:profile")),
            "action_label": _("Открыть профиль"),
        },
    )


@shared_task(**EMAIL_TASK_OPTIONS)
def send_application_created_email(application_id: int) -> int:
    """
    Отправляет письмо владельцу проекта о новом отклике.
    Args:
        application_id: Идентификатор отклика
    """
    application = (
        Application.objects.select_related(
            "project",
            "project__owner",
            "vacancy",
            "vacancy__role",
            "specialist",
            "specialist__user",
        )
        .filter(pk=application_id)
        .first()
    )

    if not application or not application.project.owner.email:
        return 0

    specialist_user = application.specialist.user

    return _send_theme_email(
        subject=_("Новый отклик на проект «%(project)s»")
        % {"project": application.project.title},
        recipient=application.project.owner.email,
        context={
            "title": _("Новый отклик"),
            "preheader": _("%(specialist)s откликнулся на роль.")
            % {"specialist": _display_user(specialist_user)},
            "greeting": _("Здравствуйте, %(name)s.")
            % {"name": _display_user(application.project.owner)},
            "intro": (
                _(
                    "Специалист %(specialist)s отправил отклик на роль «%(role)s» "
                    "в проекте «%(project)s»."
                )
                % {
                    "specialist": _display_user(specialist_user),
                    "role": application.vacancy.title,
                    "project": application.project.title,
                }
            ),
            "message": application.message,
            "details": [
                (_("Проект"), application.project.title),
                (_("Роль"), application.vacancy.title),
                (_("Специалист"), _display_user(specialist_user)),
            ],
            "action_url": _absolute_url(reverse("interactions:application_list")),
            "action_label": _("Посмотреть отклики"),
        },
    )


@shared_task(**EMAIL_TASK_OPTIONS)
def send_application_status_email(application_id: int) -> int:
    """
    Отправляет письмо специалисту о решении по отклику.
    Args:
        application_id: Идентификатор отклика
    """
    application = (
        Application.objects.select_related(
            "project",
            "vacancy",
            "vacancy__role",
            "specialist",
            "specialist__user",
        )
        .filter(pk=application_id)
        .first()
    )

    if not application or not application.specialist.user.email:
        return 0

    accepted = application.status == Application.Status.ACCEPTED
    title = _("Отклик принят") if accepted else _("Отклик отклонён")
    intro = (
        _(
            "Ваш отклик на роль «%(role)s» в проекте «%(project)s» принят. "
            "Вы добавлены в команду проекта."
        )
        % {"role": application.vacancy.title, "project": application.project.title}
        if accepted
        else (
            _("Ваш отклик на роль «%(role)s» в проекте «%(project)s» отклонён.")
            % {"role": application.vacancy.title, "project": application.project.title}
        )
    )

    return _send_theme_email(
        subject=_("%(status)s: «%(project)s»")
        % {"status": title, "project": application.project.title},
        recipient=application.specialist.user.email,
        context={
            "title": title,
            "preheader": _("Статус отклика: %(status)s.")
            % {"status": application.get_status_display()},
            "greeting": _("Здравствуйте, %(name)s.")
            % {"name": _display_user(application.specialist.user)},
            "intro": intro,
            "details": [
                (_("Проект"), application.project.title),
                (_("Роль"), application.vacancy.title),
                (_("Статус"), application.get_status_display()),
            ],
            "action_url": _absolute_url(reverse("interactions:application_list")),
            "action_label": _("Открыть мои отклики"),
        },
    )


@shared_task(**EMAIL_TASK_OPTIONS)
def send_invitation_created_email(invitation_id: int) -> int:
    """
    Отправляет письмо специалисту о новом приглашении.
    Args:
        invitation_id: Идентификатор приглашения
    """
    invitation = (
        Invitation.objects.select_related(
            "project",
            "vacancy",
            "vacancy__role",
            "specialist",
            "specialist__user",
            "invited_by",
        )
        .filter(pk=invitation_id)
        .first()
    )

    if not invitation or not invitation.specialist.user.email:
        return 0

    return _send_theme_email(
        subject=_("Вас пригласили в проект «%(project)s»")
        % {"project": invitation.project.title},
        recipient=invitation.specialist.user.email,
        context={
            "title": _("Новое приглашение"),
            "preheader": _("Приглашение на роль «%(role)s».")
            % {"role": invitation.vacancy.title},
            "greeting": _("Здравствуйте, %(name)s.")
            % {"name": _display_user(invitation.specialist.user)},
            "intro": (
                _("%(owner)s приглашает вас в проект «%(project)s» на роль «%(role)s».")
                % {
                    "owner": _display_user(invitation.invited_by),
                    "project": invitation.project.title,
                    "role": invitation.vacancy.title,
                }
            ),
            "message": invitation.message,
            "details": [
                (_("Проект"), invitation.project.title),
                (_("Роль"), invitation.vacancy.title),
                (_("Пригласил"), _display_user(invitation.invited_by)),
            ],
            "action_url": _absolute_url(reverse("interactions:invitation_list")),
            "action_label": _("Посмотреть приглашение"),
        },
    )


@shared_task(**EMAIL_TASK_OPTIONS)
def send_invitation_status_email(invitation_id: int) -> int:
    """
    Отправляет владельцу проекта письмо об ответе на приглашение.
    Args:
        invitation_id: Идентификатор приглашения
    """
    invitation = (
        Invitation.objects.select_related(
            "project",
            "vacancy",
            "specialist",
            "specialist__user",
            "invited_by",
        )
        .filter(pk=invitation_id)
        .first()
    )

    if not invitation or not invitation.invited_by.email:
        return 0

    accepted = invitation.status == Invitation.Status.ACCEPTED
    title = _("Приглашение принято") if accepted else _("Приглашение отклонено")
    specialist_user = invitation.specialist.user

    return _send_theme_email(
        subject=_("%(status)s: «%(project)s»")
        % {"status": title, "project": invitation.project.title},
        recipient=invitation.invited_by.email,
        context={
            "title": title,
            "preheader": _("%(specialist)s ответил на приглашение.")
            % {"specialist": _display_user(specialist_user)},
            "greeting": _("Здравствуйте, %(name)s.")
            % {"name": _display_user(invitation.invited_by)},
            "intro": (
                _(
                    "Специалист %(specialist)s %(decision)s приглашение "
                    "в проект «%(project)s»."
                )
                % {
                    "specialist": _display_user(specialist_user),
                    "decision": _("принял") if accepted else _("отклонил"),
                    "project": invitation.project.title,
                }
            ),
            "details": [
                (_("Проект"), invitation.project.title),
                (_("Роль"), invitation.vacancy.title),
                (_("Специалист"), _display_user(specialist_user)),
                (_("Статус"), invitation.get_status_display()),
            ],
            "action_url": _absolute_url(reverse("interactions:invitation_list")),
            "action_label": _("Открыть приглашения"),
        },
    )


@shared_task
def expire_stale_invitations(invitation_lifetime_days: int | None = None) -> int:
    """
    Переводит старые ожидающие приглашения в статус истекших.
    Args:
        invitation_lifetime_days: Срок жизни приглашения в днях
    """
    lifetime_days = invitation_lifetime_days or settings.INVITATION_EXPIRE_DAYS
    expired_before = timezone.now() - timedelta(days=lifetime_days)

    invitations = Invitation.objects.filter(
        status=Invitation.Status.PENDING,
        invited_at__lt=expired_before,
    ).order_by("pk")
    responded_at = timezone.now()
    updated_count = 0

    for invitation in invitations.iterator():
        invitation.status = Invitation.Status.EXPIRED
        invitation.responded_at = responded_at
        invitation.save(update_fields=["status", "responded_at"])
        updated_count += 1

    return updated_count


@shared_task
def send_pending_application_digest() -> int:
    """
    Отправляет владельцам проектов сводку по ожидающим откликам.
    """
    owners = _owners_with_pending_applications()
    sent_count = 0

    for owner in owners:
        if not owner.email:
            continue

        pending_count = getattr(owner, "pending_applications_count", 0)
        try:
            send_pending_application_digest_email.delay(owner.pk, pending_count)
        except Exception:
            logger.exception("Не удалось поставить application digest в очередь.")
        else:
            sent_count += 1

    return sent_count


@shared_task
def send_pending_invitation_digest() -> int:
    """
    Отправляет специалистам сводку по ожидающим приглашениям.
    """
    specialists = _users_with_pending_invitations()
    sent_count = 0

    for user in specialists:
        if not user.email:
            continue

        pending_count = getattr(user, "pending_invitations_count", 0)
        try:
            send_pending_invitation_digest_email.delay(user.pk, pending_count)
        except Exception:
            logger.exception("Не удалось поставить invitation digest в очередь.")
        else:
            sent_count += 1

    return sent_count


@shared_task(**EMAIL_TASK_OPTIONS)
def send_pending_application_digest_email(owner_id: int, pending_count: int) -> int:
    """Отправляет одному владельцу HTML-сводку по ожидающим откликам."""
    owner = User.objects.filter(pk=owner_id).first()

    if not owner or not owner.email:
        return 0

    return _send_theme_email(
        subject=_("New-Makers: новые отклики ждут рассмотрения"),
        recipient=owner.email,
        context={
            "title": _("Новые отклики ждут рассмотрения"),
            "preheader": _("У ваших проектов есть отклики, которые нужно обработать."),
            "greeting": _("Здравствуйте, %(name)s.")
            % {"name": owner.get_full_name() or owner.username},
            "intro": ngettext(
                "У ваших проектов есть %(count)s отклик на рассмотрении.",
                "У ваших проектов есть %(count)s откликов на рассмотрении.",
                pending_count,
            )
            % {"count": pending_count},
            "details": [
                (_("Ожидающих откликов"), pending_count),
                (_("Действие"), _("Принять или отклонить отклики")),
            ],
            "action_url": _absolute_url(reverse("interactions:application_list")),
            "action_label": _("Открыть отклики"),
        },
    )


@shared_task(**EMAIL_TASK_OPTIONS)
def send_pending_invitation_digest_email(user_id: int, pending_count: int) -> int:
    """Отправляет одному специалисту HTML-сводку по ожидающим приглашениям."""
    user = User.objects.filter(pk=user_id).first()

    if not user or not user.email:
        return 0

    return _send_theme_email(
        subject=_("New-Makers: у вас есть приглашения в проекты"),
        recipient=user.email,
        context={
            "title": _("Приглашения ждут ответа"),
            "preheader": _(
                "У вас есть приглашения в проекты, которые нужно обработать."
            ),
            "greeting": _("Здравствуйте, %(name)s.")
            % {"name": user.get_full_name() or user.username},
            "intro": ngettext(
                "Вас ждёт %(count)s приглашение в проект.",
                "Вас ждут %(count)s приглашений в проекты.",
                pending_count,
            )
            % {"count": pending_count},
            "details": [
                (_("Ожидающих приглашений"), pending_count),
                (_("Действие"), _("Принять или отклонить приглашения")),
            ],
            "action_url": _absolute_url(reverse("interactions:invitation_list")),
            "action_label": _("Открыть приглашения"),
        },
    )


def _owners_with_pending_applications() -> QuerySet:
    """
    Возвращает владельцев проектов с ожидающими откликами.
    """
    return (
        User.objects.filter(
            owned_projects__applications__status=Application.Status.PENDING,
        )
        .annotate(
            pending_applications_count=Count(
                "owned_projects__applications",
                distinct=True,
            )
        )
        .filter(pending_applications_count__gt=0)
        .order_by("username")
    )


def _users_with_pending_invitations() -> QuerySet:
    """
    Возвращает пользователей-специалистов с ожидающими приглашениями.
    """
    return (
        User.objects.filter(
            specialist_profile__invitations__status=Invitation.Status.PENDING,
        )
        .annotate(
            pending_invitations_count=Count(
                "specialist_profile__invitations",
                distinct=True,
            )
        )
        .filter(pending_invitations_count__gt=0)
        .order_by("username")
    )


def _send_theme_email(*, subject: str, recipient: str, context: dict[str, Any]) -> int:
    """
    Отправляет HTML-письмо в едином стиле New-Makers.
    Args:
        subject: Тема письма
        recipient: Email получателя
        context: Контекст шаблона письма
    """
    if not settings.EMAIL_NOTIFICATIONS_ENABLED:
        return 0

    html_body = render_to_string("emails/base.html", context)
    text_body = render_to_string(
        "emails/base.txt",
        {
            **context,
            "plain_message": strip_tags(context.get("message", "")),
        },
    )
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    )
    email.attach_alternative(html_body, "text/html")
    return email.send()


def _absolute_url(path: str) -> str:
    """
    Возвращает абсолютную ссылку сайта для письма.
    Args:
        path: Относительный путь
    """
    return f"{settings.SITE_URL}{path}"


def _display_user(user: object) -> str:
    """
    Возвращает отображаемое имя пользователя для письма.
    Args:
        user: Объект пользователя
    """
    full_name = user.get_full_name()
    return full_name or user.username
