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

    def has_active_owned_projects(self) -> bool:
        """
        Проверяет, есть ли у пользователя собственные неархивные проекты.
        """
        if not self.pk:
            return False

        from apps.projects.models import Project

        return (
            Project.objects.filter(owner=self)
            .exclude(status=Project.Status.ARCHIVED)
            .exists()
        )

    def get_dynamic_role(self) -> str:
        """
        Возвращает динамическую роль пользователя на сервисе.
        """
        if self.is_staff or self.is_superuser or self.role == self.UserRole.ADMIN:
            return self.UserRole.ADMIN

        if self.has_active_owned_projects():
            return self.UserRole.PROJECT_OWNER

        return self.UserRole.SPECIALIST

    def get_dynamic_role_display(self) -> str:
        """
        Возвращает человекочитаемое название динамической роли.
        """
        dynamic_role = self.get_dynamic_role()
        return self.UserRole(dynamic_role).label

    def is_dynamic_project_owner(self) -> bool:
        """
        Проверяет, является ли пользователь владельцем активных проектов.
        """
        return self.get_dynamic_role() == self.UserRole.PROJECT_OWNER

    def is_dynamic_specialist(self) -> bool:
        """
        Проверяет, отображается ли пользователь как специалист.
        """
        return self.get_dynamic_role() == self.UserRole.SPECIALIST

    class Meta:
        verbose_name = _("пользователь")
        verbose_name_plural = _("пользователи")
        ordering = ["username"]

    def __str__(self) -> str:
        """
        Возвращает строковое представление объекта.
        """
        return self.get_full_name() or self.username


# Create your models here.
