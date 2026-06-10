from __future__ import annotations

from typing import Any

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.http import HttpRequest

from apps.accounts.models import User
from apps.interactions.emails import enqueue_welcome_email
from apps.specialists.models import SpecialistProfile


class NewMakersSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Адаптер OAuth-регистрации для бизнес-логики New-Makers."""

    def save_user(self, request: HttpRequest, sociallogin: Any, form: Any | None = None) -> User:
        """
        Сохраняет OAuth-пользователя и создает профиль специалиста.
        Args:
            request: HTTP-запрос текущего пользователя
            sociallogin: Объект социальной авторизации allauth
            form: Форма регистрации allauth
        """
        user = super().save_user(request, sociallogin, form)
        user.role = User.UserRole.SPECIALIST
        user.save(update_fields=["role"])

        SpecialistProfile.objects.get_or_create(
            user=user,
            defaults={
                "created_by": user,
                "updated_by": user,
            },
        )
        enqueue_welcome_email(user.pk)

        return user
