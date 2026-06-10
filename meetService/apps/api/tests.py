from __future__ import annotations

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from apps.directories.models import Role, Technology
from apps.interactions.models import Application, FavoriteProject, Invitation
from apps.projects.models import (
    Project,
    ProjectMembership,
    ProjectTechnology,
    ProjectVacancy,
)
from apps.specialists.models import SpecialistProfile


User = get_user_model()


class NewMakersApiTests(APITestCase):
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
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="password",
            is_staff=True,
        )
        self.role = Role.objects.create(
            name="Backend-разработчик",
            slug="backend-developer",
        )
        self.technology = Technology.objects.create(
            name="Django",
            slug="django",
            category=Technology.TechnologyCategory.FRAMEWORK,
        )
        self.specialist = SpecialistProfile.objects.create(
            user=self.specialist_user,
            main_role=self.role,
            bio="Backend-разработчик, готовый участвовать в проектной команде.",
            status=SpecialistProfile.AvailabilityStatus.LOOKING,
        )
        self.project = Project.objects.create(
            owner=self.owner,
            title="New-Makers API",
            short_description="API для поиска проектных команд.",
            description="Подробное описание проекта для API-тестов.",
            goal="Проверить публичные и ролевые сценарии API.",
            status=Project.Status.PUBLISHED,
        )
        ProjectTechnology.objects.create(
            project=self.project,
            technology=self.technology,
        )
        self.vacancy = ProjectVacancy.objects.create(
            project=self.project,
            role=self.role,
            title="Backend",
            description="Нужен backend-разработчик.",
            required_count=2,
        )

    def response_results(self, response: Response) -> list[dict[str, object]]:
        """
        Выполняет логику функции.
        Args:
            response: Значение параметра `response`
        """
        return response.data.get("results", response.data)

    def test_public_project_list_shows_published_projects_only(self) -> None:
        """
        Проверяет сценарий `test_public_project_list_shows_published_projects_only`.
        """
        Project.objects.create(
            owner=self.owner,
            title="Draft API",
            short_description="Черновик проекта.",
            description="Подробное описание черновика.",
            goal="Не попасть в публичный API.",
            status=Project.Status.DRAFT,
        )

        response = self.client.get(reverse("api:project-list"))
        titles = {project["title"] for project in self.response_results(response)}

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.project.title, titles)
        self.assertNotIn("Draft API", titles)

    def test_project_filter_by_technology_and_open_vacancies(self) -> None:
        """
        Проверяет сценарий `test_project_filter_by_technology_and_open_vacancies`.
        """
        response = self.client.get(
            reverse("api:project-list"),
            {
                "technology": self.technology.slug,
                "has_open_vacancies": "true",
            },
        )

        results = self.response_results(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], self.project.id)

    def test_project_serializer_uses_request_context_for_user_fields(self) -> None:
        """
        Проверяет сценарий `test_project_serializer_uses_request_context_for_user_fields`.
        """
        FavoriteProject.objects.create(user=self.specialist_user, project=self.project)
        self.client.force_authenticate(self.specialist_user)

        response = self.client.get(
            reverse("api:project-detail", kwargs={"pk": self.project.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_favorite"])
        self.assertTrue(response.data["can_apply"])
        self.assertFalse(response.data["can_manage"])

    def test_specialist_can_create_application(self) -> None:
        """
        Проверяет сценарий `test_specialist_can_create_application`.
        """
        self.client.force_authenticate(self.specialist_user)

        response = self.client.post(
            reverse("api:application-list"),
            {
                "vacancy": self.vacancy.pk,
                "message": "Хочу присоединиться к команде проекта.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Application.objects.filter(
                vacancy=self.vacancy,
                specialist=self.specialist,
            ).exists()
        )

    def test_owner_can_accept_application(self) -> None:
        """
        Проверяет сценарий `test_owner_can_accept_application`.
        """
        application = Application.objects.create(
            project=self.project,
            vacancy=self.vacancy,
            specialist=self.specialist,
            message="Готов участвовать.",
        )
        self.client.force_authenticate(self.owner)

        response = self.client.post(
            reverse("api:application-accept", kwargs={"pk": application.pk}),
            format="json",
        )
        application.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(application.status, Application.Status.ACCEPTED)
        self.assertTrue(
            ProjectMembership.objects.filter(
                project=self.project,
                specialist=self.specialist,
                status=ProjectMembership.Status.ACTIVE,
            ).exists()
        )

    def test_project_owner_can_create_vacancy_via_nested_endpoint(self) -> None:
        """
        Проверяет сценарий `test_project_owner_can_create_vacancy_via_nested_endpoint`.
        """
        self.client.force_authenticate(self.owner)

        response = self.client.post(
            reverse("api:project-vacancies", kwargs={"pk": self.project.pk}),
            {
                "role": self.role.pk,
                "title": "QA",
                "description": "Нужен специалист по тестированию.",
                "required_level": SpecialistProfile.Level.JUNIOR,
                "required_count": 1,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            ProjectVacancy.objects.filter(project=self.project, title="QA").exists()
        )

    def test_non_owner_cannot_create_project_vacancy(self) -> None:
        """
        Проверяет сценарий `test_non_owner_cannot_create_project_vacancy`.
        """
        self.client.force_authenticate(self.specialist_user)

        response = self.client.post(
            reverse("api:project-vacancies", kwargs={"pk": self.project.pk}),
            {
                "role": self.role.pk,
                "title": "QA",
                "description": "Нужен специалист по тестированию.",
                "required_level": SpecialistProfile.Level.JUNIOR,
                "required_count": 1,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_cannot_move_vacancy_to_another_project(self) -> None:
        """Проверяет неизменяемость проекта существующей вакансии."""
        other_owner = User.objects.create_user(
            username="other-owner",
            email="other-owner@example.com",
            password="password",
        )
        other_project = Project.objects.create(
            owner=other_owner,
            title="Other project",
            short_description="Чужой проект.",
            description="Подробное описание чужого проекта.",
            goal="Проверить запрет переноса вакансии.",
            status=Project.Status.PUBLISHED,
        )
        self.client.force_authenticate(self.owner)

        response = self.client.patch(
            reverse("api:vacancy-detail", kwargs={"pk": self.vacancy.pk}),
            {"project": other_project.pk},
            format="json",
        )
        self.vacancy.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.vacancy.project, self.project)
        self.assertIn("project", response.data)

    def test_owner_cannot_invite_hidden_specialist_via_api(self) -> None:
        """Проверяет запрет API-приглашения скрытого специалиста."""
        self.specialist.status = SpecialistProfile.AvailabilityStatus.HIDDEN
        self.specialist.save(update_fields=["status", "updated_at"])
        self.client.force_authenticate(self.owner)

        response = self.client.post(
            reverse("api:invitation-list"),
            {
                "vacancy": self.vacancy.pk,
                "specialist": self.specialist.pk,
                "message": "Приглашаем в проект.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Invitation.objects.exists())

    def test_invitation_response_does_not_expose_specialist_contacts(self) -> None:
        """Проверяет сокращённые данные специалиста в ответе приглашения."""
        self.specialist.telegram = "private_contact"
        self.specialist.save(update_fields=["telegram", "updated_at"])
        self.client.force_authenticate(self.owner)

        response = self.client.post(
            reverse("api:invitation-list"),
            {
                "vacancy": self.vacancy.pk,
                "specialist": self.specialist.pk,
                "message": "Приглашаем в проект.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("telegram", response.data["specialist_detail"])
        self.assertNotIn("github_url", response.data["specialist_detail"])

    def test_get_specialists_me_does_not_create_profile(self) -> None:
        user = User.objects.create_user(username="without-profile", password="password")
        self.client.force_authenticate(user)

        response = self.client.get(reverse("api:specialist-me"))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(SpecialistProfile.objects.filter(user=user).exists())

    def test_api_profile_requires_main_role_and_technology(self) -> None:
        user = User.objects.create_user(username="new-specialist", password="password")
        self.client.force_authenticate(user)

        response = self.client.post(
            reverse("api:specialist-list"),
            {"bio": "Полное описание нового специалиста."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("main_role", response.data)
        self.assertIn("technology_ids", response.data)

    def test_api_reopens_vacancy_when_limit_is_increased(self) -> None:
        self.vacancy.current_count = 1
        self.vacancy.required_count = 1
        self.vacancy.status = ProjectVacancy.Status.CLOSED
        self.vacancy.save()
        self.client.force_authenticate(self.owner)

        response = self.client.patch(
            reverse("api:vacancy-detail", kwargs={"pk": self.vacancy.pk}),
            {"required_count": 2, "status": ProjectVacancy.Status.OPEN},
            format="json",
        )
        self.vacancy.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.vacancy.status, ProjectVacancy.Status.OPEN)
        self.assertEqual(self.vacancy.required_count, 2)

    def test_api_rejects_inactive_role_for_new_vacancy(self) -> None:
        inactive_role = Role.objects.create(
            name="Отключённая роль",
            slug="inactive-role",
            is_active=False,
        )
        self.client.force_authenticate(self.owner)

        response = self.client.post(
            reverse("api:project-vacancies", kwargs={"pk": self.project.pk}),
            {
                "role": inactive_role.pk,
                "title": "Недоступная роль",
                "description": "Роль не должна назначаться через API.",
                "required_count": 1,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role", response.data)
