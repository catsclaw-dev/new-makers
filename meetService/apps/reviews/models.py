from __future__ import annotations

from django.db import models


from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords

from apps.projects.models import Project, ProjectMembership
from apps.specialists.models import SpecialistProfile


class Review(models.Model):
    """Отзыв о специалисте в рамках проекта."""

    class Status(models.TextChoices):
        DRAFT = "draft", _("Черновик")
        PUBLISHED = "published", _("Опубликован")
        HIDDEN = "hidden", _("Скрыт")
        REJECTED = "rejected", _("Отклонён")

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name=_("проект"),
        help_text=_("Проект, в рамках которого оставлен отзыв."),
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="written_reviews",
        verbose_name=_("автор отзыва"),
        help_text=_("Пользователь, который оставил отзыв."),
    )
    specialist = models.ForeignKey(
        SpecialistProfile,
        on_delete=models.CASCADE,
        related_name="received_reviews",
        verbose_name=_("специалист"),
        help_text=_("Специалист, о котором оставлен отзыв."),
    )
    rating = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5),
        ],
        verbose_name=_("оценка"),
        help_text=_("Оценка от 1 до 5."),
    )
    text = models.TextField(
        verbose_name=_("текст отзыва"),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name=_("статус"),
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("дата создания"),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("дата изменения"),
    )

    history = HistoricalRecords(verbose_name=_("история изменений"))

    class Meta:
        verbose_name = _("отзыв")
        verbose_name_plural = _("отзывы")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "author", "specialist"],
                name="unique_review_for_project_author_specialist",
            ),
            models.CheckConstraint(
                condition=Q(rating__gte=1) & Q(rating__lte=5),
                name="review_rating_between_1_and_5",
            ),
        ]

    def __str__(self) -> str:
        """
        Возвращает строковое представление объекта.
        """
        return f"Отзыв {self.author} о {self.specialist} — {self.rating}/5"

    def clean(self) -> None:
        """
        Проверяет бизнес-правила отзыва.
        """
        errors = {}

        if self.author_id and self.specialist_id:
            if self.author_id == self.specialist.user_id:
                errors["specialist"] = _("Нельзя оставить отзыв самому себе.")

        if self.project_id and self.specialist_id:
            is_project_member = ProjectMembership.objects.filter(
                project=self.project,
                specialist=self.specialist,
            ).exists()

            if not is_project_member:
                errors["specialist"] = _(
                    "Отзыв можно оставить только специалисту, который участвовал в проекте."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args: object, **kwargs: object) -> None:
        """
        Перед сохранением очищает текст и запускает валидацию.
        Args:
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы
        """
        self.text = self.text.strip()
        self.full_clean()
        super().save(*args, **kwargs)

    def publish(self) -> None:
        """
        Публикует отзыв.
        """
        self.status = self.Status.PUBLISHED
        self.save(update_fields=["status", "updated_at"])

    def hide(self) -> None:
        """
        Скрывает отзыв.
        """
        self.status = self.Status.HIDDEN
        self.save(update_fields=["status", "updated_at"])

    def reject(self) -> None:
        """
        Отклоняет отзыв.
        """
        self.status = self.Status.REJECTED
        self.save(update_fields=["status", "updated_at"])

    def is_public(self) -> bool:
        """
        Проверяет, опубликован ли отзыв.
        """
        return self.status == self.Status.PUBLISHED
