from django.contrib import admin

from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from import_export.admin import ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    Project,
    ProjectFile,
    ProjectMembership,
    ProjectTechnology,
    ProjectVacancy,
)


class ProjectTechnologyInline(admin.TabularInline):
    """Inline для технологий проекта."""

    model = ProjectTechnology
    extra = 1
    raw_id_fields = ("technology",)
    fields = (
        "technology",
        "is_required",
        "created_at",
    )
    readonly_fields = ("created_at",)


class ProjectVacancyInline(admin.TabularInline):
    """Inline для открытых ролей проекта."""

    model = ProjectVacancy
    extra = 1
    raw_id_fields = ("role",)
    fields = (
        "role",
        "title",
        "required_level",
        "required_count",
        "current_count",
        "status",
        "created_at",
        "updated_at",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )


class ProjectMembershipInline(admin.TabularInline):
    """Inline для участников команды проекта."""

    model = ProjectMembership
    extra = 0
    raw_id_fields = (
        "specialist",
        "role",
        "added_by",
    )
    fields = (
        "specialist",
        "role",
        "status",
        "joined_at",
        "left_at",
        "added_by",
    )
    readonly_fields = ("joined_at",)


class ProjectFileInline(admin.TabularInline):
    """Inline для файлов проекта."""

    model = ProjectFile
    extra = 0
    raw_id_fields = ("uploaded_by",)
    fields = (
        "title",
        "file",
        "file_type",
        "uploaded_by",
        "uploaded_at",
    )
    readonly_fields = ("uploaded_at",)


@admin.register(Project)
class ProjectAdmin(ImportExportModelAdmin, SimpleHistoryAdmin):
    """Админ-панель проектов."""

    list_display = (
        "title",
        "owner",
        "stage",
        "participation_format",
        "status",
        "display_open_vacancies_count",
        "display_members_count",
        "display_technologies_count",
        "created_at",
        "updated_at",
    )
    list_display_links = (
        "title",
        "owner",
    )
    list_filter = (
        "stage",
        "participation_format",
        "status",
        "technologies",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "title",
        "slug",
        "short_description",
        "description",
        "goal",
        "owner__username",
        "owner__email",
    )
    raw_id_fields = (
        "owner",
        "created_by",
        "updated_by",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "display_cover_preview",
        "display_open_vacancies_count",
        "display_members_count",
        "display_technologies_count",
    )
    date_hierarchy = "created_at"
    prepopulated_fields = {
        "slug": ("title",),
    }
    inlines = (
        ProjectTechnologyInline,
        ProjectVacancyInline,
        ProjectMembershipInline,
        ProjectFileInline,
    )

    fieldsets = (
        (
            _("Владелец и статус"),
            {
                "fields": (
                    "owner",
                    "status",
                    "stage",
                    "participation_format",
                ),
            },
        ),
        (
            _("Описание проекта"),
            {
                "fields": (
                    "title",
                    "slug",
                    "short_description",
                    "description",
                    "goal",
                ),
            },
        ),
        (
            _("Медиа и ссылки"),
            {
                "fields": (
                    "cover_image",
                    "display_cover_preview",
                    "repository_url",
                    "demo_url",
                ),
            },
        ),
        (
            _("Статистика"),
            {
                "fields": (
                    "display_open_vacancies_count",
                    "display_members_count",
                    "display_technologies_count",
                ),
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
                "owner",
                "created_by",
                "updated_by",
            )
            .prefetch_related(
                "technologies",
                "members",
            )
            .annotate(
                vacancies_count=Count("vacancies", distinct=True),
                members_count=Count("memberships", distinct=True),
                technologies_count=Count("technologies", distinct=True),
            )
        )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="Открытых ролей")
    def display_open_vacancies_count(self, obj: Project) -> int:
        return obj.vacancies.filter(status=ProjectVacancy.Status.OPEN).count()

    @admin.display(description="Участников")
    def display_members_count(self, obj: Project) -> int:
        return getattr(obj, "members_count", obj.memberships.count())

    @admin.display(description="Технологий")
    def display_technologies_count(self, obj: Project) -> int:
        return getattr(obj, "technologies_count", obj.technologies.count())

    @admin.display(description="Предпросмотр обложки")
    def display_cover_preview(self, obj: Project) -> str:
        if obj and obj.cover_image:
            return format_html(
                '<img src="{}" style="max-height: 140px; border-radius: 8px;" />',
                obj.cover_image.url,
            )
        return "Обложка не загружена"


