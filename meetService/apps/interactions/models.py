from __future__ import annotations

from enum import member
from django.db import models, transaction

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords

from apps.accounts.models import User
from apps.projects.models import Project, ProjectMembership, ProjectVacancy
from apps.specialists.models import SpecialistProfile


class Application(models.Model):
    """Отклик специалиста на открытую роль в проекте."""

    class Status(models.TextChoices):
        PENDING = "pending", _("На рассмотрении")
        ACCEPTED = "accepted", _("Принят")
        REJECTED = "rejected", _("Отклонён")

    ACTIVE_STATUSES = [
        Status.PENDING,
    ]

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="applications",
        verbose_name=_("проект"),
    )
    vacancy = models.ForeignKey(
        ProjectVacancy,
        on_delete=models.CASCADE,
        related_name="applications",
        verbose_name=_("открытая роль"),
    )
    specialist = models.ForeignKey(
        SpecialistProfile,
        on_delete=models.CASCADE,
        related_name="applications",
        verbose_name=_("специалист"),
    )
    message = models.TextField(
        max_length=1000,
        blank=True,
        validators=[
            MaxLengthValidator(1000),
        ],
        verbose_name=_("комментарий к отклику"),
        help_text=_("Краткий комментарий специалиста к отклику. До 1000 символов."),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_("статус отклика"),
    )
    applied_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("дата отклика"),
    )
    reviewed_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("дата рассмотрения"),
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_applications",
        verbose_name=_("рассмотрел"),
    )

    history = HistoricalRecords(verbose_name=_("история изменений"))

    class Meta:
        verbose_name = _("отклик")
        verbose_name_plural = _("отклики")
        ordering = ["-applied_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "vacancy", "specialist"],
                condition=Q(status="pending"),
                name="unique_active_application_for_vacancy",
            ),
        ]

    def __str__(self) -> str:
        """
        Возвращает строковое представление объекта.
        """
        return f"{self.specialist} → {self.project}"

    def clean(self) -> None:
        """
        Проверяет бизнес-правила отклика.
        """
        errors = {}

        if (
            self.vacancy_id
            and self.project_id
            and self.vacancy.project_id != self.project_id
        ):
            errors["vacancy"] = _(
                "Выбранная открытая роль не относится к указанному проекту."
            )

        if self.project_id and self.specialist_id:
            if self.project.owner_id == self.specialist.user_id:
                errors["project"] = _("Нельзя откликаться на собственный проект.")

        if self.status == self.Status.PENDING:
            if self.project_id and self.specialist_id:
                already_member = ProjectMembership.objects.filter(
                    project=self.project,
                    specialist=self.specialist,
                    status__in=[
                        ProjectMembership.Status.ACTIVE,
                        ProjectMembership.Status.PAUSED,
                    ],
                ).exists()

                if already_member:
                    errors["specialist"] = _(
                        "Специалист уже состоит в команде этого проекта."
                    )

            if self.project_id and self.project.status != Project.Status.PUBLISHED:
                errors["project"] = _("Нельзя откликаться на неопубликованный проект.")

            if self.vacancy_id and not self.vacancy.is_open():
                errors["vacancy"] = _(
                    "Нельзя откликаться на закрытую или заполненную роль."
                )

            duplicate_exists = (
                Application.objects.filter(
                    project=self.project,
                    vacancy=self.vacancy,
                    specialist=self.specialist,
                    status__in=self.ACTIVE_STATUSES,
                )
                .exclude(pk=self.pk)
                .exists()
            )

            if duplicate_exists:
                errors["specialist"] = _(
                    "У специалиста уже есть активный отклик на эту роль."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args: object, **kwargs: object) -> None:
        """
        Перед сохранением очищает сообщение и запускает валидацию.
        Args:
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы
        """
        self.message = self.message.strip()
        self.full_clean()
        super().save(*args, **kwargs)

    def accept(self, reviewed_by: User | None = None) -> ProjectMembership:
        """
        Принимает отклик и добавляет специалиста в команду проекта.
        Args:
            reviewed_by: Пользователь, выполняющий рассмотрение
        """
        with transaction.atomic():
            application = (
                Application.objects.select_for_update()
                .select_related("project", "vacancy", "vacancy__role", "specialist")
                .get(pk=self.pk)
            )

            if application.status != application.Status.PENDING:
                raise ValidationError(_("Можно принять только отклик на рассмотрении."))

            application.project = Project.objects.select_for_update().get(
                pk=application.project_id
            )
            application.vacancy.project = application.project

            if application.project.status != Project.Status.PUBLISHED:
                raise ValidationError(_("Нельзя принять отклик в закрытый проект."))

            if reviewed_by and not application.project.can_be_edited_by(reviewed_by):
                raise ValidationError(
                    _(
                        "Принимать отклики может только владелец проекта или администратор."
                    )
                )

            already_member = ProjectMembership.objects.filter(
                project=application.project,
                specialist=application.specialist,
                status__in=[
                    ProjectMembership.Status.ACTIVE,
                    ProjectMembership.Status.PAUSED,
                ],
            ).first()

            reviewed_at = timezone.now()

            if already_member:
                application.status = Application.Status.ACCEPTED
                application.reviewed_at = reviewed_at
                application.reviewed_by = reviewed_by
                application.save(
                    update_fields=["status", "reviewed_at", "reviewed_by"]
                )

                self.status = Application.Status.ACCEPTED
                self.reviewed_at = reviewed_at
                self.reviewed_by = reviewed_by
                from apps.interactions.emails import enqueue_application_status_email

                enqueue_application_status_email(application.pk)

                return already_member

            membership = application.vacancy.add_specialist(
                specialist=application.specialist,
                added_by=reviewed_by,
            )

            application.status = Application.Status.ACCEPTED
            application.reviewed_at = reviewed_at
            application.reviewed_by = reviewed_by
            application.save(update_fields=["status", "reviewed_at", "reviewed_by"])

            self.status = Application.Status.ACCEPTED
            self.reviewed_at = reviewed_at
            self.reviewed_by = reviewed_by
            from apps.interactions.emails import enqueue_application_status_email

            enqueue_application_status_email(application.pk)

            return membership

    def reject(self, reviewed_by: User | None = None) -> None:
        """
        Отклоняет отклик.
        Args:
            reviewed_by: Пользователь, выполняющий рассмотрение
        """
        with transaction.atomic():
            application = (
                Application.objects.select_for_update()
                .select_related("project")
                .get(pk=self.pk)
            )

            if application.status != application.Status.PENDING:
                raise ValidationError(
                    _("Можно отклонить только отклик на рассмотрении.")
                )

            if reviewed_by and not application.project.can_be_edited_by(reviewed_by):
                raise ValidationError(
                    _(
                        "Отклонять отклики может только владелец проекта или администратор."
                    )
                )

            reviewed_at = timezone.now()

            application.status = Application.Status.REJECTED
            application.reviewed_at = reviewed_at
            application.reviewed_by = reviewed_by
            application.save(update_fields=["status", "reviewed_at", "reviewed_by"])

            self.status = Application.Status.REJECTED
            self.reviewed_at = reviewed_at
            self.reviewed_by = reviewed_by
            from apps.interactions.emails import enqueue_application_status_email

            enqueue_application_status_email(application.pk)


