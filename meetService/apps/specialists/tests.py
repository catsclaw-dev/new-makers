from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.directories.models import Role
from apps.specialists.forms import SpecialistProfileForm
from apps.specialists.models import SpecialistProfile


User = get_user_model()


class SpecialistProfileFormTests(TestCase):
    def test_short_bio_is_invalid(self) -> None:
        """
        Проверяет сценарий `test_short_bio_is_invalid`.
        """
        form = SpecialistProfileForm(
            data={
                "level": SpecialistProfile.Level.JUNIOR,
                "status": SpecialistProfile.AvailabilityStatus.LOOKING,
                "bio": "Слишком кратко",
                "experience_years": 2,
                "github_url": "",
                "gitlab_url": "",
                "portfolio_url": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("bio", form.errors)

    def test_experience_cannot_exceed_business_limit(self) -> None:
        """
        Проверяет сценарий `test_experience_cannot_exceed_business_limit`.
        """
        form = SpecialistProfileForm(
            data={
                "level": SpecialistProfile.Level.SENIOR,
                "status": SpecialistProfile.AvailabilityStatus.OPEN,
                "bio": "Опытный специалист для командной разработки.",
                "experience_years": 61,
                "github_url": "",
                "gitlab_url": "",
                "portfolio_url": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("experience_years", form.errors)


class SpecialistVisibilityTests(TestCase):
    """Тесты видимости профилей специалистов."""

    def setUp(self) -> None:
        """
        Подготавливает пользователей и роль специалиста.
        """
        self.role = Role.objects.create(
            name="Backend-разработчик",
            slug="backend-developer",
        )
        self.visible_user = User.objects.create_user(
            username="visible-specialist",
            password="password",
        )
        self.hidden_user = User.objects.create_user(
            username="hidden-specialist",
            password="password",
        )
        self.admin = User.objects.create_user(
            username="admin",
            password="password",
            is_staff=True,
        )
        self.visible_profile = SpecialistProfile.objects.create(
            user=self.visible_user,
            main_role=self.role,
            bio="Открытый специалист для проектной команды.",
            status=SpecialistProfile.AvailabilityStatus.LOOKING,
        )
        self.hidden_profile = SpecialistProfile.objects.create(
            user=self.hidden_user,
            main_role=self.role,
            bio="Скрытый специалист для проверки приватности.",
            status=SpecialistProfile.AvailabilityStatus.HIDDEN,
        )

    def test_hidden_specialist_is_not_listed(self) -> None:
        """
        Проверяет, что скрытый специалист не отображается в каталоге.
        """
        response = self.client.get(reverse("specialists:specialist_list"))

        self.assertContains(response, self.visible_user.username)
        self.assertNotContains(response, self.hidden_user.username)

    def test_anonymous_user_cannot_open_hidden_specialist_detail(self) -> None:
        """
        Проверяет закрытие прямой ссылки на скрытый профиль для гостей.
        """
        response = self.client.get(
            reverse(
                "specialists:specialist_detail",
                kwargs={"pk": self.hidden_profile.pk},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_hidden_specialist_owner_can_open_detail(self) -> None:
        """
        Проверяет доступ владельца к своему скрытому профилю.
        """
        self.client.force_login(self.hidden_user)

        response = self.client.get(
            reverse(
                "specialists:specialist_detail",
                kwargs={"pk": self.hidden_profile.pk},
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_admin_can_open_hidden_specialist_detail(self) -> None:
        """
        Проверяет доступ администратора к скрытому профилю.
        """
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse(
                "specialists:specialist_detail",
                kwargs={"pk": self.hidden_profile.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
