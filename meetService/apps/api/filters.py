from __future__ import annotations

import django_filters
from django.db.models import F, QuerySet

from apps.interactions.models import Application, Invitation
from apps.projects.models import Project, ProjectVacancy
from apps.specialists.models import SpecialistProfile


class ProjectFilter(django_filters.FilterSet):
    technology = django_filters.CharFilter(field_name="technologies__slug")
    role = django_filters.CharFilter(field_name="vacancies__role__slug")
    has_open_vacancies = django_filters.BooleanFilter(
        method="filter_has_open_vacancies"
    )
    created_after = django_filters.DateTimeFilter(
        field_name="created_at",
        lookup_expr="gte",
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created_at",
        lookup_expr="lte",
    )

    class Meta:
        model = Project
        fields = (
            "stage",
            "participation_format",
            "status",
            "owner",
            "technology",
            "role",
            "has_open_vacancies",
        )

    def filter_has_open_vacancies(
        self, queryset: QuerySet, name: str, value: object
    ) -> object:
        """
        Применяет пользовательскую фильтрацию queryset.
        Args:
            queryset: Набор объектов для обработки
            name: Название поля или объекта
            value: Проверяемое значение
        """
        open_filter = {
            "vacancies__status": ProjectVacancy.Status.OPEN,
            "vacancies__current_count__lt": F("vacancies__required_count"),
        }

        if value:
            return queryset.filter(**open_filter).distinct()

        return queryset.exclude(**open_filter).distinct()


class ProjectVacancyFilter(django_filters.FilterSet):
    role = django_filters.CharFilter(field_name="role__slug")
    project_slug = django_filters.CharFilter(field_name="project__slug")
    is_open = django_filters.BooleanFilter(method="filter_is_open")

    class Meta:
        model = ProjectVacancy
        fields = (
            "project",
            "project_slug",
            "role",
            "required_level",
            "status",
            "is_open",
        )

    def filter_is_open(self, queryset: QuerySet, name: str, value: object) -> object:
        """
        Применяет пользовательскую фильтрацию queryset.
        Args:
            queryset: Набор объектов для обработки
            name: Название поля или объекта
            value: Проверяемое значение
        """
        open_filter = {
            "status": ProjectVacancy.Status.OPEN,
            "current_count__lt": F("required_count"),
        }

        if value:
            return queryset.filter(**open_filter)

        return queryset.exclude(**open_filter)


class SpecialistProfileFilter(django_filters.FilterSet):
    role = django_filters.CharFilter(field_name="main_role__slug")
    technology = django_filters.CharFilter(field_name="technologies__slug")
    min_experience = django_filters.NumberFilter(
        field_name="experience_years",
        lookup_expr="gte",
    )
    max_experience = django_filters.NumberFilter(
        field_name="experience_years",
        lookup_expr="lte",
    )
    is_available = django_filters.BooleanFilter(method="filter_is_available")

    class Meta:
        model = SpecialistProfile
        fields = (
            "role",
            "technology",
            "level",
            "status",
            "participation_format",
            "city",
            "is_available",
        )

    def filter_is_available(
        self, queryset: QuerySet, name: str, value: object
    ) -> object:
        """
        Применяет пользовательскую фильтрацию queryset.
        Args:
            queryset: Набор объектов для обработки
            name: Название поля или объекта
            value: Проверяемое значение
        """
        available_statuses = [
            SpecialistProfile.AvailabilityStatus.LOOKING,
            SpecialistProfile.AvailabilityStatus.OPEN,
        ]

        if value:
            return queryset.filter(status__in=available_statuses)

        return queryset.exclude(status__in=available_statuses)


class ApplicationFilter(django_filters.FilterSet):
    project_slug = django_filters.CharFilter(field_name="project__slug")
    vacancy_role = django_filters.CharFilter(field_name="vacancy__role__slug")

    class Meta:
        model = Application
        fields = (
            "project",
            "project_slug",
            "vacancy",
            "vacancy_role",
            "status",
        )


class InvitationFilter(django_filters.FilterSet):
    project_slug = django_filters.CharFilter(field_name="project__slug")
    vacancy_role = django_filters.CharFilter(field_name="vacancy__role__slug")

    class Meta:
        model = Invitation
        fields = (
            "project",
            "project_slug",
            "vacancy",
            "vacancy_role",
            "status",
        )
