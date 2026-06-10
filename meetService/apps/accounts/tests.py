from pathlib import Path
from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.specialists.models import SpecialistProfile


User = get_user_model()


class AccountEmailTests(TestCase):
    """Тесты управления email в личном кабинете."""

    def test_register_creates_unverified_user_and_redirects_to_login(self) -> None:
        """
        Проверяет создание аккаунта с обязательным подтверждением email.
        """
        with patch("apps.accounts.views.enqueue_welcome_email") as enqueue_mock:
            response = self.client.post(
                reverse("accounts:register"),
                {
                    "username": "new_user",
                    "email": "new-user@example.com",
                    "first_name": "New",
                    "last_name": "User",
                    "password1": "StrongPassword123!",
                    "password2": "StrongPassword123!",
                },
            )

        self.assertRedirects(response, reverse("accounts:login"))
        user = User.objects.get(
            username="new_user",
            email="new-user@example.com",
        )
        self.assertTrue(SpecialistProfile.objects.filter(user=user).exists())
        self.assertTrue(
            EmailAddress.objects.filter(
                user=user,
                email="new-user@example.com",
                primary=True,
                verified=False,
            ).exists()
        )
        enqueue_mock.assert_called_once_with(user.pk)

    def test_register_rolls_back_if_confirmation_fails(self) -> None:
        """Проверяет отсутствие частично созданного аккаунта при ошибке."""
        with patch.object(
            EmailAddress,
            "send_confirmation",
            side_effect=RuntimeError("Email delivery failed"),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    reverse("accounts:register"),
                    {
                        "username": "failed_user",
                        "email": "failed-user@example.com",
                        "first_name": "Failed",
                        "last_name": "User",
                        "password1": "StrongPassword123!",
                        "password2": "StrongPassword123!",
                    },
                )

        self.assertFalse(User.objects.filter(username="failed_user").exists())
        self.assertFalse(
            SpecialistProfile.objects.filter(user__username="failed_user").exists()
        )
        self.assertFalse(
            EmailAddress.objects.filter(email="failed-user@example.com").exists()
        )

    def test_regular_user_without_email_sees_email_notice(self) -> None:
        """
        Проверяет предупреждение о пустом email для обычного пользователя.
        """
        user = User.objects.create_user(username="oauth_user", password="password")
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:profile"))

        self.assertContains(response, "Укажите email для уведомлений")

    def test_staff_user_without_email_does_not_see_email_notice(self) -> None:
        """
        Проверяет, что администратор без email не получает предупреждение.
        """
        user = User.objects.create_user(
            username="admin",
            password="password",
            is_staff=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:profile"))

        self.assertNotContains(response, "Укажите email для уведомлений")

    def test_user_can_update_email(self) -> None:
        """
        Проверяет сохранение email текущего пользователя.
        """
        user = User.objects.create_user(username="oauth_user", password="password")
        self.client.force_login(user)

        response = self.client.post(
            reverse("accounts:update_email"),
            {"email": "new-email@example.com"},
        )
        user.refresh_from_db()

        self.assertRedirects(response, reverse("accounts:login"))
        self.assertEqual(user.email, "new-email@example.com")
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertTrue(
            EmailAddress.objects.filter(
                user=user,
                email="new-email@example.com",
                primary=True,
                verified=False,
            ).exists()
        )

    def test_update_email_preserves_verified_address(self) -> None:
        """Проверяет повторный выбор ранее подтверждённого адреса."""
        user = User.objects.create_user(
            username="verified_user",
            email="old@example.com",
            password="password",
        )
        EmailAddress.objects.create(
            user=user,
            email="verified@example.com",
            verified=True,
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("accounts:update_email"),
            {"email": "verified@example.com"},
        )

        self.assertRedirects(response, reverse("accounts:profile"))
        self.assertIn("_auth_user_id", self.client.session)

    def test_user_cannot_set_duplicate_email(self) -> None:
        """
        Проверяет запрет дублирования email.
        """
        User.objects.create_user(
            username="existing",
            email="taken@example.com",
            password="password",
        )
        user = User.objects.create_user(username="oauth_user", password="password")
        self.client.force_login(user)

        response = self.client.post(
            reverse("accounts:update_email"),
            {"email": "taken@example.com"},
        )
        user.refresh_from_db()

        self.assertRedirects(response, reverse("accounts:profile"))
        self.assertEqual(user.email, "")

    def test_register_duplicate_email_explains_existing_account(self) -> None:
        """
        Проверяет понятное сообщение при регистрации на занятую почту.
        """
        User.objects.create_user(
            username="github_user",
            email="taken@example.com",
            password="password",
        )

        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "new_user",
                "email": "taken@example.com",
                "first_name": "New",
                "last_name": "User",
                "password1": "StrongPassword123!",
                "password2": "StrongPassword123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Пользователь с таким email уже зарегистрирован")
        self.assertContains(response, "OAuth-провайдер")

    def test_email_is_case_insensitively_unique_in_database(self) -> None:
        User.objects.create_user(
            username="first",
            email="unique@example.com",
            password="password",
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(
                username="second",
                email="UNIQUE@example.com",
                password="password",
            )

    def test_socialaccount_templates_extend_project_base(self) -> None:
        """
        Проверяет, что OAuth-страницы используют базовый шаблон сайта.
        """
        templates_dir = Path(__file__).resolve().parents[2] / "templates"
        template_names = [
            "socialaccount/login_redirect.html",
            "socialaccount/login.html",
            "socialaccount/authentication_error.html",
            "socialaccount/login_cancelled.html",
        ]

        for template_name in template_names:
            content = (templates_dir / template_name).read_text()
            self.assertIn('{% extends "base.html" %}', content)
