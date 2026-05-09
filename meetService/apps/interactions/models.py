from enum import member
from django.db import models, transaction

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords

from apps.projects.models import Project, ProjectMembership, ProjectVacancy
from apps.specialists.models import SpecialistProfile


class Application(models.Model):
    """Отклик специалиста на открытую роль в проекте."""

    class Status(models.TextChoices):
        PENDING = "pending", _("На рассмотрении")
        ACCEPTED = "accepted", _("Принят")
        REJECTED = "rejected", _("Отклонён")
        CANCELLED = "cancelled", _("Отменён")

    ACTIVE_STATUSES = [
        Status.PENDING,
        Status.ACCEPTED,
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
        blank=True,
        verbose_name=_("сообщение"),
        help_text=_("Сопроводительное сообщение специалиста владельцу проекта."),
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
                condition=Q(status__in=["pending", "accepted"]),
                name="unique_active_application_for_vacancy",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.specialist} → {self.project}"

    def clean(self):
        """Проверяет бизнес-правила отклика."""
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

    def save(self, *args, **kwargs):
        """Перед сохранением очищает сообщение и запускает валидацию."""
        self.message = self.message.strip()
        self.full_clean()
        super().save(*args, **kwargs)

    def accept(self) -> ProjectMembership:
        """Принимает приглашение и добавляет специалиста в команду проекта."""
        with transaction.atomic():
            invitation = (
                Invitation.objects.select_for_update()
                .select_related(
                    "project", "vacancy", "vacancy__role", "specialist", "invited_by"
                )
                .get(pk=self.pk)
            )

            if invitation.status != invitation.Status.PENDING:
                raise ValidationError(
                    _("Можно принять только приглашение со статусом «Ожидает ответа».")
                )

            already_member = ProjectMembership.objects.filter(
                project=invitation.project,
                specialist=invitation.specialist,
                status=ProjectMembership.Status.ACTIVE,
            ).first()

            if already_member:
                invitation.status = invitation.Status.ACCEPTED
                invitation.responded_at = timezone.now()
                Invitation.objects.filter(pk=invitation.pk).update(
                    status=Invitation.Status.ACCEPTED,
                    responded_at=invitation.responded_at,
                )

                self.status = invitation.status
                self.responded_at = invitation.responded_at

                return already_member

            if not invitation.vacancy.is_open():
                raise ValidationError(_("Открытая роль уже закрыта или заполнена."))

            membership = invitation.vacancy.add_specialist(
                specialist=invitation.specialist,
                added_by=invitation.invited_by,
            )

            invitation.status = invitation.Status.ACCEPTED
            invitation.responded_at = timezone.now()
            Invitation.objects.filter(pk=invitation.pk).update(
                status=Invitation.Status.ACCEPTED,
                responded_at=invitation.responded_at,
            )

            self.status = invitation.status
            self.responded_at = invitation.responded_at

            return membership

    def reject(self, reviewed_by=None) -> None:
        """Отклоняет отклик."""
        self.status = self.Status.REJECTED
        self.reviewed_at = timezone.now()
        self.reviewed_by = reviewed_by
        self.save(update_fields=["status", "reviewed_at", "reviewed_by"])


class Invitation(models.Model):
    """Приглашение специалиста в проект."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Ожидает ответа")
        ACCEPTED = "accepted", _("Принято")
        DECLINED = "declined", _("Отклонено")
        CANCELLED = "cancelled", _("Отменено")
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
        blank=True,
        verbose_name=_("сообщение"),
        help_text=_("Сообщение владельца проекта специалисту."),
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
        return f"{self.project} → {self.specialist}"

    def clean(self):
        """Проверяет бизнес-правила приглашения."""
        errors = {}

        if (
            self.vacancy_id
            and self.project_id
            and self.vacancy.project_id != self.project_id
        ):
            errors["vacancy"] = _(
                "Выбранная открытая роль не относится к указанному проекту."
            )

        if self.specialist_id and self.project_id:
            if self.specialist.user_id == self.project.owner_id:
                errors["specialist"] = _(
                    "Нельзя приглашать владельца проекта в его собственный проект."
                )

            already_member = ProjectMembership.objects.filter(
                project=self.project,
                specialist=self.specialist,
                status=ProjectMembership.Status.ACTIVE,
            ).exists()

            if already_member:
                errors["specialist"] = _("Специалист уже состоит в команде проекта.")

        if self.invited_by_id and self.project_id:
            if (
                self.project.owner_id != self.invited_by_id
                and not self.invited_by.is_staff
            ):
                errors["invited_by"] = _(
                    "Приглашать специалистов может только владелец проекта или администратор."
                )

        if self.status == self.Status.PENDING:
            if self.project_id and self.project.status != Project.Status.PUBLISHED:
                errors["project"] = _("Нельзя приглашать в неопубликованный проект.")

            if self.vacancy_id and not self.vacancy.is_open():
                errors["vacancy"] = _(
                    "Нельзя приглашать на закрытую или заполненную роль."
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
                    "Для этого специалиста уже есть активное приглашение на эту роль."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Перед сохранением очищает сообщение и запускает валидацию."""
        self.message = self.message.strip()
        self.full_clean()
        super().save(*args, **kwargs)

    def accept(self) -> ProjectMembership:
        """Принимает приглашение и добавляет специалиста в команду проекта."""
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

            already_member = ProjectMembership.objects.filter(
                project=invitation.project,
                specialist=invitation.specialist,
                status=ProjectMembership.Status.ACTIVE,
            ).first()

            if already_member:
                responded_at = timezone.now()

                Invitation.objects.filter(pk=invitation.pk).update(
                    status=Invitation.Status.ACCEPTED,
                    responded_at=responded_at,
                )

                self.status = Invitation.Status.ACCEPTED
                self.responded_at = responded_at

                return already_member

            if not invitation.vacancy.is_open():
                raise ValidationError(_("Открытая роль уже закрыта или заполнена."))

            membership = invitation.vacancy.add_specialist(
                specialist=invitation.specialist,
                added_by=invitation.invited_by,
            )

            responded_at = timezone.now()

            Invitation.objects.filter(pk=invitation.pk).update(
                status=Invitation.Status.ACCEPTED,
                responded_at=responded_at,
            )

            self.status = Invitation.Status.ACCEPTED
            self.responded_at = responded_at

            return membership

    def decline(self) -> None:
        """Отклоняет приглашение."""
        if self.status != self.Status.PENDING:
            raise ValidationError(
                _("Можно отклонить только приглашение со статусом «Ожидает ответа».")
            )

        responded_at = timezone.now()

        Invitation.objects.filter(pk=self.pk).update(
            status=Invitation.Status.DECLINED,
            responded_at=responded_at,
        )

        self.status = Invitation.Status.DECLINED
        self.responded_at = responded_at


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
        return f"{self.user} добавил «{self.project}» в избранное"
