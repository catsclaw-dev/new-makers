from __future__ import annotations

from import_export import fields, resources
from django.db.models import F

from .models import Project, ProjectMembership, ProjectVacancy
from django.utils.translation import gettext_lazy as _


class ProjectResource(resources.ModelResource):
    """Ресурс для экспорта проектов в Excel."""

    owner = fields.Field(column_name=_("Владелец"))
    status_display = fields.Field(column_name=_("Статус"))
    stage_display = fields.Field(column_name=_("Стадия"))
    participation_format_display = fields.Field(column_name=_("Формат участия"))
    technologies_list = fields.Field(column_name=_("Технологии"))
    open_vacancies_count = fields.Field(column_name=_("Открытых ролей"))
    members_count = fields.Field(column_name=_("Участников"))

    class Meta:
        model = Project
        fields = (
            "id",
            "title",
            "owner",
            "status_display",
            "stage_display",
            "participation_format_display",
            "short_description",
            "goal",
            "technologies_list",
            "open_vacancies_count",
            "members_count",
            "repository_url",
            "demo_url",
            "created_at",
            "updated_at",
        )
        export_order = fields

    def dehydrate_owner(self, obj: object) -> object:
        """
        Возвращает значение поля для экспорта данных.
        Args:
            obj: Объект модели
        """
        return obj.owner.get_username() if obj.owner else ""

    def dehydrate_status_display(self, obj: object) -> object:
        """
        Возвращает значение поля для экспорта данных.
        Args:
            obj: Объект модели
        """
        return obj.get_status_display()

    def dehydrate_stage_display(self, obj: object) -> object:
        """
        Возвращает значение поля для экспорта данных.
        Args:
            obj: Объект модели
        """
        return obj.get_stage_display()

    def dehydrate_participation_format_display(self, obj: object) -> object:
        """
        Возвращает значение поля для экспорта данных.
        Args:
            obj: Объект модели
        """
        return obj.get_participation_format_display()

    def dehydrate_technologies_list(self, obj: object) -> object:
        """
        Возвращает значение поля для экспорта данных.
        Args:
            obj: Объект модели
        """
        return ", ".join(obj.technologies.values_list("name", flat=True))

    def dehydrate_open_vacancies_count(self, obj: object) -> int:
        """
        Возвращает значение поля для экспорта данных.
        Args:
            obj: Объект модели
        """
        return obj.vacancies.filter(
            status=ProjectVacancy.Status.OPEN,
            current_count__lt=F("required_count"),
        ).count()

    def dehydrate_members_count(self, obj: object) -> int:
        """
        Возвращает значение поля для экспорта данных.
        Args:
            obj: Объект модели
        """
        return obj.memberships.filter(
            status__in=[
                ProjectMembership.Status.ACTIVE,
                ProjectMembership.Status.PAUSED,
            ]
        ).count()
