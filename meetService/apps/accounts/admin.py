from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Админ-панель для кастомной модели пользователя."""

    list_display = (
        "username",
        "email",
        "role",
        "is_staff",
        "is_active",
        "date_joined",
        "display_full_name",
    )
    list_display_links = ("username", "email")
    list_filter = (
        "role",
        "is_staff",
        "is_superuser",
        "is_active",
        "groups",
        "date_joined",
    )
    search_fields = (
        "username",
        "email",
        "first_name",
        "last_name",
    )
    readonly_fields = (
        "last_login",
        "date_joined",
    )
    date_hierarchy = "date_joined"
    ordering = ("username",)

    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            _("Роль в сервисе"),
            {
                "fields": ("role",),
            },
        ),
    )

    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        (
            _("Роль в сервисе"),
            {
                "classes": ("wide",),
                "fields": ("role",),
            },
        ),
    )

    @admin.display(description=_("ФИО"))
    def display_full_name(self, obj: User) -> str:
        """
        Возвращает полное имя пользователя или прочерк.
        Args:
            obj: Объект модели
        """
        return obj.get_full_name() or "—"


# Register your models here.