class Invitation(models.Model):
    """Приглашение специалиста в проект."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Ожидает ответа")
        ACCEPTED = "accepted", _("Принято")
        DECLINED = "declined", _("Отклонено")
        EXPIRED = "expired", _("Истекло")

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="invitations",
        verbose_name=_("проект"),
    )
    vacancy = models.ForeignKey(
        ProjectVacancy,
        on_delete=models.CASCADE,
        related_name="invitations",
        verbose_name=_("открытая роль"),
    )
    specialist = models.ForeignKey(
        SpecialistProfile,
        on_delete=models.CASCADE,
        related_name="invitations",
        verbose_name=_("специалист"),
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_invitations",
        verbose_name=_("пригласил"),
    )
    message = models.TextField(
        max_length=1000,
        blank=True,
        validators=[
            MaxLengthValidator(1000),
        ],
        verbose_name=_("текст приглашения"),
        help_text=_(
            "Краткий текст приглашения специалиста в проект. До 1000 символов."
        ),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_("статус приглашения"),
    )
    invited_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("дата приглашения"),
    )
    responded_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("дата ответа"),
    )

    history = HistoricalRecords(verbose_name=_("история изменений"))

    class Meta:
        verbose_name = _("приглашение")
        verbose_name_plural = _("приглашения")
        ordering = ["-invited_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "vacancy", "specialist"],
                condition=Q(status="pending"),
                name="unique_pending_invitation_for_vacancy",
            ),
        ]

    def __str__(self) -> str:
        """
        Возвращает строковое представление объекта.
        """
        return f"{self.project} → {self.specialist}"

    def clean(self) -> None:
        """
        Проверяет бизнес-правила отклика.
        """
        errors = {}

        if (
            self.vacancy_id
            and self.project_id
            and self.vacancy.project_id != self.project_id
        ):
            errors["vacancy"] = _(
                "Выбранная открытая роль не относится к указанному проекту."
            )

        if self.project_id and self.specialist_id:
            if self.project.owner_id == self.specialist.user_id:
                errors["project"] = _("Нельзя откликаться на собственный проект.")

        if self.status == self.Status.PENDING:
            if self.project_id and self.specialist_id:
                already_member = ProjectMembership.objects.filter(
                    project=self.project,
                    specialist=self.specialist,
                    status__in=[
                        ProjectMembership.Status.ACTIVE,
                        ProjectMembership.Status.PAUSED,
                    ],
                ).exists()

                if already_member:
                    errors["specialist"] = _(
                        "Специалист уже состоит в команде этого проекта."
                    )

            if self.specialist_id and not self.specialist.is_available_for_project():
                errors["__all__"] = _(
                    "Приглашать можно только специалиста, открытого к предложениям."
                )

            if self.project_id and self.project.status != Project.Status.PUBLISHED:
                errors["project"] = _("Нельзя откликаться на неопубликованный проект.")

            if self.vacancy_id and not self.vacancy.is_open():
                errors["vacancy"] = _(
                    "Нельзя откликаться на закрытую или заполненную роль."
                )

            duplicate_exists = (
                Invitation.objects.filter(
                    project=self.project,
                    vacancy=self.vacancy,
                    specialist=self.specialist,
                    status=self.Status.PENDING,
                )
                .exclude(pk=self.pk)
                .exists()
            )

            if duplicate_exists:
                errors["specialist"] = _(
                    "У специалиста уже есть активный отклик на эту роль."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args: object, **kwargs: object) -> None:
        """
        Перед сохранением очищает сообщение и запускает валидацию.
        Args:
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы
        """
        self.message = self.message.strip()
        self.full_clean()
        super().save(*args, **kwargs)

    def accept(self) -> ProjectMembership:
        """
        Принимает приглашение и добавляет специалиста в команду проекта.
        """
        with transaction.atomic():
            invitation = (
                Invitation.objects.select_for_update()
                .select_related(
                    "project",
                    "vacancy",
                    "vacancy__role",
                    "specialist",
                    "invited_by",
                )
                .get(pk=self.pk)
            )

            if invitation.status != invitation.Status.PENDING:
                raise ValidationError(
                    _("Можно принять только приглашение со статусом «Ожидает ответа».")
                )

            invitation.project = Project.objects.select_for_update().get(
                pk=invitation.project_id
            )
            invitation.vacancy.project = invitation.project

            if invitation.project.status != Project.Status.PUBLISHED:
                raise ValidationError(_("Нельзя принять приглашение в закрытый проект."))

            already_member = ProjectMembership.objects.filter(
                project=invitation.project,
                specialist=invitation.specialist,
                status__in=[
                    ProjectMembership.Status.ACTIVE,
                    ProjectMembership.Status.PAUSED,
                ],
            ).first()

            if already_member:
                responded_at = timezone.now()

                invitation.status = Invitation.Status.ACCEPTED
                invitation.responded_at = responded_at
                invitation.save(update_fields=["status", "responded_at"])

                self.status = Invitation.Status.ACCEPTED
                self.responded_at = responded_at
                from apps.interactions.emails import enqueue_invitation_status_email

                enqueue_invitation_status_email(invitation.pk)

                return already_member

            if not invitation.vacancy.is_open():
                raise ValidationError(_("Открытая роль уже закрыта или заполнена."))

            membership = invitation.vacancy.add_specialist(
                specialist=invitation.specialist,
                added_by=invitation.invited_by,
            )

            responded_at = timezone.now()

            invitation.status = Invitation.Status.ACCEPTED
            invitation.responded_at = responded_at
            invitation.save(update_fields=["status", "responded_at"])

            self.status = Invitation.Status.ACCEPTED
            self.responded_at = responded_at
            from apps.interactions.emails import enqueue_invitation_status_email

            enqueue_invitation_status_email(invitation.pk)

            return membership

    def decline(self) -> None:
        """
        Отклоняет приглашение.
        """
        with transaction.atomic():
            invitation = Invitation.objects.select_for_update().get(pk=self.pk)

            if invitation.status != self.Status.PENDING:
                raise ValidationError(
                    _("Можно отклонить только приглашение со статусом «Ожидает ответа».")
                )

            responded_at = timezone.now()
            invitation.status = Invitation.Status.DECLINED
            invitation.responded_at = responded_at
            invitation.save(update_fields=["status", "responded_at"])

        self.status = invitation.status
        self.responded_at = invitation.responded_at
        from apps.interactions.emails import enqueue_invitation_status_email

        enqueue_invitation_status_email(self.pk)


class FavoriteProject(models.Model):
    """Избранный проект пользователя."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorite_projects",
        verbose_name=_("пользователь"),
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="favorited_by",
        verbose_name=_("проект"),
    )
    added_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("дата добавления"),
    )

    class Meta:
        verbose_name = _("избранный проект")
        verbose_name_plural = _("избранные проекты")
        ordering = ["-added_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "project"],
                name="unique_favorite_project",
            ),
        ]

    def __str__(self) -> str:
        """
        Возвращает строковое представление объекта.
        """
        return f"{self.user} добавил «{self.project}» в избранное"
