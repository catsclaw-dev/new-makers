from django.contrib import admin
from django.db.models import Avg, Count, Q
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from import_export.admin import ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from apps.interactions.models import Application, Invitation
from apps.projects.models import ProjectMembership
from apps.reviews.models import Review

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


class SpecialistProjectMembershipInline(admin.TabularInline):
    """Inline для участия специалиста в проектах."""

    model = ProjectMembership
    extra = 0
    raw_id_fields = (
        "project",
        "role",
        "added_by",
    )
    fields = (
        "project",
        "role",
        "status",
        "joined_at",
        "left_at",
        "added_by",
    )
    readonly_fields = ("joined_at",)


class SpecialistApplicationInline(admin.TabularInline):
    """Inline для откликов специалиста."""

    model = Application
    extra = 0
    can_delete = False
    fields = (
        "project",
        "vacancy",
        "status",
        "message",
        "applied_at",
        "reviewed_at",
        "reviewed_by",
    )
    readonly_fields = (
        "project",
        "vacancy",
        "status",
        "message",
        "applied_at",
        "reviewed_at",
        "reviewed_by",
    )

    def has_add_permission(self, request, obj=None):
        return False


class SpecialistInvitationInline(admin.TabularInline):
    """Inline для приглашений специалиста."""

    model = Invitation
    extra = 0
    can_delete = False
    fields = (
        "project",
        "vacancy",
        "invited_by",
        "status",
        "message",
        "invited_at",
        "responded_at",
    )
    readonly_fields = (
        "project",
        "vacancy",
        "invited_by",
        "status",
        "message",
        "invited_at",
        "responded_at",
    )

    def has_add_permission(self, request, obj=None):
        return False


class SpecialistReviewInline(admin.TabularInline):
    """Inline для отзывов о специалисте."""

    model = Review
    extra = 0
    can_delete = False
    fields = (
        "project",
        "author",
        "rating",
        "status",
        "text",
        "created_at",
        "updated_at",
    )
    readonly_fields = (
        "project",
        "author",
        "rating",
        "status",
        "text",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request, obj=None):
        return False


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
        "display_active_projects_count",
        "display_applications_count",
        "display_invitations_count",
        "display_reviews_count",
        "display_average_rating",
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
        "project_memberships__status",
        "applications__status",
        "invitations__status",
        "received_reviews__status",
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
        "project_memberships__project__title",
        "applications__project__title",
        "invitations__project__title",
    )
    raw_id_fields = (
        "user",
        "main_role",
        "created_by",
        "updated_by",
    )
    filter_horizontal = (
        "preferred_roles",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "display_avatar_preview",
        "display_technology_count",
        "display_active_projects_count",
        "display_applications_count",
        "display_invitations_count",
        "display_reviews_count",
        "display_average_rating",
    )
    date_hierarchy = "created_at"
    inlines = (
        SpecialistTechnologyInline,
        SpecialistProjectMembershipInline,
        SpecialistApplicationInline,
        SpecialistInvitationInline,
        SpecialistReviewInline,
    )
    actions = (
        "mark_as_looking",
        "mark_as_open",
        "mark_as_busy",
    )

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
            _("Статистика специалиста"),
            {
                "fields": (
                    "display_technology_count",
                    "display_active_projects_count",
                    "display_applications_count",
                    "display_invitations_count",
                    "display_reviews_count",
                    "display_average_rating",
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
                "user",
                "main_role",
            )
            .prefetch_related(
                "preferred_roles",
                "technologies",
            )
            .annotate(
                technologies_count=Count("technologies", distinct=True),
                active_projects_count=Count(
                    "project_memberships",
                    filter=Q(project_memberships__status=ProjectMembership.Status.ACTIVE),
                    distinct=True,
                ),
                applications_count=Count("applications", distinct=True),
                invitations_count=Count("invitations", distinct=True),
                reviews_count=Count("received_reviews", distinct=True),
                average_rating=Avg(
                    "received_reviews__rating",
                    filter=Q(received_reviews__status=Review.Status.PUBLISHED),
                ),
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

    @admin.display(description="Активных проектов")
    def display_active_projects_count(self, obj: SpecialistProfile) -> int:
        return getattr(obj, "active_projects_count", obj.project_memberships.count())

    @admin.display(description="Откликов")
    def display_applications_count(self, obj: SpecialistProfile) -> int:
        return getattr(obj, "applications_count", obj.applications.count())

    @admin.display(description="Приглашений")
    def display_invitations_count(self, obj: SpecialistProfile) -> int:
        return getattr(obj, "invitations_count", obj.invitations.count())

    @admin.display(description="Отзывов")
    def display_reviews_count(self, obj: SpecialistProfile) -> int:
        return getattr(obj, "reviews_count", obj.received_reviews.count())

    @admin.display(description="Средняя оценка")
    def display_average_rating(self, obj: SpecialistProfile) -> str:
        average_rating = getattr(obj, "average_rating", None)

        if average_rating is None:
            return "—"

        return f"{average_rating:.1f}/5"

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

    @admin.action(description="Установить статус «Ищу проект»")
    def mark_as_looking(self, request, queryset):
        updated_count = queryset.update(status=SpecialistProfile.AvailabilityStatus.LOOKING)
        self.message_user(request, f"Обновлено профилей: {updated_count}")

    @admin.action(description="Установить статус «Открыт к предложениям»")
    def mark_as_open(self, request, queryset):
        updated_count = queryset.update(status=SpecialistProfile.AvailabilityStatus.OPEN)
        self.message_user(request, f"Обновлено профилей: {updated_count}")

    @admin.action(description="Установить статус «Занят»")
    def mark_as_busy(self, request, queryset):
        updated_count = queryset.update(status=SpecialistProfile.AvailabilityStatus.BUSY)
        self.message_user(request, f"Обновлено профилей: {updated_count}")


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
    readonly_fields = (
        "created_at",
    )
    date_hierarchy = "created_at"
