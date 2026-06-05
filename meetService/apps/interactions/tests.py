from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.directories.models import Role
from apps.interactions.models import Application
from apps.projects.models import Project, ProjectMembership, ProjectVacancy
from apps.specialists.models import SpecialistProfile


User = get_user_model()


class ApplicationBusinessTests(TestCase):
    def setUp(self) -> None:
        """
        Подготавливает тестовые данные.
        """
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="password",
        )
        self.specialist_user = User.objects.create_user(
            username="specialist",
            email="specialist@example.com",
            password="password",
        )
        self.specialist = SpecialistProfile.objects.create(
            user=self.specialist_user,
            bio="Специалист с опытом участия в проектных командах.",
        )
        self.owner_profile = SpecialistProfile.objects.create(
            user=self.owner,
            bio="Владелец проекта с техническим профилем.",
        )
        self.role = Role.objects.create(
            name="Frontend-разработчик",
            slug="frontend-developer",
        )
        self.project = Project.objects.create(
            owner=self.owner,
            title="Платформа команд",
            short_description="Поиск команды для проектов.",
            description="Подробное описание опубликованного проекта.",
            goal="Найти участников команды.",
            status=Project.Status.PUBLISHED,
        )
        self.vacancy = ProjectVacancy.objects.create(
            project=self.project,
            role=self.role,
            title="Frontend",
            description="Нужен frontend-разработчик.",
            required_count=1,
        )

    def test_application_to_own_project_is_invalid(self) -> None:
        """
        Проверяет сценарий `test_application_to_own_project_is_invalid`.
        """
        application = Application(
            project=self.project,
            vacancy=self.vacancy,
            specialist=self.owner_profile,
            message="Хочу откликнуться на свой проект.",
        )

        with self.assertRaises(ValidationError):
            application.full_clean()

    def test_duplicate_active_application_is_invalid(self) -> None:
        """
        Проверяет сценарий `test_duplicate_active_application_is_invalid`.
        """
        Application.objects.create(
            project=self.project,
            vacancy=self.vacancy,
            specialist=self.specialist,
            message="Первый отклик.",
        )

        duplicate = Application(
            project=self.project,
            vacancy=self.vacancy,
            specialist=self.specialist,
            message="Повторный отклик.",
        )

        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_accept_application_adds_specialist_to_project(self) -> None:
        """
        Проверяет сценарий `test_accept_application_adds_specialist_to_project`.
        """
        application = Application.objects.create(
            project=self.project,
            vacancy=self.vacancy,
            specialist=self.specialist,
            message="Готов присоединиться к команде.",
        )

        membership = application.accept(reviewed_by=self.owner)
        self.vacancy.refresh_from_db()
        application.refresh_from_db()

        self.assertEqual(application.status, Application.Status.ACCEPTED)
        self.assertEqual(membership.status, ProjectMembership.Status.ACTIVE)
        self.assertEqual(self.vacancy.current_count, 1)
        self.assertEqual(self.vacancy.status, ProjectVacancy.Status.CLOSED)
