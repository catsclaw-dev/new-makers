from __future__ import annotations

from pathlib import Path

import yaml
from django.conf import settings
from django.test import SimpleTestCase
from django.urls import reverse


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class DeployConfigurationTests(SimpleTestCase):
    """Тесты конфигурации деплоя, OAuth2 и фоновых сервисов."""

    def test_google_oauth_provider_is_configured(self) -> None:
        """
        Проверяет подключение Google OAuth2 через django-allauth.
        """
        self.assertIn("allauth.socialaccount.providers.google", settings.INSTALLED_APPS)
        self.assertIn(
            "allauth.account.auth_backends.AuthenticationBackend",
            settings.AUTHENTICATION_BACKENDS,
        )
        self.assertEqual(
            settings.SOCIALACCOUNT_ADAPTER,
            "apps.accounts.adapters.MeetServiceSocialAccountAdapter",
        )

    def test_github_oauth_provider_is_configured(self) -> None:
        """
        Проверяет подключение GitHub OAuth2 через django-allauth.
        """
        self.assertIn("allauth.socialaccount.providers.github", settings.INSTALLED_APPS)
        self.assertIn("github", settings.SOCIALACCOUNT_PROVIDERS)

    def test_google_login_url_is_registered(self) -> None:
        """
        Проверяет регистрацию маршрута входа через Google.
        """
        self.assertEqual(reverse("google_login"), "/oauth/google/login/")

    def test_github_login_url_is_registered(self) -> None:
        """
        Проверяет регистрацию маршрута входа через GitHub.
        """
        self.assertEqual(reverse("github_login"), "/oauth/github/login/")

    def test_celery_periodic_tasks_are_registered(self) -> None:
        """
        Проверяет регистрацию периодических задач Celery Beat.
        """
        task_names = {
            task_config["task"]
            for task_config in settings.CELERY_BEAT_SCHEDULE.values()
        }

        self.assertIn(
            "apps.interactions.tasks.expire_stale_invitations",
            task_names,
        )
        self.assertIn(
            "apps.projects.tasks.sync_project_vacancy_counts",
            task_names,
        )

    def test_docker_compose_uses_sqlite_without_postgres_service(self) -> None:
        """
        Проверяет, что Docker-конфигурация оставляет SQLite основной базой.
        """
        compose = yaml.safe_load((PROJECT_ROOT / "docker-compose.yml").read_text())
        services = compose["services"]

        self.assertNotIn("postgres", services)
        self.assertIn("sqlite:", services["web"]["environment"]["DATABASE_URL"])

    def test_docker_compose_contains_rabbitmq_redis_mailhog_and_celery(self) -> None:
        """
        Проверяет наличие RabbitMQ, Redis, Mailhog, Celery worker и Celery Beat.
        """
        compose = yaml.safe_load((PROJECT_ROOT / "docker-compose.yml").read_text())
        services = compose["services"]

        self.assertIn("rabbitmq", services)
        self.assertIn("redis", services)
        self.assertIn("mailhog", services)
        self.assertIn("celery_worker", services)
        self.assertIn("celery_beat", services)
        self.assertEqual(services["mailhog"]["ports"], ["1025:1025", "8025:8025"])

    def test_rabbitmq_has_management_ui_healthcheck_and_persistent_data(self) -> None:
        """
        Проверяет management UI, healthcheck и volume RabbitMQ.
        """
        compose = yaml.safe_load((PROJECT_ROOT / "docker-compose.yml").read_text())
        rabbitmq = compose["services"]["rabbitmq"]

        self.assertEqual(rabbitmq["image"], "rabbitmq:4.2-management-alpine")
        self.assertEqual(rabbitmq["ports"], ["5672:5672", "15672:15672"])
        self.assertIn("healthcheck", rabbitmq)
        self.assertIn("rabbitmq_data:/var/lib/rabbitmq", rabbitmq["volumes"])
        self.assertIn("rabbitmq_data", compose["volumes"])

    def test_celery_uses_rabbitmq_broker_and_redis_result_backend(self) -> None:
        """
        Проверяет разделение broker и result backend Celery.
        """
        compose = yaml.safe_load((PROJECT_ROOT / "docker-compose.yml").read_text())

        for service_name in ("web", "celery_worker", "celery_beat"):
            environment = compose["services"][service_name]["environment"]
            self.assertIn("amqp://", environment["CELERY_BROKER_URL"])
            self.assertIn("rabbitmq:5672", environment["CELERY_BROKER_URL"])
            self.assertIn("redis://redis:6379/0", environment["CELERY_RESULT_BACKEND"])

        for service_name in ("celery_worker", "celery_beat"):
            rabbitmq_dependency = compose["services"][service_name]["depends_on"][
                "rabbitmq"
            ]
            self.assertEqual(rabbitmq_dependency["condition"], "service_healthy")

    def test_env_example_contains_rabbitmq_and_redis_celery_urls(self) -> None:
        """
        Проверяет переменные RabbitMQ и Redis в шаблоне окружения.
        """
        env_example = (PROJECT_ROOT / ".env.example").read_text()

        self.assertIn("RABBITMQ_DEFAULT_USER=", env_example)
        self.assertIn("RABBITMQ_DEFAULT_PASS=", env_example)
        self.assertIn("CELERY_BROKER_URL=amqp://", env_example)
        self.assertIn("@rabbitmq:5672//", env_example)
        self.assertIn("CELERY_RESULT_BACKEND=redis://redis:6379/0", env_example)

    def test_celery_queues_are_compatible_with_rabbitmq_4_3(self) -> None:
        """
        Проверяет exclusive-очереди Celery для совместимости с RabbitMQ 4.3.
        """
        self.assertTrue(settings.CELERY_CONTROL_QUEUE_EXCLUSIVE)
        self.assertTrue(settings.CELERY_EVENT_QUEUE_EXCLUSIVE)

    def test_requirements_keep_psycopg_as_optional_deploy_dependency(self) -> None:
        """
        Проверяет наличие psycopg без обязательного сервиса PostgreSQL.
        """
        requirements = (PROJECT_ROOT / "requirements.txt").read_text()

        self.assertTrue(
            "psycopg[binary]" in requirements
            or (
                "psycopg==" in requirements
                and "psycopg-binary==" in requirements
            )
        )
        self.assertIn("django-allauth", requirements)
        self.assertTrue(
            "celery[redis]" in requirements
            or ("celery==" in requirements and "redis==" in requirements)
        )
        self.assertIn("amqp==", requirements)

    def test_dockerignore_excludes_env_files(self) -> None:
        """
        Проверяет, что секреты из .env не попадают в Docker image.
        """
        dockerignore = (PROJECT_ROOT / ".dockerignore").read_text()

        self.assertIn(".env", dockerignore)
        self.assertIn(".env.*", dockerignore)
        self.assertIn("!.env.example", dockerignore)

    def test_media_files_are_served_from_absolute_url(self) -> None:
        """
        Проверяет абсолютный URL для пользовательских файлов.
        """
        self.assertEqual(settings.MEDIA_URL, "/media/")
        self.assertEqual(settings.STATIC_URL, "/static/")

    def test_docker_compose_mounts_host_media_directory(self) -> None:
        """
        Проверяет подключение локальной папки media в контейнер.
        """
        compose = yaml.safe_load((PROJECT_ROOT / "docker-compose.yml").read_text())
        web_volumes = compose["services"]["web"]["volumes"]

        self.assertIn("./meetService/media:/app/meetService/media", web_volumes)
