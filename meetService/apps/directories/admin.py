from django.contrib import admin

from django.contrib import admin
from django.db.models import Count
from django.utils.translation import gettext_lazy as _
from import_export.admin import ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from .models import Role, Technology


@admin.register(Role)
class RoleAdmin(ImportExportModelAdmin, SimpleHistoryAdmin):
    """Админ-панель справочника ролей."""

    list_display = (
        "name",
        "slug",
        "is_active",
        "created_at",
        "updated_at",
        "display_status",
    )
    list_display_links = ("name", "slug")
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
    )
    date_hierarchy = "created_at"
    prepopulated_fields = {
        "slug": ("name",),
    }

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
            _("Служебная информация"),
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    @admin.display(description="Статус")
    def display_status(self, obj: Role) -> str:
        return "Активна" if obj.is_active else "Отключена"


@admin.register(Technology)
class TechnologyAdmin(ImportExportModelAdmin, SimpleHistoryAdmin):
    """Админ-панель справочника технологий."""

    list_display = (
        "name",
        "slug",
        "category",
        "is_active",
        "created_at",
        "updated_at",
        "display_category_label",
    )
    list_display_links = ("name", "slug")
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
    )
    date_hierarchy = "created_at"
    prepopulated_fields = {
        "slug": ("name",),
    }

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
            _("Служебная информация"),
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    @admin.display(description="Категория")
    def display_category_label(self, obj: Technology) -> str:
        return obj.get_category_display()
