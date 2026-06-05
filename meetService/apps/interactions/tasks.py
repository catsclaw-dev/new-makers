from __future__ import annotations

from datetime import timedelta
from typing import Any

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives, send_mail
from django.db.models import Count, QuerySet
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils import timezone

from apps.interactions.models import Application, Invitation


User = get_user_model()


@shared_task
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
        subject="Добро пожаловать в MeetService",
        recipient=user.email,
        context={
            "title": "Добро пожаловать в MeetService",
            "preheader": "Аккаунт создан, можно искать команду и проекты.",
            "greeting": f"Здравствуйте, {_display_user(user)}.",
            "intro": (
                "Ваш аккаунт создан. Теперь можно оформить профиль специалиста, "
                "откликаться на проекты или собрать команду для своей идеи."
            ),
            "details": [
                ("Аккаунт", user.username),
                ("Роль по умолчанию", user.get_dynamic_role_display()),
            ],
            "action_url": _absolute_url(reverse("accounts:profile")),
            "action_label": "Открыть профиль",
        },
    )


@shared_task
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
        subject=f"Новый отклик на проект «{application.project.title}»",
        recipient=application.project.owner.email,
        context={
            "title": "Новый отклик",
            "preheader": f"{_display_user(specialist_user)} откликнулся на роль.",
            "greeting": f"Здравствуйте, {_display_user(application.project.owner)}.",
            "intro": (
                f"Специалист {_display_user(specialist_user)} отправил отклик "
                f"на роль «{application.vacancy.title}» в проекте "
                f"«{application.project.title}»."
            ),
            "message": application.message,
            "details": [
                ("Проект", application.project.title),
                ("Роль", application.vacancy.title),
                ("Специалист", _display_user(specialist_user)),
            ],
            "action_url": _absolute_url(reverse("interactions:application_list")),
            "action_label": "Посмотреть отклики",
        },
    )


@shared_task
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
    title = "Отклик принят" if accepted else "Отклик отклонён"
    intro = (
        f"Ваш отклик на роль «{application.vacancy.title}» в проекте "
        f"«{application.project.title}» принят. Вы добавлены в команду проекта."
        if accepted
        else (
            f"Ваш отклик на роль «{application.vacancy.title}» в проекте "
            f"«{application.project.title}» отклонён."
        )
    )

    return _send_theme_email(
        subject=f"{title}: «{application.project.title}»",
        recipient=application.specialist.user.email,
        context={
            "title": title,
            "preheader": f"Статус отклика: {application.get_status_display()}.",
            "greeting": f"Здравствуйте, {_display_user(application.specialist.user)}.",
            "intro": intro,
            "details": [
                ("Проект", application.project.title),
                ("Роль", application.vacancy.title),
                ("Статус", application.get_status_display()),
            ],
            "action_url": _absolute_url(reverse("interactions:application_list")),
            "action_label": "Открыть мои отклики",
        },
    )


@shared_task
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
        subject=f"Вас пригласили в проект «{invitation.project.title}»",
        recipient=invitation.specialist.user.email,
        context={
            "title": "Новое приглашение",
            "preheader": f"Приглашение на роль «{invitation.vacancy.title}».",
            "greeting": f"Здравствуйте, {_display_user(invitation.specialist.user)}.",
            "intro": (
                f"{_display_user(invitation.invited_by)} приглашает вас "
                f"в проект «{invitation.project.title}» на роль "
                f"«{invitation.vacancy.title}»."
            ),
            "message": invitation.message,
            "details": [
                ("Проект", invitation.project.title),
                ("Роль", invitation.vacancy.title),
                ("Пригласил", _display_user(invitation.invited_by)),
            ],
            "action_url": _absolute_url(reverse("interactions:invitation_list")),
            "action_label": "Посмотреть приглашение",
        },
    )


@shared_task
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
    title = "Приглашение принято" if accepted else "Приглашение отклонено"
    specialist_user = invitation.specialist.user

    return _send_theme_email(
        subject=f"{title}: «{invitation.project.title}»",
        recipient=invitation.invited_by.email,
        context={
            "title": title,
            "preheader": f"{_display_user(specialist_user)} ответил на приглашение.",
            "greeting": f"Здравствуйте, {_display_user(invitation.invited_by)}.",
            "intro": (
                f"Специалист {_display_user(specialist_user)} "
                f"{'принял' if accepted else 'отклонил'} приглашение "
                f"в проект «{invitation.project.title}»."
            ),
            "details": [
                ("Проект", invitation.project.title),
                ("Роль", invitation.vacancy.title),
                ("Специалист", _display_user(specialist_user)),
                ("Статус", invitation.get_status_display()),
            ],
            "action_url": _absolute_url(reverse("interactions:invitation_list")),
            "action_label": "Открыть приглашения",
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

    return Invitation.objects.filter(
        status=Invitation.Status.PENDING,
        invited_at__lt=expired_before,
    ).update(
        status=Invitation.Status.EXPIRED,
        responded_at=timezone.now(),
    )


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
        send_mail(
            subject="MeetService: новые отклики ждут рассмотрения",
            message=(
                f"Здравствуйте, {owner.get_full_name() or owner.username}.\n\n"
                f"У ваших проектов есть отклики на рассмотрении: {pending_count}.\n"
                "Откройте личный кабинет MeetService, чтобы принять или отклонить их."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[owner.email],
            fail_silently=False,
        )
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
        send_mail(
            subject="MeetService: у вас есть приглашения в проекты",
            message=(
                f"Здравствуйте, {user.get_full_name() or user.username}.\n\n"
                f"Вас ждут приглашения в проекты: {pending_count}.\n"
                "Откройте MeetService, чтобы принять или отклонить приглашения."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        sent_count += 1

    return sent_count


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
    Отправляет HTML-письмо в едином стиле MeetService.
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
