from __future__ import annotations

from django.http import HttpRequest

from apps.interactions.models import Application, Invitation


def notification_counts(request: HttpRequest) -> dict[str, int]:
    """
    Выполняет логику функции.
    Args:
        request: HTTP-запрос текущего пользователя
    """
    if not request.user.is_authenticated:
        return {
            "header_applications_count": 0,
            "header_invitations_count": 0,
            "header_notifications_count": 0,
        }

    user = request.user

    applications_count = Application.objects.filter(
        project__owner=user,
        status=Application.Status.PENDING,
    ).count()

    invitations_count = 0

    specialist_profile = getattr(user, "specialist_profile", None)
    if specialist_profile:
        invitations_count = Invitation.objects.filter(
            specialist=specialist_profile,
            status=Invitation.Status.PENDING,
        ).count()

    return {
        "header_applications_count": applications_count,
        "header_invitations_count": invitations_count,
        "header_notifications_count": applications_count + invitations_count,
    }
