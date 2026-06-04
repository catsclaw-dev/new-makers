from rest_framework.permissions import SAFE_METHODS, BasePermission


def is_admin(user) -> bool:
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


class IsAdminOrReadOnly(BasePermission):
    """Allows public reads, but restricts writes to staff users."""

    def has_permission(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return True

        return is_admin(request.user)


class IsProjectOwnerOrAdmin(BasePermission):
    """Allows object writes only to project owners and staff users."""

    def has_object_permission(self, request, view, obj) -> bool:
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

    def has_object_permission(self, request, view, obj) -> bool:
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

    def has_object_permission(self, request, view, obj) -> bool:
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

    def has_object_permission(self, request, view, obj) -> bool:
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

    def has_object_permission(self, request, view, obj) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and obj.user_id == request.user.id
        )
