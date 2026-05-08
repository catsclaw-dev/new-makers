from django.contrib import admin
from django.db.models import Count, Q
from django.utils.translation import gettext_lazy as _
from import_export.admin import ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from apps.projects.models import Project, ProjectVacancy

from .models import Role, Technology


@admin.register(Role)
class RoleAdmin(ImportExportModelAdmin, SimpleHistoryAdmin):
    """Админ-панель справочника ролей."""

    list_display = (
        "name",
        "slug",
        "is_active",
        "display_open_vacancies_count",
        "display_main_specialists_count",
        "display_preferred_specialists_count",
        "display_status",
        "created_at",
        "updated_at",
    )
    list_display_links = (
        "name",
        "slug",
    )
    list_filter = (
        "is_active",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "name",
        "slug",
        "description",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "display_open_vacancies_count",
        "display_main_specialists_count",
        "display_preferred_specialists_count",
    )
    date_hierarchy = "created_at"
    prepopulated_fields = {
        "slug": ("name",),
    }
    actions = (
        "activate_roles",
        "deactivate_roles",
    )

    fieldsets = (
        (
            _("Основная информация"),
            {
                "fields": (
                    "name",
                    "slug",
                    "description",
                    "is_active",
                ),
            },
        ),
        (
            _("Статистика использования"),
            {
                "fields": (
                    "display_open_vacancies_count",
                    "display_main_specialists_count",
                    "display_preferred_specialists_count",
                ),
            },
        ),
        (
            _("Служебная информация"),
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(
            open_vacancies_count=Count(
                "project_vacancies",
                filter=Q(project_vacancies__status=ProjectVacancy.Status.OPEN),
                distinct=True,
            ),
            main_specialists_count=Count(
                "main_specialists",
                distinct=True,
            ),
            preferred_specialists_count=Count(
                "preferred_by_specialists",
                distinct=True,
            ),
        )

    @admin.display(description="Открытых ролей")
    def display_open_vacancies_count(self, obj: Role) -> int:
        return getattr(obj, "open_vacancies_count", 0)

    @admin.display(description="Основная у специалистов")
    def display_main_specialists_count(self, obj: Role) -> int:
        return getattr(obj, "main_specialists_count", 0)

    @admin.display(description="Интересует специалистов")
    def display_preferred_specialists_count(self, obj: Role) -> int:
        return getattr(obj, "preferred_specialists_count", 0)

    @admin.display(description="Статус")
    def display_status(self, obj: Role) -> str:
        return "Активна" if obj.is_active else "Отключена"

    @admin.action(description="Активировать выбранные роли")
    def activate_roles(self, request, queryset):
        updated_count = queryset.update(is_active=True)
        self.message_user(request, f"Активировано ролей: {updated_count}")

    @admin.action(description="Отключить выбранные роли")
    def deactivate_roles(self, request, queryset):
        updated_count = queryset.update(is_active=False)
        self.message_user(request, f"Отключено ролей: {updated_count}")


@admin.register(Technology)
class TechnologyAdmin(ImportExportModelAdmin, SimpleHistoryAdmin):
    """Админ-панель справочника технологий."""

    list_display = (
        "name",
        "slug",
        "category",
        "is_active",
        "display_projects_count",
        "display_published_projects_count",
        "display_specialists_count",
        "display_category_label",
        "created_at",
        "updated_at",
    )
    list_display_links = (
        "name",
        "slug",
    )
    list_filter = (
        "category",
        "is_active",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "name",
        "slug",
        "description",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "display_projects_count",
        "display_published_projects_count",
        "display_specialists_count",
    )
    date_hierarchy = "created_at"
    prepopulated_fields = {
        "slug": ("name",),
    }
    actions = (
        "activate_technologies",
        "deactivate_technologies",
    )

    fieldsets = (
        (
            _("Основная информация"),
            {
                "fields": (
                    "name",
                    "slug",
                    "category",
                    "description",
                    "is_active",
                ),
            },
        ),
        (
            _("Статистика использования"),
            {
                "fields": (
                    "display_projects_count",
                    "display_published_projects_count",
                    "display_specialists_count",
                ),
            },
        ),
        (
            _("Служебная информация"),
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(
            projects_count=Count(
                "projects",
                distinct=True,
            ),
            published_projects_count=Count(
                "projects",
                filter=Q(projects__status=Project.Status.PUBLISHED),
                distinct=True,
            ),
            specialists_count=Count(
                "specialists",
                distinct=True,
            ),
        )

    @admin.display(description="Проектов")
    def display_projects_count(self, obj: Technology) -> int:
        return getattr(obj, "projects_count", 0)

    @admin.display(description="Опубликованных проектов")
    def display_published_projects_count(self, obj: Technology) -> int:
        return getattr(obj, "published_projects_count", 0)

    @admin.display(description="Специалистов")
    def display_specialists_count(self, obj: Technology) -> int:
        return getattr(obj, "specialists_count", 0)

    @admin.display(description="Категория")
    def display_category_label(self, obj: Technology) -> str:
        return obj.get_category_display()

    @admin.action(description="Активировать выбранные технологии")
    def activate_technologies(self, request, queryset):
        updated_count = queryset.update(is_active=True)
        self.message_user(request, f"Активировано технологий: {updated_count}")

    @admin.action(description="Отключить выбранные технологии")
    def deactivate_technologies(self, request, queryset):
        updated_count = queryset.update(is_active=False)
        self.message_user(request, f"Отключено технологий: {updated_count}")
