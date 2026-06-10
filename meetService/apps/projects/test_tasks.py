from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.directories.models import Role
from apps.projects.models import Project, ProjectMembership, ProjectVacancy
from apps.projects.tasks import sync_project_vacancy_counts
from apps.specialists.models import SpecialistProfile


User = get_user_model()


class ProjectTaskTests(TestCase):
    """Тесты фоновых задач проектов."""

    def setUp(self) -> None:
        """
        Подготавливает проект, роль и специалиста.
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
            bio="Готов участвовать.",
        )
        self.role = Role.objects.create(
            name="Frontend-разработчик",
            slug="frontend-developer",
        )
        self.project = Project.objects.create(
            owner=self.owner,
            title="Командная платформа",
            short_description="Поиск команды.",
            description="Описание проекта.",
            goal="Запустить MVP.",
            status=Project.Status.PUBLISHED,
        )

    def test_sync_project_vacancy_counts_updates_current_count(self) -> None:
        """
        Проверяет пересчет количества участников по открытой роли.
        """
        vacancy = ProjectVacancy.objects.create(
            project=self.project,
            role=self.role,
            title="Frontend",
            description="Нужен frontend-разработчик.",
            required_count=2,
        )
        ProjectMembership.objects.create(
            project=self.project,
            specialist=self.specialist,
            vacancy=vacancy,
            role=self.role,
            added_by=self.owner,
        )

        changed_count = sync_project_vacancy_counts()
        vacancy.refresh_from_db()

        self.assertEqual(changed_count, 1)
        self.assertEqual(vacancy.current_count, 1)
        self.assertEqual(vacancy.status, ProjectVacancy.Status.OPEN)

    def test_sync_project_vacancy_counts_closes_filled_vacancy(self) -> None:
        """
        Проверяет автоматическое закрытие заполненной роли.
        """
        vacancy = ProjectVacancy.objects.create(
            project=self.project,
            role=self.role,
            title="Frontend",
            description="Нужен frontend-разработчик.",
            required_count=1,
        )
        ProjectMembership.objects.create(
            project=self.project,
            specialist=self.specialist,
            vacancy=vacancy,
            role=self.role,
            added_by=self.owner,
        )

        changed_count = sync_project_vacancy_counts()
        vacancy.refresh_from_db()

        self.assertEqual(changed_count, 1)
        self.assertEqual(vacancy.current_count, 1)
        self.assertEqual(vacancy.status, ProjectVacancy.Status.CLOSED)

    def test_sync_project_vacancy_counts_returns_zero_without_changes(self) -> None:
        """
        Проверяет, что задача не сохраняет уже синхронизированную роль.
        """
        vacancy = ProjectVacancy.objects.create(
            project=self.project,
            role=self.role,
            title="Frontend",
            description="Нужен frontend-разработчик.",
            required_count=2,
        )

        changed_count = sync_project_vacancy_counts()
        vacancy.refresh_from_db()

        self.assertEqual(changed_count, 0)
        self.assertEqual(vacancy.current_count, 0)
        self.assertEqual(vacancy.status, ProjectVacancy.Status.OPEN)

    def test_sync_project_vacancy_counts_keeps_paused_vacancy_paused(self) -> None:
        """
        Проверяет, что задача не переоткрывает роль на паузе.
        """
        vacancy = ProjectVacancy.objects.create(
            project=self.project,
            role=self.role,
            title="Frontend",
            description="Нужен frontend-разработчик.",
            required_count=2,
        )
        ProjectMembership.objects.create(
            project=self.project,
            specialist=self.specialist,
            vacancy=vacancy,
            role=self.role,
            added_by=self.owner,
        )
        ProjectVacancy.objects.filter(pk=vacancy.pk).update(
            status=ProjectVacancy.Status.PAUSED
        )

        changed_count = sync_project_vacancy_counts()
        vacancy.refresh_from_db()

        self.assertEqual(changed_count, 1)
        self.assertEqual(vacancy.current_count, 1)
        self.assertEqual(vacancy.status, ProjectVacancy.Status.PAUSED)

    def test_sync_project_vacancy_counts_keeps_manually_closed_vacancy_closed(self) -> None:
        """
        Проверяет, что задача не переоткрывает вручную закрытую роль.
        """
        vacancy = ProjectVacancy.objects.create(
            project=self.project,
            role=self.role,
            title="Frontend",
            description="Нужен frontend-разработчик.",
            required_count=2,
            current_count=1,
            status=ProjectVacancy.Status.CLOSED,
        )

        changed_count = sync_project_vacancy_counts()
        vacancy.refresh_from_db()

        self.assertEqual(changed_count, 1)
        self.assertEqual(vacancy.current_count, 0)
        self.assertEqual(vacancy.status, ProjectVacancy.Status.CLOSED)

    def test_sync_counts_memberships_by_vacancy_and_includes_paused(self) -> None:
        """Проверяет раздельный подсчёт одинаковых ролей и статус PAUSED."""
        second_user = User.objects.create_user(
            username="paused-specialist",
            email="paused@example.com",
            password="password",
        )
        second_specialist = SpecialistProfile.objects.create(user=second_user)
        first_vacancy = ProjectVacancy.objects.create(
            project=self.project,
            role=self.role,
            title="Frontend A",
            description="Первая роль.",
            required_count=2,
        )
        second_vacancy = ProjectVacancy.objects.create(
            project=self.project,
            role=self.role,
            title="Frontend B",
            description="Вторая роль.",
            required_count=2,
        )
        ProjectMembership.objects.create(
            project=self.project,
            specialist=second_specialist,
            vacancy=first_vacancy,
            role=self.role,
            status=ProjectMembership.Status.PAUSED,
        )

        sync_project_vacancy_counts()
        first_vacancy.refresh_from_db()
        second_vacancy.refresh_from_db()

        self.assertEqual(first_vacancy.current_count, 1)
        self.assertEqual(second_vacancy.current_count, 0)
