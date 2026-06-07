from __future__ import annotations

from django.contrib import admin
from django.db.models import Count, Q, QuerySet
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from import_export.admin import ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from apps.interactions.models import Application, Invitation
from apps.projects.models import ProjectMembership

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

    def has_add_permission(self, request: HttpRequest, obj: object = None) -> bool:
        """
        Выполняет логику функции.
        Args:
            request: HTTP-запрос текущего пользователя
            obj: Объект модели
        """
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

    def has_add_permission(self, request: HttpRequest, obj: object = None) -> bool:
        """
        Выполняет логику функции.
        Args:
            request: HTTP-запрос текущего пользователя
            obj: Объект модели
        """
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
    filter_horizontal = ("preferred_roles",)
    readonly_fields = (
        "created_at",
        "updated_at",
        "display_avatar_preview",
        "display_technology_count",
        "display_active_projects_count",
        "display_applications_count",
        "display_invitations_count",
    )
    date_hierarchy = "created_at"
    inlines = (
        SpecialistTechnologyInline,
        SpecialistProjectMembershipInline,
        SpecialistApplicationInline,
        SpecialistInvitationInline,
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

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """
        Возвращает queryset с нужными фильтрами и оптимизациями.
        Args:
            request: HTTP-запрос текущего пользователя
        """
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
                    filter=Q(
                        project_memberships__status=ProjectMembership.Status.ACTIVE
                    ),
                    distinct=True,
                ),
                applications_count=Count("applications", distinct=True),
                invitations_count=Count("invitations", distinct=True),
            )
        )

    def save_model(
        self, request: HttpRequest, obj: object, form: object, change: bool
    ) -> object:
        """
        Сохраняет модель в административном интерфейсе.
        Args:
            request: HTTP-запрос текущего пользователя
            obj: Объект модели
            form: Форма с проверенными данными
            change: Признак редактирования существующего объекта
        """
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description=_("Специалист"))
    def display_name(self, obj: SpecialistProfile) -> str:
        """
        Возвращает значение для отображения в интерфейсе администратора.
        Args:
            obj: Объект модели
        """
        return obj.get_display_name()

    @admin.display(description=_("Технологий"))
    def display_technology_count(self, obj: SpecialistProfile) -> int:
        """
        Возвращает значение для отображения в интерфейсе администратора.
        Args:
            obj: Объект модели
        """
        return getattr(obj, "technologies_count", obj.technologies.count())

    @admin.display(description=_("Активных проектов"))
    def display_active_projects_count(self, obj: SpecialistProfile) -> int:
        """
        Возвращает значение для отображения в интерфейсе администратора.
        Args:
            obj: Объект модели
        """
        return getattr(obj, "active_projects_count", obj.project_memberships.count())

    @admin.display(description=_("Откликов"))
    def display_applications_count(self, obj: SpecialistProfile) -> int:
        """
        Возвращает значение для отображения в интерфейсе администратора.
        Args:
            obj: Объект модели
        """
        return getattr(obj, "applications_count", obj.applications.count())

    @admin.display(description=_("Приглашений"))
    def display_invitations_count(self, obj: SpecialistProfile) -> int:
        """
        Возвращает значение для отображения в интерфейсе администратора.
        Args:
            obj: Объект модели
        """
        return getattr(obj, "invitations_count", obj.invitations.count())

    @admin.display(boolean=True, description=_("Доступен"))
    def display_is_available(self, obj: SpecialistProfile) -> bool:
        """
        Возвращает значение для отображения в интерфейсе администратора.
        Args:
            obj: Объект модели
        """
        return obj.is_available_for_project()

    @admin.display(description=_("Предпросмотр аватара"))
    def display_avatar_preview(self, obj: SpecialistProfile) -> str:
        """
        Возвращает значение для отображения в интерфейсе администратора.
        Args:
            obj: Объект модели
        """
        if obj and obj.avatar:
            return format_html(
                '<img src="{}" style="max-height: 120px; border-radius: 8px;" />',
                obj.avatar.url,
            )
        return _("Аватар не загружен")

    @admin.action(description=_("Установить статус «Ищу проект»"))
    def mark_as_looking(self, request: HttpRequest, queryset: QuerySet) -> object:
        """
        Выполняет логику функции.
        Args:
            request: HTTP-запрос текущего пользователя
            queryset: Набор объектов для обработки
        """
        updated_count = queryset.update(
            status=SpecialistProfile.AvailabilityStatus.LOOKING
        )
        self.message_user(
            request,
            _("Обновлено профилей: %(count)s") % {"count": updated_count},
        )

    @admin.action(description=_("Установить статус «Открыт к предложениям»"))
    def mark_as_open(self, request: HttpRequest, queryset: QuerySet) -> object:
        """
        Выполняет логику функции.
        Args:
            request: HTTP-запрос текущего пользователя
            queryset: Набор объектов для обработки
        """
        updated_count = queryset.update(
            status=SpecialistProfile.AvailabilityStatus.OPEN
        )
        self.message_user(
            request,
            _("Обновлено профилей: %(count)s") % {"count": updated_count},
        )

    @admin.action(description=_("Установить статус «Занят»"))
    def mark_as_busy(self, request: HttpRequest, queryset: QuerySet) -> object:
        """
        Выполняет логику функции.
        Args:
            request: HTTP-запрос текущего пользователя
            queryset: Набор объектов для обработки
        """
        updated_count = queryset.update(
            status=SpecialistProfile.AvailabilityStatus.BUSY
        )
        self.message_user(
            request,
            _("Обновлено профилей: %(count)s") % {"count": updated_count},
        )


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
