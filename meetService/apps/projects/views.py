from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import models, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render, redirect
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.http import Http404

from apps.directories.models import Role, Technology
from apps.interactions.models import FavoriteProject
from apps.projects.models import Project, ProjectMembership, ProjectVacancy
from apps.specialists.models import SpecialistProfile
from apps.projects.forms import ProjectForm, ProjectVacancyForm


def home(request):
    """Главная страница сервиса с поиском, виджетами и агрегатами."""
    query = request.GET.get("q", "").strip()

    projects = (
        Project.objects.published()
        .select_related("owner")
        .prefetch_related("technologies", "vacancies__role")
        .order_by("-created_at")
    )

    specialists = (
        SpecialistProfile.objects.select_related("user", "main_role")
        .prefetch_related("technologies")
        .filter(status=SpecialistProfile.AvailabilityStatus.LOOKING)
        .order_by("-created_at")
    )

    if query:
        projects = projects.filter(
            Q(title__icontains=query)
            | Q(short_description__icontains=query)
            | Q(description__icontains=query)
            | Q(technologies__name__icontains=query)
            | Q(vacancies__role__name__icontains=query)
        ).distinct()

        specialists = specialists.filter(
            Q(user__username__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(main_role__name__icontains=query)
            | Q(technologies__name__icontains=query)
            | Q(bio__icontains=query)
        ).distinct()

    new_projects_paginator = Paginator(projects, 3)

    urgent_projects_paginator = Paginator(
        Project.objects.urgent()
        .select_related("owner")
        .prefetch_related("technologies", "vacancies__role"),
        3,
    )

    new_page_number = request.GET.get("new_page", 1)
    urgent_page_number = request.GET.get("urgent_page", 1)

    try:
        new_projects_page = new_projects_paginator.page(new_page_number)
    except PageNotAnInteger:
        new_projects_page = new_projects_paginator.page(1)
    except EmptyPage:
        new_projects_page = new_projects_paginator.page(
            new_projects_paginator.num_pages
        )

    try:
        urgent_projects_page = urgent_projects_paginator.page(urgent_page_number)
    except PageNotAnInteger:
        urgent_projects_page = urgent_projects_paginator.page(1)
    except EmptyPage:
        urgent_projects_page = urgent_projects_paginator.page(
            urgent_projects_paginator.num_pages
        )

    active_specialists = specialists[:6]

    popular_technologies = (
        Technology.objects.filter(is_active=True)
        .annotate(project_count=Count("projects"))
        .order_by("-project_count", "name")[:10]
    )

    statistics = {
        "published_projects_count": Project.objects.published().count(),
        "specialists_count": SpecialistProfile.objects.count(),
        "roles_count": Role.objects.filter(is_active=True).count(),
        "technologies_count": Technology.objects.filter(is_active=True).count(),
    }

    context = {
        "query": query,
        "new_projects_page": new_projects_page,
        "urgent_projects_page": urgent_projects_page,
        "active_specialists": active_specialists,
        "popular_technologies": popular_technologies,
        "statistics": statistics,
    }
    return render(request, "projects/home.html", context)


def project_list(request):
    """Каталог проектов с поиском, фильтрацией, сортировкой и пагинацией."""
    query = request.GET.get("q", "").strip()
    technology_slug = request.GET.get("technology", "").strip()
    role_slug = request.GET.get("role", "").strip()
    ordering = request.GET.get("ordering", "-created_at").strip()

    allowed_ordering = {
        "-created_at": "-created_at",
        "created_at": "created_at",
        "title": "title",
        "-title": "-title",
    }

    projects = (
        Project.objects.published()
        .select_related("owner")
        .prefetch_related("technologies", "vacancies__role")
    )

    if query:
        projects = projects.filter(
            Q(title__icontains=query)
            | Q(short_description__icontains=query)
            | Q(description__icontains=query)
            | Q(goal__icontains=query)
            | Q(technologies__name__icontains=query)
            | Q(vacancies__role__name__icontains=query)
        ).distinct()

    if technology_slug:
        projects = projects.filter(technologies__slug=technology_slug)

    if role_slug:
        projects = projects.filter(vacancies__role__slug=role_slug)

    projects = projects.exclude(status=Project.Status.ARCHIVED)
    projects = projects.order_by(allowed_ordering.get(ordering, "-created_at"))

    paginator = Paginator(projects, 6)
    page_number = request.GET.get("page", 1)

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    technologies = Technology.objects.filter(is_active=True).order_by("name")
    roles = Role.objects.filter(is_active=True).order_by("name")

    context = {
        "page_obj": page_obj,
        "query": query,
        "technology_slug": technology_slug,
        "role_slug": role_slug,
        "ordering": ordering,
        "technologies": technologies,
        "roles": roles,
    }
    return render(request, "projects/project_list.html", context)


def project_detail(request, slug):
    """Детальная страница проекта.

    Опубликованные проекты видят все.
    Черновики, архивные и закрытые проекты видит только владелец или администратор.
    """
    project = get_object_or_404(
        Project.objects.select_related("owner").prefetch_related(
            "technologies",
            "vacancies__role",
            "memberships__specialist__user",
            "memberships__role",
            "files",
        ),
        slug=slug,
    )

    if project.status != Project.Status.PUBLISHED:
        if not project.can_be_edited_by(request.user):
            raise Http404("Проект не найден.")

    technology_ids = project.technologies.values_list("id", flat=True)

    similar_projects = (
        Project.objects.published()
        .filter(technologies__id__in=technology_ids)
        .exclude(pk=project.pk)
        .distinct()
        .prefetch_related("technologies")
        .order_by("-created_at")[:3]
    )

    open_vacancies = project.vacancies.filter(
        status=ProjectVacancy.Status.OPEN,
        current_count__lt=models.F("required_count"),
    ).select_related("role")

    memberships = project.memberships.select_related("specialist__user", "role")
    files = project.files.all()

    is_favorite = False
    is_team_member = False
    can_manage_project = project.can_be_edited_by(request.user)

    if request.user.is_authenticated:
        is_favorite = FavoriteProject.objects.filter(
            user=request.user,
            project=project,
        ).exists()

        specialist_profile = getattr(request.user, "specialist_profile", None)

        if specialist_profile is not None:
            is_team_member = ProjectMembership.objects.filter(
                project=project,
                specialist=specialist_profile,
                status=ProjectMembership.Status.ACTIVE,
            ).exists()

    context = {
        "project": project,
        "open_vacancies": open_vacancies,
        "memberships": memberships,
        "files": files,
        "similar_projects": similar_projects,
        "is_favorite": is_favorite,
        "is_team_member": is_team_member,
        "can_manage_project": can_manage_project,
    }
    return render(request, "projects/project_detail.html", context)


@login_required
def my_projects(request):
    """Проекты, которыми владеет текущий пользователь."""
    projects = (
        Project.objects.select_related("owner")
        .prefetch_related("technologies", "vacancies__role")
        .filter(owner=request.user)
        .order_by("-created_at")
    )

    context = {
        "projects": projects,
        "projects_count": projects.count(),
    }
    return render(request, "projects/my_projects.html", context)


@login_required
def my_teams(request):
    """Проекты, в командах которых состоит текущий специалист."""
    specialist_profile = getattr(request.user, "specialist_profile", None)

    memberships = ProjectMembership.objects.none()

    if specialist_profile is not None:
        memberships = (
            ProjectMembership.objects.select_related("project", "role")
            .prefetch_related("project__technologies")
            .filter(
                specialist=specialist_profile,
                status=ProjectMembership.Status.ACTIVE,
            )
            .order_by("-joined_at")
        )

    context = {
        "specialist_profile": specialist_profile,
        "memberships": memberships,
    }
    return render(request, "projects/my_teams.html", context)


@login_required
def project_create(request):
    """Создание нового проекта вместе с первой открытой ролью."""
    if request.method == "POST":
        form = ProjectForm(request.POST, request.FILES)
        vacancy_form = ProjectVacancyForm(request.POST)

        if form.is_valid() and vacancy_form.is_valid():
            with transaction.atomic():
                project = form.save(commit=False)
                project.owner = request.user
                project.status = Project.Status.DRAFT
                project.created_by = request.user
                project.updated_by = request.user
                project.save()

                form.save_technologies(project)

                vacancy = vacancy_form.save(commit=False)
                vacancy.project = project
                vacancy.status = ProjectVacancy.Status.OPEN
                vacancy.save()

            messages.success(
                request,
                "Проект создан как черновик. Первая открытая роль добавлена.",
            )
            return redirect(project.get_absolute_url())
    else:
        form = ProjectForm()
        vacancy_form = ProjectVacancyForm()

    context = {
        "form": form,
        "vacancy_form": vacancy_form,
        "page_title": "Создать проект",
        "submit_text": "Создать проект",
    }
    return render(request, "projects/project_form.html", context)


@login_required
def project_update(request, slug):
    """Редактирование проекта владельцем или администратором."""
    project = get_object_or_404(Project, slug=slug)

    if not project.can_be_edited_by(request.user):
        raise PermissionDenied(
            "Редактировать проект может только владелец или администратор."
        )

    if request.method == "POST":
        form = ProjectForm(request.POST, request.FILES, instance=project)

        if form.is_valid():
            project = form.save(commit=False)
            project.updated_by = request.user
            project.save()

            form.save_technologies(project)

            messages.success(request, "Проект обновлён.")
            return redirect(project.get_absolute_url())
    else:
        form = ProjectForm(instance=project)

    context = {
        "form": form,
        "project": project,
        "page_title": "Редактировать проект",
        "submit_text": "Сохранить изменения",
    }
    return render(request, "projects/project_form.html", context)


@login_required
def project_delete(request, slug):
    """Удаление проекта владельцем или администратором."""
    project = get_object_or_404(Project, slug=slug)

    if not project.can_be_edited_by(request.user):
        raise PermissionDenied(
            "Удалить проект может только владелец или администратор."
        )

    if request.method == "POST":
        project_title = project.title
        project.delete()

        messages.info(request, f"Проект «{project_title}» удалён.")
        return redirect("projects:my_projects")

    context = {
        "project": project,
    }
    return render(request, "projects/project_confirm_delete.html", context)


@login_required
def project_vacancy_create(request, slug):
    """Добавление открытой роли к проекту."""
    project = get_object_or_404(Project, slug=slug)

    if not project.can_be_edited_by(request.user):
        raise PermissionDenied(
            "Добавлять роли может только владелец проекта или администратор."
        )

    if request.method == "POST":
        form = ProjectVacancyForm(request.POST)

        if form.is_valid():
            vacancy = form.save(commit=False)
            vacancy.project = project
            vacancy.save()

            messages.success(request, "Открытая роль добавлена к проекту.")
            return redirect("projects:my_projects")
    else:
        form = ProjectVacancyForm()

    context = {
        "form": form,
        "project": project,
        "page_title": "Добавить открытую роль",
        "submit_text": "Добавить роль",
    }
    return render(request, "projects/vacancy_form.html", context)


@login_required
def project_submit_for_moderation(request, slug):
    """Отправляет черновик проекта на модерацию."""
    project = get_object_or_404(Project, slug=slug)

    if not project.can_be_edited_by(request.user):
        raise PermissionDenied(
            "Отправить проект на модерацию может только владелец или администратор."
        )

    if request.method != "POST":
        return redirect(project.get_absolute_url())

    if project.status != Project.Status.DRAFT:
        messages.error(request, "На модерацию можно отправить только черновик.")
        return redirect(project.get_absolute_url())

    has_open_vacancies = ProjectVacancy.objects.filter(
        project=project,
        status=ProjectVacancy.Status.OPEN,
        current_count__lt=models.F("required_count"),
    ).exists()

    if not has_open_vacancies:
        messages.error(
            request,
            "Перед отправкой на модерацию добавь хотя бы одну открытую роль.",
        )
        return redirect(project.get_absolute_url())

    project.status = Project.Status.MODERATION
    project.updated_by = request.user
    project.save(update_fields=["status", "updated_by", "updated_at"])

    messages.success(request, "Проект отправлен на рассмотрение модератору.")
    return redirect(project.get_absolute_url())
