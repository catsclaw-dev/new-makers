from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords


class Role(models.Model):
    """Справочник ролей специалистов и ролей в проектах."""

    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("название роли"),
        help_text=_("Например: Frontend-разработчик, Backend-разработчик, QA-инженер."),
    )
    slug = models.SlugField(
        max_length=120,
        unique=True,
        verbose_name=_("URL-идентификатор"),
        help_text=_("Короткое уникальное имя для URL и фильтрации."),
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("описание"),
        help_text=_("Краткое описание обязанностей и смысла роли."),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("активна"),
        help_text=_("Если выключено, роль не используется в новых записях."),
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
        verbose_name = _("роль")
        verbose_name_plural = _("роли")
        ordering = ["name"]

    def __str__(self) -> str:
        """
        Возвращает строковое представление объекта.
        """
        return self.name

    def get_absolute_url(self) -> str:
        """
        Возвращает значение `absolute url`.
        """
        return reverse("role_detail", kwargs={"slug": self.slug})


class Technology(models.Model):
    """Справочник технологий, языков программирования и инструментов."""

    class TechnologyCategory(models.TextChoices):
        LANGUAGE = "language", _("Язык программирования")
        FRAMEWORK = "framework", _("Фреймворк")
        DATABASE = "database", _("База данных")
        DEVOPS = "devops", _("DevOps")
        DESIGN = "design", _("Дизайн")
        TESTING = "testing", _("Тестирование")
        OTHER = "other", _("Другое")

    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("название технологии"),
        help_text=_("Например: Python, Django, React, PostgreSQL."),
    )
    slug = models.SlugField(
        max_length=120,
        unique=True,
        verbose_name=_("URL-идентификатор"),
    )
    category = models.CharField(
        max_length=30,
        choices=TechnologyCategory.choices,
        default=TechnologyCategory.OTHER,
        verbose_name=_("категория"),
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("описание"),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("активна"),
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
        verbose_name = _("технология")
        verbose_name_plural = _("технологии")
        ordering = ["category", "name"]

    def __str__(self) -> str:
        """
        Возвращает строковое представление объекта.
        """
        return self.name

    def get_absolute_url(self) -> str:
        """
        Возвращает значение `absolute url`.
        """
        return reverse("technology_detail", kwargs={"slug": self.slug})
