from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.directories.models import Role
from apps.interactions.models import Application, Invitation
from apps.interactions.tasks import (
    expire_stale_invitations,
    send_application_created_email,
    send_application_status_email,
    send_invitation_created_email,
    send_pending_application_digest,
    send_pending_application_digest_email,
    send_pending_invitation_digest,
    send_pending_invitation_digest_email,
    send_welcome_email,
)
from apps.projects.models import Project, ProjectVacancy
from apps.specialists.models import SpecialistProfile


User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="New-Makers <noreply@new-makers.local>",
    INVITATION_EXPIRE_DAYS=14,
    SITE_URL="http://127.0.0.1:8000",
)
class InteractionTaskTests(TestCase):
    """Тесты фоновых задач откликов и приглашений."""

    def setUp(self) -> None:
        """
        Подготавливает пользователей, проект и открытую роль.
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
            bio="Готов участвовать в проектах.",
        )
        self.role = Role.objects.create(
            name="Backend-разработчик",
            slug="backend-developer",
        )
        self.project = Project.objects.create(
            owner=self.owner,
            title="Сервис команд",
            short_description="Поиск участников.",
            description="Подробное описание проекта.",
            goal="Собрать команду.",
            status=Project.Status.PUBLISHED,
        )
        self.vacancy = ProjectVacancy.objects.create(
            project=self.project,
            role=self.role,
            title="Backend",
            description="Нужен backend-разработчик.",
            required_count=2,
        )

    def create_invitation(self, *, invited_at: object | None = None) -> Invitation:
        """
        Создает приглашение и при необходимости меняет дату отправки.
        Args:
            invited_at: Дата отправки приглашения
        """
        invitation = Invitation.objects.create(
            project=self.project,
            vacancy=self.vacancy,
            specialist=self.specialist,
            invited_by=self.owner,
            message="Приглашаем в проект.",
        )

        if invited_at is not None:
            Invitation.objects.filter(pk=invitation.pk).update(invited_at=invited_at)
            invitation.refresh_from_db()

        return invitation

    def test_expire_stale_invitations_marks_old_pending_invitation(self) -> None:
        """
        Проверяет, что старое ожидающее приглашение становится истекшим.
        """
        invitation = self.create_invitation(
            invited_at=timezone.now() - timedelta(days=20)
        )
        history_count = invitation.history.count()

        updated_count = expire_stale_invitations(invitation_lifetime_days=14)
        invitation.refresh_from_db()

        self.assertEqual(updated_count, 1)
        self.assertEqual(invitation.status, Invitation.Status.EXPIRED)
        self.assertIsNotNone(invitation.responded_at)
        self.assertGreater(invitation.history.count(), history_count)

    def test_expire_stale_invitations_keeps_recent_pending_invitation(self) -> None:
        """
        Проверяет, что свежее ожидающее приглашение не истекает.
        """
        invitation = self.create_invitation(
            invited_at=timezone.now() - timedelta(days=3)
        )

        updated_count = expire_stale_invitations(invitation_lifetime_days=14)
        invitation.refresh_from_db()

        self.assertEqual(updated_count, 0)
        self.assertEqual(invitation.status, Invitation.Status.PENDING)

    def test_expire_stale_invitations_ignores_accepted_invitation(self) -> None:
        """
        Проверяет, что принятое приглашение не переводится в истекшие.
        """
        invitation = self.create_invitation(
            invited_at=timezone.now() - timedelta(days=20)
        )
        Invitation.objects.filter(pk=invitation.pk).update(
            status=Invitation.Status.ACCEPTED
        )

        updated_count = expire_stale_invitations(invitation_lifetime_days=14)
        invitation.refresh_from_db()

        self.assertEqual(updated_count, 0)
        self.assertEqual(invitation.status, Invitation.Status.ACCEPTED)

    def test_pending_application_digest_sends_email_to_project_owner(self) -> None:
        """
        Проверяет отправку письма владельцу проекта по ожидающему отклику.
        """
        Application.objects.create(
            project=self.project,
            vacancy=self.vacancy,
            specialist=self.specialist,
            message="Хочу участвовать.",
        )

        with patch(
            "apps.interactions.tasks.send_pending_application_digest_email.delay"
        ) as delay:
            queued_count = send_pending_application_digest()

        self.assertEqual(queued_count, 1)
        delay.assert_called_once_with(self.owner.pk, 1)

        sent_count = send_pending_application_digest_email(self.owner.pk, 1)
        self.assertEqual(sent_count, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["owner@example.com"])
        self.assertIn("1 отклик на рассмотрении", mail.outbox[0].body)

    def test_pending_application_digest_skips_owner_without_email(self) -> None:
        """
        Проверяет, что сводка не отправляется владельцу без email.
        """
        self.owner.email = ""
        self.owner.save(update_fields=["email"])
        Application.objects.create(
            project=self.project,
            vacancy=self.vacancy,
            specialist=self.specialist,
            message="Хочу участвовать.",
        )

        sent_count = send_pending_application_digest()

        self.assertEqual(sent_count, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_pending_invitation_digest_sends_email_to_specialist(self) -> None:
        """
        Проверяет отправку письма специалисту по ожидающему приглашению.
        """
        self.create_invitation()

        with patch(
            "apps.interactions.tasks.send_pending_invitation_digest_email.delay"
        ) as delay:
            queued_count = send_pending_invitation_digest()

        self.assertEqual(queued_count, 1)
        delay.assert_called_once_with(self.specialist_user.pk, 1)

        sent_count = send_pending_invitation_digest_email(
            self.specialist_user.pk,
            1,
        )
        self.assertEqual(sent_count, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["specialist@example.com"])
        self.assertIn("1 приглашение в проект", mail.outbox[0].body)

    def test_welcome_email_uses_html_template(self) -> None:
        """
        Проверяет HTML-верстку приветственного письма.
        """
        sent_count = send_welcome_email(self.specialist_user.pk)

        self.assertEqual(sent_count, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["specialist@example.com"])
        self.assertIn("Добро пожаловать в New-Makers", mail.outbox[0].subject)
        self.assertIn("Открыть профиль", mail.outbox[0].alternatives[0].content)

    def test_application_created_email_uses_project_context(self) -> None:
        """
        Проверяет письмо владельцу проекта о новом отклике.
        """
        application = Application.objects.create(
            project=self.project,
            vacancy=self.vacancy,
            specialist=self.specialist,
            message="Хочу присоединиться к команде.",
        )

        sent_count = send_application_created_email(application.pk)

        self.assertEqual(sent_count, 1)
        self.assertEqual(mail.outbox[0].to, ["owner@example.com"])
        self.assertIn("Новый отклик", mail.outbox[0].alternatives[0].content)
        self.assertIn(self.project.title, mail.outbox[0].alternatives[0].content)

    def test_application_status_email_uses_status_context(self) -> None:
        """
        Проверяет письмо специалисту о принятом отклике.
        """
        application = Application.objects.create(
            project=self.project,
            vacancy=self.vacancy,
            specialist=self.specialist,
            message="Хочу присоединиться к команде.",
        )
        Application.objects.filter(pk=application.pk).update(
            status=Application.Status.ACCEPTED
        )

        sent_count = send_application_status_email(application.pk)

        self.assertEqual(sent_count, 1)
        self.assertEqual(mail.outbox[0].to, ["specialist@example.com"])
        self.assertIn("Отклик принят", mail.outbox[0].subject)

    def test_invitation_created_email_uses_project_context(self) -> None:
        """
        Проверяет письмо специалисту о новом приглашении.
        """
        invitation = self.create_invitation()

        sent_count = send_invitation_created_email(invitation.pk)

        self.assertEqual(sent_count, 1)
        self.assertEqual(mail.outbox[0].to, ["specialist@example.com"])
        self.assertIn("Новое приглашение", mail.outbox[0].alternatives[0].content)
        self.assertIn(self.project.title, mail.outbox[0].alternatives[0].content)
