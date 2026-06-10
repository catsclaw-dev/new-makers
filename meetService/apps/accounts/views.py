from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from django.utils.translation import gettext_lazy as _

from allauth.account.models import EmailAddress

from apps.accounts.forms import (
    AccountEmailForm,
    RegisterForm,
    VerifiedEmailAuthenticationForm,
)
from apps.interactions.emails import enqueue_welcome_email
from apps.common_throttling import is_rate_limited, rate_limit
from apps.interactions.models import Application, FavoriteProject, Invitation
from apps.projects.models import Project, ProjectMembership


@rate_limit(scope="register", limit=10, window=60 * 60)
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
            with transaction.atomic():
                user = form.save()

                email_address, _created = EmailAddress.objects.get_or_create(
                    user=user,
                    email=user.email,
                    defaults={
                        "primary": True,
                        "verified": False,
                    },
                )

                if not email_address.primary:
                    EmailAddress.objects.filter(
                        user=user,
                        primary=True,
                    ).update(primary=False)

                    email_address.primary = True
                    email_address.save(update_fields=["primary"])

                email_address.send_confirmation(
                    request,
                    signup=True,
                )
                enqueue_welcome_email(user.pk)

            messages.success(
                request,
                _(
                    "Регистрация почти завершена. "
                    "Мы отправили письмо со ссылкой подтверждения email."
                ),
            )
            return redirect("accounts:login")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})


class AccountLoginView(LoginView):
    """Страница входа пользователя."""

    template_name = "accounts/login.html"
    authentication_form = VerifiedEmailAuthenticationForm
    redirect_authenticated_user = True

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        if is_rate_limited(request, scope="login", limit=5, window=60):
            return HttpResponse(
                _("Слишком много попыток входа. Повтори попытку через минуту."),
                status=429,
            )
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs: object) -> dict[str, Any]:
        """
        Добавляет признаки доступности OAuth2-провайдеров.
        Args:
            **kwargs: Именованные аргументы
        """
        context = super().get_context_data(**kwargs)
        context["github_oauth_enabled"] = bool(
            settings.GITHUB_OAUTH_CLIENT_ID and settings.GITHUB_OAUTH_CLIENT_SECRET
        )
        context["google_oauth_enabled"] = bool(
            settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET
        )
        return context


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
        _("Администратор")
        if user.is_staff or user.is_superuser
        else _("Владелец проекта")
        if is_project_owner
        else _("Специалист")
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
                status__in=[
                    ProjectMembership.Status.ACTIVE,
                    ProjectMembership.Status.PAUSED,
                ],
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
        "email_form": AccountEmailForm(instance=user),
        "show_email_required_notice": not user.email
        and not user.is_staff
        and not user.is_superuser,
    }
    return render(request, "accounts/profile.html", context)


@login_required
@require_POST
def update_email(request: HttpRequest) -> HttpResponse:
    """
    Обновляет email текущего пользователя.
    Args:
        request: HTTP-запрос текущего пользователя
    """
    form = AccountEmailForm(request.POST, instance=request.user)

    if form.is_valid():
        new_email = form.cleaned_data["email"]

        with transaction.atomic():
            user = form.save()
            email_address, _created = EmailAddress.objects.get_or_create(
                user=user,
                email=new_email,
                defaults={
                    "primary": True,
                    "verified": False,
                },
            )

            EmailAddress.objects.filter(user=user, primary=True).exclude(
                pk=email_address.pk
            ).update(primary=False)

            if not email_address.primary:
                email_address.primary = True
                email_address.save(update_fields=["primary"])

            if not email_address.verified:
                email_address.send_confirmation(request)

        if email_address.verified:
            messages.success(request, _("Email обновлён."))
            return redirect("accounts:profile")

        if not request.user.is_staff and not request.user.is_superuser:
            auth_logout(request)

        messages.success(
            request,
            _("Email обновлён. Подтверди новый адрес по ссылке из письма."),
        )

        if not request.user.is_authenticated:
            return redirect("accounts:login")
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)

    return redirect("accounts:profile")
