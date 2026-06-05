from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request

from apps.accounts.models import User


def is_admin(user: User | None) -> bool:
    """
    Проверяет, является ли пользователь администратором.
    Args:
        user: Объект пользователя
    """
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


class IsAdminOrReadOnly(BasePermission):
    """Allows public reads, but restricts writes to staff users."""

    def has_permission(self, request: Request, view: object) -> bool:
        """
        Проверяет доступ к действию без привязки к объекту.
        Args:
            request: HTTP-запрос текущего пользователя
            view: Значение параметра `view`
        """
        if request.method in SAFE_METHODS:
            return True

        return is_admin(request.user)


class IsProjectOwnerOrAdmin(BasePermission):
    """Allows object writes only to project owners and staff users."""

    def has_object_permission(self, request: Request, view: object, obj: object) -> bool:
        """
        Проверяет доступ к конкретному объекту.
        Args:
            request: HTTP-запрос текущего пользователя
            view: Значение параметра `view`
            obj: Объект модели
        """
        if request.method in SAFE_METHODS:
            return True

        if is_admin(request.user):
            return True

        project = getattr(obj, "project", obj)
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(project, "owner_id", None) == request.user.id
        )


class IsSpecialistOwnerOrAdmin(BasePermission):
    """Allows profile writes only to the profile owner and staff users."""

    def has_object_permission(self, request: Request, view: object, obj: object) -> bool:
        """
        Проверяет доступ к конкретному объекту.
        Args:
            request: HTTP-запрос текущего пользователя
            view: Значение параметра `view`
            obj: Объект модели
        """
        if request.method in SAFE_METHODS:
            return True

        return bool(
            is_admin(request.user)
            or (
                request.user
                and request.user.is_authenticated
                and getattr(obj, "user_id", None) == request.user.id
            )
        )


class IsApplicationReviewer(BasePermission):
    """Allows accepting or rejecting an application by project owner or staff."""

    def has_object_permission(self, request: Request, view: object, obj: object) -> bool:
        """
        Проверяет доступ к конкретному объекту.
        Args:
            request: HTTP-запрос текущего пользователя
            view: Значение параметра `view`
            obj: Объект модели
        """
        return bool(
            is_admin(request.user)
            or (
                request.user
                and request.user.is_authenticated
                and obj.project.owner_id == request.user.id
            )
        )


class IsInvitationRecipientOrAdmin(BasePermission):
    """Allows invitation responses by the invited specialist or staff."""

    def has_object_permission(self, request: Request, view: object, obj: object) -> bool:
        """
        Проверяет доступ к конкретному объекту.
        Args:
            request: HTTP-запрос текущего пользователя
            view: Значение параметра `view`
            obj: Объект модели
        """
        return bool(
            is_admin(request.user)
            or (
                request.user
                and request.user.is_authenticated
                and obj.specialist.user_id == request.user.id
            )
        )


class IsFavoriteOwner(BasePermission):
    """Allows users to manage only their own favorite projects."""

    def has_object_permission(self, request: Request, view: object, obj: object) -> bool:
        """
        Проверяет доступ к конкретному объекту.
        Args:
            request: HTTP-запрос текущего пользователя
            view: Значение параметра `view`
            obj: Объект модели
        """
        return bool(
            request.user
            and request.user.is_authenticated
            and obj.user_id == request.user.id
        )
