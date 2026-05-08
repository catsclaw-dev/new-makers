from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords


class User(AbstractUser):
    """Кастомная модель пользователя сервиса поиска IT-команды."""

    class UserRole(models.TextChoices):
        SPECIALIST = "specialist", _("Специалист")
        PROJECT_OWNER = "project_owner", _("Владелец проекта")
        ADMIN = "admin", _("Администратор")

    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.SPECIALIST,
        verbose_name=_("роль пользователя"),
        help_text=_("Определяет основной сценарий работы пользователя на сайте."),
    )

    history = HistoricalRecords(verbose_name=_("история изменений"))

    class Meta:
        verbose_name = _("пользователь")
        verbose_name_plural = _("пользователи")
        ordering = ["username"]

    def __str__(self) -> str:
        return self.get_full_name() or self.username


# Create your models here.
