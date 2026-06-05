from __future__ import annotations

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from apps.directories.models import Role, Technology
from apps.interactions.models import Application, FavoriteProject
from apps.projects.models import Project, ProjectMembership, ProjectTechnology, ProjectVacancy
from apps.reviews.models import Review
from apps.specialists.models import SpecialistProfile


User = get_user_model()


class MeetServiceApiTests(APITestCase):
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
            title="MeetService API",
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

    def test_user_cannot_update_another_author_review(self) -> None:
        """
        Проверяет запрет редактирования чужого опубликованного отзыва.
        """
        ProjectMembership.objects.create(
            project=self.project,
            specialist=self.specialist,
            role=self.role,
            added_by=self.owner,
        )
        review = Review.objects.create(
            project=self.project,
            author=self.owner,
            specialist=self.specialist,
            rating=5,
            text="Специалист хорошо показал себя в проекте.",
            status=Review.Status.PUBLISHED,
        )
        self.client.force_authenticate(self.specialist_user)

        response = self.client.patch(
            reverse("api:review-detail", kwargs={"pk": review.pk}),
            {"text": "Пытаюсь изменить чужой отзыв."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_review_author_can_update_own_review(self) -> None:
        """
        Проверяет редактирование собственного отзыва.
        """
        ProjectMembership.objects.create(
            project=self.project,
            specialist=self.specialist,
            role=self.role,
            added_by=self.owner,
        )
        review = Review.objects.create(
            project=self.project,
            author=self.owner,
            specialist=self.specialist,
            rating=5,
            text="Специалист хорошо показал себя в проекте.",
            status=Review.Status.PUBLISHED,
        )
        self.client.force_authenticate(self.owner)

        response = self.client.patch(
            reverse("api:review-detail", kwargs={"pk": review.pk}),
            {"text": "Обновленный текст собственного отзыва."},
            format="json",
        )
        review.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(review.text, "Обновленный текст собственного отзыва.")

    def test_admin_can_delete_any_review(self) -> None:
        """
        Проверяет удаление любого отзыва администратором.
        """
        ProjectMembership.objects.create(
            project=self.project,
            specialist=self.specialist,
            role=self.role,
            added_by=self.owner,
        )
        review = Review.objects.create(
            project=self.project,
            author=self.owner,
            specialist=self.specialist,
            rating=5,
            text="Специалист хорошо показал себя в проекте.",
            status=Review.Status.PUBLISHED,
        )
        self.client.force_authenticate(self.admin)

        response = self.client.delete(
            reverse("api:review-detail", kwargs={"pk": review.pk}),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Review.objects.filter(pk=review.pk).exists())
