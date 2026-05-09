from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from apps.interactions.forms import ApplicationForm
from apps.interactions.models import Application, FavoriteProject
from apps.projects.models import Project
from apps.specialists.models import SpecialistProfile


@login_required
def project_apply(request, slug):
    """Создание отклика специалиста на проект."""
    project = get_object_or_404(
        Project.objects.published()
        .select_related("owner")
        .prefetch_related("vacancies__role"),
        slug=slug,
    )

    try:
        specialist = request.user.specialist_profile
    except SpecialistProfile.DoesNotExist:
        messages.error(
            request,
            "Чтобы откликнуться на проект, сначала нужен профиль специалиста.",
        )
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
    """Страница откликов: отправленные отклики и отклики на проекты пользователя."""
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
        .filter(project__owner=request.user)
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
    project = get_object_or_404(Project.objects.published(), slug=slug)

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
