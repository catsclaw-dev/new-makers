from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.directories.models import Role
from apps.projects.models import Project, ProjectMembership, ProjectVacancy
from apps.specialists.models import SpecialistProfile


User = get_user_model()


class ProjectBusinessTests(TestCase):
    def setUp(self) -> None:
        """
        Подготавливает тестовые данные.
        """
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="password",
        )
        self.other_user = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="password",
        )
        self.specialist_user = User.objects.create_user(
            username="specialist",
            email="specialist@example.com",
            password="password",
        )
        self.role = Role.objects.create(
            name="Backend-разработчик",
            slug="backend-developer",
        )
        self.specialist = SpecialistProfile.objects.create(
            user=self.specialist_user,
            bio="Специалист для проверки повторного участия.",
        )

    def create_project(self, **kwargs: object) -> object:
        """
        Создает связанные данные приложения.
        Args:
            **kwargs: Именованные аргументы
        """
        defaults = {
            "owner": self.owner,
            "title": "Командный сервис",
            "short_description": "Сервис поиска команды",
            "description": "Подробное описание проекта для теста.",
            "goal": "Собрать команду и запустить MVP.",
        }
        defaults.update(kwargs)
        return Project.objects.create(**defaults)

    def test_vacancy_closes_when_required_count_reached(self) -> None:
        """
        Проверяет сценарий `test_vacancy_closes_when_required_count_reached`.
        """
        project = self.create_project(status=Project.Status.PUBLISHED)

        vacancy = ProjectVacancy.objects.create(
            project=project,
            role=self.role,
            title="Backend",
            description="Нужен backend-разработчик.",
            required_count=1,
            current_count=1,
        )

        self.assertEqual(vacancy.status, ProjectVacancy.Status.CLOSED)

    def test_project_open_vacancy_annotation_counts_only_open_roles(self) -> None:
        """
        Проверяет сценарий `test_project_open_vacancy_annotation_counts_only_open_roles`.
        """
        project = self.create_project(status=Project.Status.PUBLISHED)
        ProjectVacancy.objects.create(
            project=project,
            role=self.role,
            title="Open Backend",
            description="Открытая роль.",
            required_count=2,
            current_count=0,
        )
        ProjectVacancy.objects.create(
            project=project,
            role=self.role,
            title="Filled Backend",
            description="Закрытая роль.",
            required_count=1,
            current_count=1,
        )

        annotated_project = Project.objects.with_open_vacancy_count().get(pk=project.pk)

        self.assertEqual(annotated_project.open_vacancy_count, 1)

    def test_draft_project_is_visible_to_owner_only(self) -> None:
        """
        Проверяет сценарий `test_draft_project_is_visible_to_owner_only`.
        """
        project = self.create_project(status=Project.Status.DRAFT)
        url = reverse("projects:project_detail", kwargs={"slug": project.slug})

        self.client.force_login(self.other_user)
        other_response = self.client.get(url)

        self.client.force_login(self.owner)
        owner_response = self.client.get(url)

        self.assertEqual(other_response.status_code, 404)
        self.assertEqual(owner_response.status_code, 200)

    def test_specialist_can_be_added_again_after_left_membership(self) -> None:
        """
        Проверяет повторное добавление специалиста после выхода из проекта.
        """
        project = self.create_project(status=Project.Status.PUBLISHED)
        ProjectMembership.objects.create(
            project=project,
            specialist=self.specialist,
            role=self.role,
            status=ProjectMembership.Status.LEFT,
        )

        membership = ProjectMembership.objects.create(
            project=project,
            specialist=self.specialist,
            role=self.role,
            status=ProjectMembership.Status.ACTIVE,
        )

        self.assertEqual(membership.status, ProjectMembership.Status.ACTIVE)

    def test_specialist_cannot_have_duplicate_active_membership(self) -> None:
        """
        Проверяет запрет двух активных участий в одной роли проекта.
        """
        project = self.create_project(status=Project.Status.PUBLISHED)
        ProjectMembership.objects.create(
            project=project,
            specialist=self.specialist,
            role=self.role,
            status=ProjectMembership.Status.ACTIVE,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            ProjectMembership.objects.create(
                project=project,
                specialist=self.specialist,
                role=self.role,
                status=ProjectMembership.Status.ACTIVE,
            )
