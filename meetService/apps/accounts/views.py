"""HTML-представления для регистрации, входа, выхода и профиля."""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render

from apps.accounts.forms import RegisterForm
from apps.accounts.models import User
from apps.interactions.models import Application, FavoriteProject, Invitation
from apps.projects.models import Project, ProjectMembership


def register(request):
    """Регистрация нового пользователя."""
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
def profile(request):
    """Личный кабинет пользователя с разделением по ролям."""
    user = request.user
    is_project_owner = user.role == User.UserRole.PROJECT_OWNER or user.is_staff
    is_specialist = user.role == User.UserRole.SPECIALIST

    specialist_profile = None

    if is_specialist:
        specialist_profile = getattr(user, "specialist_profile", None)

    owned_projects = Project.objects.filter(owner=user).order_by("-created_at")[:5]

    team_memberships = ProjectMembership.objects.none()
    sent_applications_count = 0
    received_invitations_count = 0

    if specialist_profile is not None:
        team_memberships = (
            ProjectMembership.objects.select_related("project", "role")
            .filter(
                specialist=specialist_profile,
                status=ProjectMembership.Status.ACTIVE,
            )
            .order_by("-joined_at")[:5]
        )

        sent_applications_count = Application.objects.filter(
            specialist=specialist_profile
        ).count()

        received_invitations_count = Invitation.objects.filter(
            specialist=specialist_profile,
            status=Invitation.Status.PENDING,
        ).count()

    context = {
        "is_project_owner": is_project_owner,
        "is_specialist": is_specialist,
        "specialist_profile": specialist_profile,
        "owned_projects": owned_projects,
        "owned_projects_count": Project.objects.filter(owner=user).count(),
        "team_memberships": team_memberships,
        "team_memberships_count": team_memberships.count(),
        "sent_applications_count": sent_applications_count,
        "incoming_applications_count": Application.objects.filter(
            project__owner=user,
            status=Application.Status.PENDING,
        ).count(),
        "received_invitations_count": received_invitations_count,
        "sent_invitations_count": Invitation.objects.filter(invited_by=user).count(),
        "favorites_count": FavoriteProject.objects.filter(user=user).count(),
    }
    return render(request, "accounts/profile.html", context)
