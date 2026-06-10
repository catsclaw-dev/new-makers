from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.directories.models import Role
from apps.common_validators import validate_project_file
from apps.interactions.models import Application, Invitation
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

        with self.assertRaises(ValidationError):
            ProjectMembership.objects.create(
                project=project,
                specialist=self.specialist,
                role=self.role,
                status=ProjectMembership.Status.ACTIVE,
            )

    def test_membership_rejects_vacancy_from_another_project(self) -> None:
        """Проверяет согласованность проекта membership и вакансии."""
        project = self.create_project(status=Project.Status.PUBLISHED)
        other_project = self.create_project(
            title="Другой проект",
            status=Project.Status.PUBLISHED,
        )
        vacancy = ProjectVacancy.objects.create(
            project=other_project,
            role=self.role,
            title="Backend",
            description="Роль другого проекта.",
        )

        with self.assertRaises(ValidationError):
            ProjectMembership.objects.create(
                project=project,
                specialist=self.specialist,
                vacancy=vacancy,
                role=self.role,
            )

    def test_membership_rejects_role_mismatch(self) -> None:
        """Проверяет согласованность роли membership и вакансии."""
        project = self.create_project(status=Project.Status.PUBLISHED)
        other_role = Role.objects.create(name="QA", slug="qa")
        vacancy = ProjectVacancy.objects.create(
            project=project,
            role=other_role,
            title="QA",
            description="Нужен тестировщик.",
        )

        with self.assertRaises(ValidationError):
            ProjectMembership.objects.create(
                project=project,
                specialist=self.specialist,
                vacancy=vacancy,
                role=self.role,
            )

    def test_membership_normalizes_left_at(self) -> None:
        """Проверяет согласованность даты выхода со статусом membership."""
        project = self.create_project(status=Project.Status.PUBLISHED)
        membership = ProjectMembership.objects.create(
            project=project,
            specialist=self.specialist,
            role=self.role,
            status=ProjectMembership.Status.LEFT,
        )

        self.assertIsNotNone(membership.left_at)

        membership.status = ProjectMembership.Status.ACTIVE
        membership.save()

        self.assertIsNone(membership.left_at)

    def test_failed_membership_move_keeps_original_vacancy(self) -> None:
        """Проверяет атомарность перемещения в заполненную вакансию."""
        project = self.create_project(status=Project.Status.PUBLISHED)
        old_vacancy = ProjectVacancy.objects.create(
            project=project,
            role=self.role,
            title="Backend A",
            description="Исходная роль.",
            required_count=2,
        )
        full_vacancy = ProjectVacancy.objects.create(
            project=project,
            role=self.role,
            title="Backend B",
            description="Заполненная роль.",
            required_count=1,
        )
        membership = old_vacancy.add_specialist(
            specialist=self.specialist,
            added_by=self.owner,
        )
        second_user = User.objects.create_user(username="second", password="password")
        second_specialist = SpecialistProfile.objects.create(user=second_user)
        full_vacancy.add_specialist(
            specialist=second_specialist,
            added_by=self.owner,
        )

        with self.assertRaises(ValidationError):
            membership.move_to(
                vacancy=full_vacancy,
                status=ProjectMembership.Status.ACTIVE,
            )

        membership.refresh_from_db()
        old_vacancy.refresh_from_db()
        full_vacancy.refresh_from_db()
        self.assertEqual(membership.vacancy, old_vacancy)
        self.assertEqual(old_vacancy.current_count, 1)
        self.assertEqual(full_vacancy.current_count, 1)

    def test_archive_closes_pending_interactions_with_history(self) -> None:
        project = self.create_project(status=Project.Status.PUBLISHED)
        vacancy = ProjectVacancy.objects.create(
            project=project,
            role=self.role,
            title="Backend",
            description="Открытая роль.",
            required_count=2,
        )
        application = Application.objects.create(
            project=project,
            vacancy=vacancy,
            specialist=self.specialist,
        )
        invitation = Invitation.objects.create(
            project=project,
            vacancy=vacancy,
            specialist=self.specialist,
            invited_by=self.owner,
        )
        application_history_count = application.history.count()
        invitation_history_count = invitation.history.count()

        project.archive(archived_by=self.owner)
        application.refresh_from_db()
        invitation.refresh_from_db()
        vacancy.refresh_from_db()

        self.assertEqual(application.status, Application.Status.REJECTED)
        self.assertEqual(invitation.status, Invitation.Status.EXPIRED)
        self.assertEqual(vacancy.status, ProjectVacancy.Status.CLOSED)
        self.assertGreater(application.history.count(), application_history_count)
        self.assertGreater(invitation.history.count(), invitation_history_count)

    def test_project_file_rejects_fake_pdf(self) -> None:
        uploaded = SimpleUploadedFile(
            "document.pdf",
            b"not a pdf",
            content_type="application/pdf",
        )

        with self.assertRaises(ValidationError):
            validate_project_file(uploaded)
