from __future__ import annotations

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _
from import_export.admin import ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from .models import Application, FavoriteProject, Invitation


@admin.register(Application)
class ApplicationAdmin(ImportExportModelAdmin, SimpleHistoryAdmin):
    """Админ-панель откликов."""

    list_display = (
        "specialist",
        "project",
        "vacancy",
        "status",
        "applied_at",
        "reviewed_at",
        "reviewed_by",
        "display_project_owner",
        "display_is_active",
    )
    list_display_links = (
        "specialist",
        "project",
    )
    list_filter = (
        "status",
        "project__status",
        "vacancy__role",
        "applied_at",
        "reviewed_at",
    )
    search_fields = (
        "message",
        "project__title",
        "vacancy__title",
        "specialist__user__username",
        "specialist__user__email",
        "specialist__user__first_name",
        "specialist__user__last_name",
        "reviewed_by__username",
        "reviewed_by__email",
    )
    raw_id_fields = (
        "project",
        "vacancy",
        "specialist",
        "reviewed_by",
    )
    readonly_fields = (
        "applied_at",
        "reviewed_at",
    )
    date_hierarchy = "applied_at"
    actions = (
        "accept_applications",
        "reject_applications",
    )

    fieldsets = (
        (
            _("Отклик"),
            {
                "fields": (
                    "project",
                    "vacancy",
                    "specialist",
                    "message",
                    "status",
                ),
            },
        ),
        (
            _("Рассмотрение"),
            {
                "fields": (
                    "reviewed_at",
                    "reviewed_by",
                ),
            },
        ),
        (
            _("Служебная информация"),
            {
                "fields": ("applied_at",),
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
        return queryset.select_related(
            "project",
            "project__owner",
            "vacancy",
            "vacancy__role",
            "specialist",
            "specialist__user",
            "reviewed_by",
        )

    @admin.display(description="Владелец проекта")
    def display_project_owner(self, obj: Application) -> str:
        """
        Возвращает значение для отображения в интерфейсе администратора.
        Args:
            obj: Объект модели
        """
        return obj.project.owner

    @admin.display(boolean=True, description="Активный")
    def display_is_active(self, obj: Application) -> bool:
        """
        Возвращает значение для отображения в интерфейсе администратора.
        Args:
            obj: Объект модели
        """
        return obj.status in Application.ACTIVE_STATUSES

    @admin.action(description="Принять выбранные отклики")
    def accept_applications(self, request: HttpRequest, queryset: QuerySet) -> object:
        """
        Выполняет логику функции.
        Args:
            request: HTTP-запрос текущего пользователя
            queryset: Набор объектов для обработки
        """
        accepted_count = 0

        for application in queryset:
            try:
                application.accept(reviewed_by=request.user)
                accepted_count += 1
            except ValidationError as error:
                self.message_user(
                    request,
                    f"Отклик «{application}» не принят: {error}",
                    level=messages.ERROR,
                )

        self.message_user(
            request,
            f"Принято откликов: {accepted_count}",
            level=messages.SUCCESS,
        )

    @admin.action(description="Отклонить выбранные отклики")
    def reject_applications(self, request: HttpRequest, queryset: QuerySet) -> object:
        """
        Выполняет логику функции.
        Args:
            request: HTTP-запрос текущего пользователя
            queryset: Набор объектов для обработки
        """
        rejected_count = 0

        for application in queryset:
            application.reject(reviewed_by=request.user)
            rejected_count += 1

        self.message_user(
            request,
            f"Отклонено откликов: {rejected_count}",
            level=messages.SUCCESS,
        )


@admin.register(Invitation)
class InvitationAdmin(ImportExportModelAdmin, SimpleHistoryAdmin):
    """Админ-панель приглашений."""

    list_display = (
        "specialist",
        "project",
        "vacancy",
        "invited_by",
        "status",
        "invited_at",
        "responded_at",
        "display_is_pending",
    )
    list_display_links = (
        "specialist",
        "project",
    )
    list_filter = (
        "status",
        "project__status",
        "vacancy__role",
        "invited_at",
        "responded_at",
    )
    search_fields = (
        "message",
        "project__title",
        "vacancy__title",
        "specialist__user__username",
        "specialist__user__email",
        "specialist__user__first_name",
        "specialist__user__last_name",
        "invited_by__username",
        "invited_by__email",
    )
    raw_id_fields = (
        "project",
        "vacancy",
        "specialist",
        "invited_by",
    )
    readonly_fields = (
        "invited_at",
        "responded_at",
    )
    date_hierarchy = "invited_at"
    actions = (
        "accept_invitations",
        "decline_invitations",
    )

    fieldsets = (
        (
            _("Приглашение"),
            {
                "fields": (
                    "project",
                    "vacancy",
                    "specialist",
                    "invited_by",
                    "message",
                    "status",
                ),
            },
        ),
        (
            _("Даты"),
            {
                "fields": (
                    "invited_at",
                    "responded_at",
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
        return queryset.select_related(
            "project",
            "vacancy",
            "vacancy__role",
            "specialist",
            "specialist__user",
            "invited_by",
        )

    @admin.display(boolean=True, description="Ожидает ответа")
    def display_is_pending(self, obj: Invitation) -> bool:
        """
        Возвращает значение для отображения в интерфейсе администратора.
        Args:
            obj: Объект модели
        """
        return obj.status == Invitation.Status.PENDING

    @admin.action(description="Принять выбранные приглашения")
    def accept_invitations(self, request: HttpRequest, queryset: QuerySet) -> object:
        """
        Выполняет логику функции.
        Args:
            request: HTTP-запрос текущего пользователя
            queryset: Набор объектов для обработки
        """
        accepted_count = 0

        for invitation in queryset:
            try:
                invitation.accept()
                accepted_count += 1
            except ValidationError as error:
                self.message_user(
                    request,
                    f"Приглашение «{invitation}» не принято: {error}",
                    level=messages.ERROR,
                )

        self.message_user(
            request,
            f"Принято приглашений: {accepted_count}",
            level=messages.SUCCESS,
        )

    @admin.action(description="Отклонить выбранные приглашения")
    def decline_invitations(self, request: HttpRequest, queryset: QuerySet) -> object:
        """
        Выполняет логику функции.
        Args:
            request: HTTP-запрос текущего пользователя
            queryset: Набор объектов для обработки
        """
        declined_count = 0

        for invitation in queryset:
            invitation.decline()
            declined_count += 1

        self.message_user(
            request,
            f"Отклонено приглашений: {declined_count}",
            level=messages.SUCCESS,
        )


@admin.register(FavoriteProject)
class FavoriteProjectAdmin(ImportExportModelAdmin):
    """Админ-панель избранных проектов."""

    list_display = (
        "user",
        "project",
        "added_at",
        "display_project_status",
        "display_project_owner",
    )
    list_display_links = (
        "user",
        "project",
    )
    list_filter = (
        "project__status",
        "project__stage",
        "added_at",
    )
    search_fields = (
        "user__username",
        "user__email",
        "project__title",
        "project__short_description",
    )
    raw_id_fields = (
        "user",
        "project",
    )
    readonly_fields = ("added_at",)
    date_hierarchy = "added_at"

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """
        Возвращает queryset с нужными фильтрами и оптимизациями.
        Args:
            request: HTTP-запрос текущего пользователя
        """
        queryset = super().get_queryset(request)
        return queryset.select_related(
            "user",
            "project",
            "project__owner",
        )

    @admin.display(description="Статус проекта")
    def display_project_status(self, obj: FavoriteProject) -> str:
        """
        Возвращает значение для отображения в интерфейсе администратора.
        Args:
            obj: Объект модели
        """
        return obj.project.get_status_display()

    @admin.display(description="Владелец проекта")
    def display_project_owner(self, obj: FavoriteProject) -> str:
        """
        Возвращает значение для отображения в интерфейсе администратора.
        Args:
            obj: Объект модели
        """
        return obj.project.owner
