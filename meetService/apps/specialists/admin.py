from django.contrib import admin

from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from import_export.admin import ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from .models import SpecialistProfile, SpecialistTechnology


class SpecialistTechnologyInline(admin.TabularInline):
    """Inline для технологий специалиста."""

    model = SpecialistTechnology
    extra = 1
    raw_id_fields = ("technology",)
    fields = (
        "technology",
        "level",
        "years_of_experience",
        "is_primary",
        "created_at",
    )
    readonly_fields = ("created_at",)


@admin.register(SpecialistProfile)
class SpecialistProfileAdmin(ImportExportModelAdmin, SimpleHistoryAdmin):
    """Админ-панель профилей специалистов."""

    list_display = (
        "display_name",
        "user",
        "main_role",
        "level",
        "status",
        "participation_format",
        "experience_years",
        "weekly_hours",
        "display_technology_count",
        "display_is_available",
        "created_at",
    )
    list_display_links = (
        "display_name",
        "user",
    )
    list_filter = (
        "main_role",
        "preferred_roles",
        "level",
        "status",
        "participation_format",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
        "bio",
        "city",
        "github_url",
        "gitlab_url",
        "portfolio_url",
        "telegram",
    )
    raw_id_fields = (
        "user",
        "main_role",
        "created_by",
        "updated_by",
    )
    filter_horizontal = ("preferred_roles",)
    readonly_fields = (
        "created_at",
        "updated_at",
        "display_avatar_preview",
        "display_technology_count",
    )
    date_hierarchy = "created_at"
    inlines = (SpecialistTechnologyInline,)

    fieldsets = (
        (
            _("Пользователь и роль"),
            {
                "fields": (
                    "user",
                    "main_role",
                    "preferred_roles",
                    "level",
                    "status",
                    "participation_format",
                ),
            },
        ),
        (
            _("Профиль"),
            {
                "fields": (
                    "avatar",
                    "display_avatar_preview",
                    "bio",
                    "experience_years",
                    "weekly_hours",
                    "city",
                    "timezone",
                ),
            },
        ),
        (
            _("Ссылки и контакты"),
            {
                "fields": (
                    "github_url",
                    "gitlab_url",
                    "portfolio_url",
                    "telegram",
                ),
            },
        ),
        (
            _("Статистика"),
            {
                "fields": ("display_technology_count",),
            },
        ),
        (
            _("Служебная информация"),
            {
                "fields": (
                    "created_at",
                    "updated_at",
                    "created_by",
                    "updated_by",
                ),
            },
        ),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return (
            queryset.select_related(
                "user",
                "main_role",
            )
            .prefetch_related(
                "preferred_roles",
                "technologies",
            )
            .annotate(
                technologies_count=Count("technologies", distinct=True),
            )
        )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="Специалист")
    def display_name(self, obj: SpecialistProfile) -> str:
        return obj.get_display_name()

    @admin.display(description="Технологий")
    def display_technology_count(self, obj: SpecialistProfile) -> int:
        return getattr(obj, "technologies_count", obj.technologies.count())

    @admin.display(boolean=True, description="Доступен")
    def display_is_available(self, obj: SpecialistProfile) -> bool:
        return obj.is_available_for_project()

    @admin.display(description="Предпросмотр аватара")
    def display_avatar_preview(self, obj: SpecialistProfile) -> str:
        if obj and obj.avatar:
            return format_html(
                '<img src="{}" style="max-height: 120px; border-radius: 8px;" />',
                obj.avatar.url,
            )
        return "Аватар не загружен"


@admin.register(SpecialistTechnology)
class SpecialistTechnologyAdmin(ImportExportModelAdmin):
    """Админ-панель технологий специалистов."""

    list_display = (
        "specialist",
        "technology",
        "level",
        "years_of_experience",
        "is_primary",
        "created_at",
    )
    list_display_links = (
        "specialist",
        "technology",
    )
    list_filter = (
        "level",
        "is_primary",
        "technology__category",
        "created_at",
    )
    search_fields = (
        "specialist__user__username",
        "specialist__user__email",
        "specialist__user__first_name",
        "specialist__user__last_name",
        "technology__name",
    )
    raw_id_fields = (
        "specialist",
        "technology",
    )
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
