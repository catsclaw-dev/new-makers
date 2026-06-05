from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.accounts.forms import RegisterForm
from apps.interactions.models import Application, FavoriteProject, Invitation
from apps.projects.models import Project, ProjectMembership


def register(request: HttpRequest) -> HttpResponse:
    """
    Регистрация нового пользователя.
    Args:
        request: HTTP-запрос текущего пользователя
    """
    if request.user.is_authenticated:
        return redirect("accounts:profile")

    if request.method == "POST":
        form = RegisterForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Регистрация завершена.")
            return redirect("accounts:profile")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})


class AccountLoginView(LoginView):
    """Страница входа пользователя."""

    template_name = "accounts/login.html"
    redirect_authenticated_user = True


class AccountLogoutView(LogoutView):
    """Выход пользователя."""

    next_page = "projects:home"


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    """
    Личный кабинет пользователя с динамическим определением роли.
    Args:
        request: HTTP-запрос текущего пользователя
    """
    user = request.user

    owned_projects_queryset = Project.objects.filter(owner=user)
    active_owned_projects_queryset = owned_projects_queryset.exclude(
        status=Project.Status.ARCHIVED
    )

    is_project_owner = (
        user.is_staff or user.is_superuser or active_owned_projects_queryset.exists()
    )

    specialist_profile = getattr(user, "specialist_profile", None)
    is_specialist = specialist_profile is not None or not is_project_owner

    dynamic_role_display = (
        "Администратор"
        if user.is_staff or user.is_superuser
        else "Владелец проекта"
        if is_project_owner
        else "Специалист"
    )

    owned_projects = active_owned_projects_queryset.order_by("-created_at")[:5]

    team_memberships = ProjectMembership.objects.none()

    sent_applications_queryset = Application.objects.none()
    received_invitations_queryset = Invitation.objects.none()

    sent_applications_count = 0
    received_invitations_count = 0

    if specialist_profile is not None:
        team_memberships = (
            ProjectMembership.objects.select_related("project", "role")
            .filter(
                specialist=specialist_profile,
                status=ProjectMembership.Status.ACTIVE,
            )
            .exclude(project__status=Project.Status.ARCHIVED)
            .order_by("-joined_at")[:5]
        )

        sent_applications_queryset = (
            Application.objects.select_related(
                "project",
                "vacancy",
                "vacancy__role",
            )
            .filter(specialist=specialist_profile)
            .order_by("-applied_at")
        )

        sent_applications_count = sent_applications_queryset.count()

        received_invitations_queryset = (
            Invitation.objects.select_related(
                "project",
                "vacancy",
                "vacancy__role",
                "invited_by",
            )
            .filter(
                specialist=specialist_profile,
                status=Invitation.Status.PENDING,
            )
            .order_by("-invited_at")
        )

        received_invitations_count = received_invitations_queryset.count()

    incoming_applications_queryset = (
        Application.objects.select_related(
            "project",
            "vacancy",
            "vacancy__role",
            "specialist",
            "specialist__user",
        )
        .filter(
            project__owner=user,
            status=Application.Status.PENDING,
        )
        .order_by("-applied_at")
    )

    context = {
        "dynamic_role_display": dynamic_role_display,
        "is_project_owner": is_project_owner,
        "is_specialist": is_specialist,
        "specialist_profile": specialist_profile,
        "owned_projects": owned_projects,
        "owned_projects_count": active_owned_projects_queryset.count(),
        "archived_owned_projects_count": owned_projects_queryset.filter(
            status=Project.Status.ARCHIVED
        ).count(),
        "team_memberships": team_memberships,
        "team_memberships_count": team_memberships.count(),
        "sent_applications_count": sent_applications_count,
        "incoming_applications_count": incoming_applications_queryset.count(),
        "recent_sent_applications": sent_applications_queryset[:3],
        "recent_received_invitations": received_invitations_queryset[:3],
        "recent_incoming_applications": incoming_applications_queryset[:3],
        "received_invitations_count": received_invitations_count,
        "sent_invitations_count": Invitation.objects.filter(invited_by=user).count(),
        "favorites_count": FavoriteProject.objects.filter(user=user).count(),
    }
    return render(request, "accounts/profile.html", context)
