from __future__ import annotations

from django.contrib import admin

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _
from import_export.admin import ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from .models import Review


@admin.register(Review)
class ReviewAdmin(ImportExportModelAdmin, SimpleHistoryAdmin):
    """Админ-панель отзывов."""

    list_display = (
        "project",
        "specialist",
        "author",
        "rating",
        "status",
        "display_short_text",
        "display_is_public",
        "created_at",
        "updated_at",
    )
    list_display_links = (
        "project",
        "specialist",
    )
    list_filter = (
        "status",
        "rating",
        "project__status",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "text",
        "project__title",
        "author__username",
        "author__email",
        "specialist__user__username",
        "specialist__user__email",
        "specialist__user__first_name",
        "specialist__user__last_name",
    )
    raw_id_fields = (
        "project",
        "author",
        "specialist",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "display_short_text",
        "display_is_public",
    )
    date_hierarchy = "created_at"
    actions = (
        "publish_reviews",
        "hide_reviews",
        "reject_reviews",
    )

    fieldsets = (
        (
            _("Связи"),
            {
                "fields": (
                    "project",
                    "author",
                    "specialist",
                ),
            },
        ),
        (
            _("Содержание отзыва"),
            {
                "fields": (
                    "rating",
                    "text",
                    "status",
                ),
            },
        ),
        (
            _("Предпросмотр"),
            {
                "fields": (
                    "display_short_text",
                    "display_is_public",
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

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """
        Возвращает queryset с нужными фильтрами и оптимизациями.
        Args:
            request: HTTP-запрос текущего пользователя
        """
        queryset = super().get_queryset(request)
        return queryset.select_related(
            "project",
            "author",
            "specialist",
            "specialist__user",
        )

    def display_short_text(self, obj: Review) -> str:
        """
        Возвращает значение для отображения в интерфейсе администратора.
        Args:
            obj: Объект модели
        """
        if not obj.text:
            return "—"

        if len(obj.text) <= 80:
            return obj.text

        return f"{obj.text[:80]}..."

    display_short_text.short_description = _("Краткий текст")

    @admin.display(boolean=True, description=_("Опубликован"))
    def display_is_public(self, obj: Review) -> bool:
        """
        Возвращает значение для отображения в интерфейсе администратора.
        Args:
            obj: Объект модели
        """
        return obj.is_public()

    @admin.action(description=_("Опубликовать выбранные отзывы"))
    def publish_reviews(self, request: HttpRequest, queryset: QuerySet) -> object:
        """
        Выполняет логику функции.
        Args:
            request: HTTP-запрос текущего пользователя
            queryset: Набор объектов для обработки
        """
        published_count = 0

        for review in queryset:
            try:
                review.publish()
                published_count += 1
            except ValidationError as error:
                self.message_user(
                    request,
                    _("Отзыв «%(review)s» не опубликован: %(error)s")
                    % {"review": review, "error": error},
                    level=messages.ERROR,
                )

        self.message_user(
            request,
            _("Опубликовано отзывов: %(count)s") % {"count": published_count},
            level=messages.SUCCESS,
        )

    @admin.action(description=_("Скрыть выбранные отзывы"))
    def hide_reviews(self, request: HttpRequest, queryset: QuerySet) -> object:
        """
        Выполняет логику функции.
        Args:
            request: HTTP-запрос текущего пользователя
            queryset: Набор объектов для обработки
        """
        hidden_count = 0

        for review in queryset:
            review.hide()
            hidden_count += 1

        self.message_user(
            request,
            _("Скрыто отзывов: %(count)s") % {"count": hidden_count},
            level=messages.SUCCESS,
        )

    @admin.action(description=_("Отклонить выбранные отзывы"))
    def reject_reviews(self, request: HttpRequest, queryset: QuerySet) -> object:
        """
        Выполняет логику функции.
        Args:
            request: HTTP-запрос текущего пользователя
            queryset: Набор объектов для обработки
        """
        rejected_count = 0

        for review in queryset:
            review.reject()
            rejected_count += 1

        self.message_user(
            request,
            _("Отклонено отзывов: %(count)s") % {"count": rejected_count},
            level=messages.SUCCESS,
        )
