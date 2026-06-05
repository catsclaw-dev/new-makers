from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.interactions.forms import ApplicationForm, InvitationForm
from apps.interactions.models import Application, FavoriteProject, Invitation
from apps.projects.models import Project, ProjectMembership, ProjectVacancy
from apps.specialists.models import SpecialistProfile


@login_required
def project_apply(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Создание отклика специалиста на проект.
    Args:
        request: HTTP-запрос текущего пользователя
        slug: URL-идентификатор объекта
    """
    project = get_object_or_404(
        Project.objects.select_related("owner").prefetch_related("vacancies__role"),
        slug=slug,
        status=Project.Status.PUBLISHED,
    )
    try:
        specialist = request.user.specialist_profile
    except SpecialistProfile.DoesNotExist:
        messages.error(
            request,
            "Чтобы откликнуться на проект, сначала нужен профиль специалиста.",
        )
        return redirect(project.get_absolute_url())

    already_member = ProjectMembership.objects.filter(
        project=project,
        specialist=specialist,
        status=ProjectMembership.Status.ACTIVE,
    ).exists()

    if already_member:
        messages.info(request, "Ты уже состоишь в команде этого проекта.")
        return redirect(project.get_absolute_url())

    if request.method == "POST":
        form = ApplicationForm(
            request.POST,
            project=project,
            specialist=specialist,
        )

        if form.is_valid():
            try:
                form.save()
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, "Отклик отправлен владельцу проекта.")
                return redirect("interactions:application_list")
    else:
        form = ApplicationForm(project=project, specialist=specialist)

    context = {
        "project": project,
        "form": form,
    }
    return render(request, "interactions/project_apply.html", context)


@login_required
def application_list(request: HttpRequest) -> HttpResponse:
    """
    Страница откликов: отправленные отклики и входящие отклики владельца.
    Args:
        request: HTTP-запрос текущего пользователя
    """
    try:
        specialist = request.user.specialist_profile
    except SpecialistProfile.DoesNotExist:
        specialist = None

    sent_applications = Application.objects.none()

    if specialist is not None:
        sent_applications = (
            Application.objects.select_related(
                "project",
                "vacancy",
                "vacancy__role",
            )
            .filter(specialist=specialist)
            .order_by("-applied_at")
        )

    incoming_applications = (
        Application.objects.select_related(
            "project",
            "vacancy",
            "vacancy__role",
            "specialist",
            "specialist__user",
        )
        .filter(
            project__owner=request.user,
            status=Application.Status.PENDING,
        )
        .order_by("-applied_at")
    )

    context = {
        "specialist": specialist,
        "sent_applications": sent_applications,
        "incoming_applications": incoming_applications,
        "sent_count": sent_applications.count(),
        "incoming_count": incoming_applications.count(),
    }
    return render(request, "interactions/application_list.html", context)


@require_POST
@login_required
def favorite_project_toggle(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Добавляет проект в избранное или удаляет его при повторном действии.
    Args:
        request: HTTP-запрос текущего пользователя
        slug: URL-идентификатор объекта
    """
    project = get_object_or_404(
        Project.objects.filter(
            status__in=[
                Project.Status.PUBLISHED,
                Project.Status.CLOSED,
            ]
        ),
        slug=slug,
    )

    favorite = FavoriteProject.objects.filter(
        user=request.user,
        project=project,
    ).first()

    if favorite:
        favorite.delete()
        messages.info(request, "Проект удалён из избранного.")
    else:
        FavoriteProject.objects.create(
            user=request.user,
            project=project,
        )
        messages.success(request, "Проект добавлен в избранное.")

    return redirect(project.get_absolute_url())


@login_required
def favorite_project_list(request: HttpRequest) -> HttpResponse:
    """
    Список избранных проектов текущего пользователя.
    Args:
        request: HTTP-запрос текущего пользователя
    """
    favorites = (
        FavoriteProject.objects.select_related("project", "project__owner")
        .prefetch_related("project__technologies", "project__vacancies__role")
        .filter(user=request.user)
        .order_by("-pk")
    )

    context = {
        "favorites": favorites,
    }
    return render(request, "interactions/favorite_project_list.html", context)


def user_has_project_for_invitation(user: User | None) -> bool:
    """
    Проверяет, есть ли у пользователя опубликованный проект с открытыми ролями.
    Args:
        user: Объект пользователя
    """
    if user.is_staff or user.is_superuser:
        return Project.objects.filter(
            status=Project.Status.PUBLISHED,
            vacancies__status=ProjectVacancy.Status.OPEN,
            vacancies__current_count__lt=models.F("vacancies__required_count"),
        ).exists()

    return Project.objects.filter(
        owner=user,
        status=Project.Status.PUBLISHED,
        vacancies__status=ProjectVacancy.Status.OPEN,
        vacancies__current_count__lt=models.F("vacancies__required_count"),
    ).exists()


@login_required
def invite_specialist(request: HttpRequest, pk: int | None) -> HttpResponse:
    """
    Приглашение специалиста в опубликованный проект текущего пользователя.
    Args:
        request: HTTP-запрос текущего пользователя
        pk: Идентификатор объекта
    """
    specialist = get_object_or_404(
        SpecialistProfile.objects.select_related("user", "main_role").prefetch_related(
            "technologies"
        ),
        pk=pk,
    )

    if specialist.user == request.user:
        messages.error(request, "Нельзя пригласить самого себя в свой проект.")
        return redirect(specialist.get_absolute_url())

    if not user_has_project_for_invitation(request.user):
        messages.error(
            request,
            "Для приглашения нужен опубликованный проект с открытой ролью.",
        )
        return redirect(specialist.get_absolute_url())

    if request.method == "POST":
        form = InvitationForm(
            request.POST,
            specialist=specialist,
            invited_by=request.user,
        )

        if form.is_valid():
            invitation = form.save(commit=False)

            if not request.user.is_staff and not request.user.is_superuser:
                if invitation.project.owner != request.user:
                    form.add_error(
                        "project",
                        "Можно приглашать только в свои проекты.",
                    )
                    return render(
                        request,
                        "interactions/invite_specialist.html",
                        {
                            "specialist": specialist,
                            "form": form,
                        },
                    )

            if invitation.project.status != Project.Status.PUBLISHED:
                form.add_error(
                    "project",
                    "Приглашать можно только в опубликованный проект.",
                )
                return render(
                    request,
                    "interactions/invite_specialist.html",
                    {
                        "specialist": specialist,
                        "form": form,
                    },
                )

            if not invitation.vacancy.is_open():
                form.add_error(
                    "vacancy",
                    "Приглашать можно только на открытую роль.",
                )
                return render(
                    request,
                    "interactions/invite_specialist.html",
                    {
                        "specialist": specialist,
                        "form": form,
                    },
                )

            already_member = ProjectMembership.objects.filter(
                project=invitation.project,
                specialist=specialist,
                status=ProjectMembership.Status.ACTIVE,
            ).exists()

            if already_member:
                form.add_error(
                    None,
                    "Специалист уже состоит в команде этого проекта.",
                )
                return render(
                    request,
                    "interactions/invite_specialist.html",
                    {
                        "specialist": specialist,
                        "form": form,
                    },
                )

            try:
                invitation.save()
            except ValidationError as error:
                form.add_error(None, error)
            except IntegrityError:
                form.add_error(
                    None,
                    "Такое активное приглашение уже существует.",
                )
            else:
                messages.success(request, "Приглашение отправлено специалисту.")
                return redirect("interactions:invitation_list")
    else:
        form = InvitationForm(
            specialist=specialist,
            invited_by=request.user,
        )

    context = {
        "specialist": specialist,
        "form": form,
    }
    return render(request, "interactions/invite_specialist.html", context)


@login_required
def invitation_list(request: HttpRequest) -> HttpResponse:
    """
    Список приглашений: активные полученные и все отправленные.
    Args:
        request: HTTP-запрос текущего пользователя
    """
    try:
        specialist = request.user.specialist_profile
    except SpecialistProfile.DoesNotExist:
        specialist = None

    received_invitations = Invitation.objects.none()

    if specialist is not None:
        received_invitations = (
            Invitation.objects.select_related(
                "project",
                "vacancy",
                "vacancy__role",
                "invited_by",
            )
            .filter(
                specialist=specialist,
                status=Invitation.Status.PENDING,
            )
            .order_by("-invited_at")
        )

    sent_invitations = (
        Invitation.objects.select_related(
            "project",
            "vacancy",
            "vacancy__role",
            "specialist",
            "specialist__user",
        )
        .filter(invited_by=request.user)
        .order_by("-invited_at")
    )

    context = {
        "specialist": specialist,
        "received_invitations": received_invitations,
        "sent_invitations": sent_invitations,
        "received_count": received_invitations.count(),
        "sent_count": sent_invitations.count(),
    }
    return render(request, "interactions/invitation_list.html", context)


@login_required
@require_POST
def invitation_accept(request: HttpRequest, pk: int | None) -> HttpResponse:
    """
    Принятие приглашения специалистом.
    Args:
        request: HTTP-запрос текущего пользователя
        pk: Идентификатор объекта
    """
    invitation = get_object_or_404(
        Invitation.objects.select_related(
            "project",
            "vacancy",
            "vacancy__role",
            "specialist",
            "specialist__user",
            "invited_by",
        ),
        pk=pk,
        specialist__user=request.user,
        status=Invitation.Status.PENDING,
    )

    try:
        invitation.accept()
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    except IntegrityError:
        messages.error(request, "Ты уже состоишь в команде этого проекта.")
    else:
        messages.success(request, "Приглашение принято. Ты добавлен в команду проекта.")

    return redirect("interactions:invitation_list")


@login_required
@require_POST
def invitation_decline(request: HttpRequest, pk: int | None) -> HttpResponse:
    """
    Отклонение приглашения специалистом.
    Args:
        request: HTTP-запрос текущего пользователя
        pk: Идентификатор объекта
    """
    invitation = get_object_or_404(
        Invitation,
        pk=pk,
        specialist__user=request.user,
        status=Invitation.Status.PENDING,
    )

    try:
        invitation.decline()
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        messages.info(request, "Приглашение отклонено.")

    return redirect("interactions:invitation_list")


def get_applications_available_for_review(user: User | None) -> QuerySet:
    """
    Возвращает отклики, которые пользователь может принять или отклонить.
    Args:
        user: Объект пользователя
    """
    applications = Application.objects.select_related(
        "project",
        "vacancy",
        "vacancy__role",
        "specialist",
        "specialist__user",
    ).filter(
        status=Application.Status.PENDING,
    )

    if user.is_staff or user.is_superuser:
        return applications

    return applications.filter(project__owner=user)


@login_required
@require_POST
def application_accept(request: HttpRequest, pk: int | None) -> HttpResponse:
    """
    Принятие отклика владельцем проекта или администратором.
    Args:
        request: HTTP-запрос текущего пользователя
        pk: Идентификатор объекта
    """
    application = get_object_or_404(
        get_applications_available_for_review(request.user),
        pk=pk,
    )

    try:
        application.accept(reviewed_by=request.user)
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    except IntegrityError:
        messages.error(request, "Специалист уже состоит в команде проекта.")
    else:
        messages.success(
            request,
            "Отклик принят. Специалист добавлен в команду проекта.",
        )

    return redirect("interactions:application_list")


@login_required
@require_POST
def application_reject(request: HttpRequest, pk: int | None) -> HttpResponse:
    """
    Отклонение отклика владельцем проекта или администратором.
    Args:
        request: HTTP-запрос текущего пользователя
        pk: Идентификатор объекта
    """
    application = get_object_or_404(
        get_applications_available_for_review(request.user),
        pk=pk,
    )

    try:
        application.reject(reviewed_by=request.user)
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        messages.info(request, "Отклик отклонён.")

    return redirect("interactions:application_list")