@admin.register(ProjectTechnology)
class ProjectTechnologyAdmin(ImportExportModelAdmin):
    """Админ-панель технологий проектов."""

    list_display = (
        "project",
        "technology",
        "is_required",
        "created_at",
    )
    list_display_links = (
        "project",
        "technology",
    )
    list_filter = (
        "is_required",
        "technology__category",
        "created_at",
    )
    search_fields = (
        "project__title",
        "technology__name",
    )
    raw_id_fields = (
        "project",
        "technology",
    )
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"


@admin.register(ProjectVacancy)
class ProjectVacancyAdmin(ImportExportModelAdmin, SimpleHistoryAdmin):
    """Админ-панель открытых ролей проектов."""

    list_display = (
        "title",
        "project",
        "role",
        "required_level",
        "required_count",
        "current_count",
        "display_remaining_slots",
        "status",
        "created_at",
    )
    list_display_links = (
        "title",
        "project",
    )
    list_filter = (
        "role",
        "required_level",
        "status",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "title",
        "description",
        "project__title",
        "role__name",
    )
    raw_id_fields = (
        "project",
        "role",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "display_remaining_slots",
    )
    date_hierarchy = "created_at"

    fieldsets = (
        (
            _("Проект и роль"),
            {
                "fields": (
                    "project",
                    "role",
                    "title",
                    "description",
                ),
            },
        ),
        (
            _("Требования и набор"),
            {
                "fields": (
                    "required_level",
                    "required_count",
                    "current_count",
                    "display_remaining_slots",
                    "status",
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

    @admin.display(description="Свободных мест")
    def display_remaining_slots(self, obj: ProjectVacancy) -> int:
        return obj.remaining_slots()


@admin.register(ProjectMembership)
class ProjectMembershipAdmin(ImportExportModelAdmin, SimpleHistoryAdmin):
    """Админ-панель участников команд."""

    list_display = (
        "project",
        "specialist",
        "role",
        "status",
        "joined_at",
        "left_at",
        "added_by",
        "display_is_active",
    )
    list_display_links = (
        "project",
        "specialist",
    )
    list_filter = (
        "role",
        "status",
        "joined_at",
        "left_at",
    )
    search_fields = (
        "project__title",
        "specialist__user__username",
        "specialist__user__email",
        "specialist__user__first_name",
        "specialist__user__last_name",
        "role__name",
    )
    raw_id_fields = (
        "project",
        "specialist",
        "role",
        "added_by",
    )
    readonly_fields = ("joined_at",)
    date_hierarchy = "joined_at"

    @admin.display(boolean=True, description="Активен")
    def display_is_active(self, obj: ProjectMembership) -> bool:
        return obj.is_active()


@admin.register(ProjectFile)
class ProjectFileAdmin(ImportExportModelAdmin):
    """Админ-панель файлов проектов."""

    list_display = (
        "title",
        "project",
        "file_type",
        "uploaded_by",
        "uploaded_at",
    )
    list_display_links = (
        "title",
        "project",
    )
    list_filter = (
        "file_type",
        "uploaded_at",
    )
    search_fields = (
        "title",
        "project__title",
        "uploaded_by__username",
        "uploaded_by__email",
    )
    raw_id_fields = (
        "project",
        "uploaded_by",
    )
    readonly_fields = ("uploaded_at",)
    date_hierarchy = "uploaded_at"
