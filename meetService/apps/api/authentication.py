from allauth.account.models import EmailAddress
from django.utils.translation import gettext_lazy as _
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


class VerifiedEmailTokenAuthentication(TokenAuthentication):
    """TokenAuthentication с проверкой подтверждённой почты."""

    def authenticate_credentials(self, key: str):
        """
        Проверяет токен и подтверждение email пользователя.
        Args:
            key: API-токен из заголовка Authorization
        """
        user, token = super().authenticate_credentials(key)

        if user.is_staff or user.is_superuser:
            return user, token

        if not user.email:
            raise AuthenticationFailed(
                _("У аккаунта не указан email. Использовать API-токен нельзя.")
            )

        email_is_verified = EmailAddress.objects.filter(
            user=user,
            email__iexact=user.email,
            verified=True,
        ).exists()

        if not email_is_verified:
            raise AuthenticationFailed(
                _("Подтверди email перед использованием API-токена.")
            )

        return user, token
