from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone as django_timezone
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords

from apps.directories.models import Role, Technology
from apps.common_validators import validate_avatar_image


class SpecialistProfile(models.Model):
    """Профиль IT-специалиста."""

    class Level(models.TextChoices):
        INTERN = "intern", _("Стажёр")
        JUNIOR = "junior", _("Junior")
        MIDDLE = "middle", _("Middle")
        SENIOR = "senior", _("Senior")
        LEAD = "lead", _("Lead")

    class AvailabilityStatus(models.TextChoices):
        LOOKING = "looking", _("Ищу проект")
        OPEN = "open", _("Открыт к предложениям")
        BUSY = "busy", _("Занят")
        HIDDEN = "hidden", _("Скрыт")

    class ParticipationFormat(models.TextChoices):
        REMOTE = "remote", _("Удалённо")
        HYBRID = "hybrid", _("Гибрид")
        OFFICE = "office", _("Офис")
        ANY = "any", _("Любой формат")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="specialist_profile",
        verbose_name=_("пользователь"),
        help_text=_("Пользователь, которому принадлежит профиль специалиста."),
    )
    main_role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="main_specialists",
        verbose_name=_("основная роль"),
        help_text=_("Основная профессиональная роль специалиста."),
    )
    preferred_roles = models.ManyToManyField(
        Role,
        blank=True,
        related_name="preferred_by_specialists",
        verbose_name=_("интересующие роли"),
        help_text=_("Роли, в которых специалист хотел бы участвовать в проектах."),
    )
    technologies = models.ManyToManyField(
        Technology,
        through="SpecialistTechnology",
        related_name="specialists",
        verbose_name=_("технологии"),
    )
    avatar = models.ImageField(
        upload_to="specialists/avatars/",
        blank=True,
        null=True,
        validators=[validate_avatar_image],
        verbose_name=_("аватар"),
        help_text=_("Фотография или изображение профиля специалиста."),
    )
    level = models.CharField(
        max_length=20,
        choices=Level.choices,
        default=Level.JUNIOR,
        verbose_name=_("уровень"),
    )
    status = models.CharField(
        max_length=20,
        choices=AvailabilityStatus.choices,
        default=AvailabilityStatus.LOOKING,
        verbose_name=_("статус доступности"),
    )
    participation_format = models.CharField(
        max_length=20,
        choices=ParticipationFormat.choices,
        default=ParticipationFormat.REMOTE,
        verbose_name=_("формат участия"),
    )
    bio = models.TextField(
        blank=True,
        verbose_name=_("о себе"),
        help_text=_("Краткое описание опыта, интересов и целей специалиста."),
    )
    experience_years = models.PositiveSmallIntegerField(
        default=0,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(60),
        ],
        verbose_name=_("опыт в годах"),
    )
    weekly_hours = models.PositiveSmallIntegerField(
        default=10,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(80),
        ],
        verbose_name=_("часов в неделю"),
        help_text=_("Сколько часов в неделю специалист готов уделять проектам."),
    )
    city = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("город"),
    )
    timezone = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("часовой пояс"),
        help_text=_("Например: Europe/Moscow."),
    )
    github_url = models.URLField(
        blank=True,
        verbose_name=_("GitHub"),
    )
    gitlab_url = models.URLField(
        blank=True,
        verbose_name=_("GitLab"),
    )
    portfolio_url = models.URLField(
        blank=True,
        verbose_name=_("портфолио"),
    )
    telegram = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Telegram"),
        help_text=_("Контакт для связи, например: @username."),
    )
    created_at = models.DateTimeField(
        default=django_timezone.now,
        verbose_name=_("дата создания"),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("дата изменения"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_specialist_profiles",
        verbose_name=_("создал"),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_specialist_profiles",
        verbose_name=_("изменил"),
    )

    history = HistoricalRecords(verbose_name=_("история изменений"))

    class Meta:
        verbose_name = _("профиль специалиста")
        verbose_name_plural = _("профили специалистов")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user} — {self.get_level_display()}"

    def get_absolute_url(self) -> str:
        return reverse("specialists:specialist_detail", kwargs={"pk": self.pk})

    def is_available_for_project(self) -> bool:
        """Проверяет, доступен ли специалист для участия в проекте."""
        return self.status in {
            self.AvailabilityStatus.LOOKING,
            self.AvailabilityStatus.OPEN,
        }

    def get_display_name(self) -> str:
        """Возвращает удобное имя специалиста для карточек и админки."""
        return self.user.get_full_name() or self.user.username

    def save(self, *args, **kwargs):
        """Перед сохранением убирает лишние пробелы из текстового описания."""
        self.bio = self.bio.strip()
        super().save(*args, **kwargs)


class SpecialistTechnology(models.Model):
    """Промежуточная таблица навыков специалиста."""

    class SkillLevel(models.TextChoices):
        BASIC = "basic", _("Базовый")
        CONFIDENT = "confident", _("Уверенный")
        ADVANCED = "advanced", _("Продвинутый")
        EXPERT = "expert", _("Эксперт")

    specialist = models.ForeignKey(
        SpecialistProfile,
        on_delete=models.CASCADE,
        related_name="specialist_technologies",
        verbose_name=_("специалист"),
    )
    technology = models.ForeignKey(
        Technology,
        on_delete=models.CASCADE,
        related_name="specialist_technologies",
        verbose_name=_("технология"),
    )
    level = models.CharField(
        max_length=20,
        choices=SkillLevel.choices,
        default=SkillLevel.CONFIDENT,
        verbose_name=_("уровень владения"),
    )
    years_of_experience = models.PositiveSmallIntegerField(
        default=0,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(60),
        ],
        verbose_name=_("опыт в годах"),
    )
    is_primary = models.BooleanField(
        default=False,
        verbose_name=_("ключевой навык"),
        help_text=_("Отметить, если технология является одной из основных."),
    )
    created_at = models.DateTimeField(
        default=django_timezone.now,
        verbose_name=_("дата добавления"),
    )

    class Meta:
        verbose_name = _("технология специалиста")
        verbose_name_plural = _("технологии специалистов")
        ordering = ["specialist", "-is_primary", "technology__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["specialist", "technology"],
                name="unique_specialist_technology",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.specialist} — {self.technology}"
