from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.interactions.forms import ApplicationForm, InvitationForm
from apps.interactions.models import Application, FavoriteProject, Invitation
from apps.projects.models import Project, ProjectMembership
from apps.specialists.models import SpecialistProfile


@login_required
def project_apply(request, slug):
    """Создание отклика специалиста на проект."""
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
def application_list(request):
    """Страница откликов: отправленные отклики и входящие отклики владельца."""
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


@login_required
def favorite_project_toggle(request, slug):
    """Добавляет проект в избранное или удаляет его при повторном действии."""
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
def favorite_project_list(request):
    """Список избранных проектов текущего пользователя."""
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


@login_required
def invite_specialist(request, pk):
    """Приглашение специалиста в один из проектов текущего пользователя."""
    specialist = get_object_or_404(
        SpecialistProfile.objects.select_related("user", "main_role").prefetch_related(
            "technologies"
        ),
        pk=pk,
    )

    if request.method == "POST":
        form = InvitationForm(
            request.POST,
            specialist=specialist,
            invited_by=request.user,
        )

        if form.is_valid():
            try:
                form.save()
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
def invitation_list(request):
    """Список приглашений: активные полученные и все отправленные."""
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
def invitation_accept(request, pk):
    """Принятие приглашения специалистом."""
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
        messages.error(request, "".join(error.message))
    except IntegrityError:
        messages.error(request, "Ты уже состоишь в команде этого проекта.")
    else:
        messages.success(request, "Приглашение принято. Ты добавлен в команду проекта.")

    return redirect("interactions:invitation_list")


@login_required
@require_POST
def invitation_decline(request, pk):
    """Отклонение приглашения специалистом."""
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


@login_required
@require_POST
def application_accept(request, pk):
    """Принятие отклика владельцем проекта."""
    application = get_object_or_404(
        Application.objects.select_related(
            "project",
            "vacancy",
            "vacancy__role",
            "specialist",
            "specialist__user",
        ),
        pk=pk,
        status=Application.Status.PENDING,
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
def application_reject(request, pk):
    """Отклонение отклика владельцем проекта."""
    application = get_object_or_404(
        Application.objects.select_related("project"),
        pk=pk,
        status=Application.Status.PENDING,
    )

    try:
        application.reject(reviewed_by=request.user)
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        messages.info(request, "Отклик отклонён.")

    return redirect("interactions:application_list")
