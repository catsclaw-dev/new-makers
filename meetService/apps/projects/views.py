from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import models, transaction
from django.db.models import Count, Q
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, render, redirect
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


from apps.directories.models import Role, Technology
from apps.interactions.models import FavoriteProject
from apps.projects.models import Project, ProjectMembership, ProjectVacancy
from apps.specialists.models import SpecialistProfile
from apps.projects.forms import (
    ProjectForm,
    ProjectVacancyForm,
    ProjectVacancyUpdateForm,
    ProjectMembershipUpdateForm,
)


def home(request: HttpRequest) -> HttpResponse:
    """
    Главная страница сервиса с поиском, виджетами и агрегаторными функциями.
    Args:
        request: HTTP-запрос текущего пользователя
    """
    query = request.GET.get("q", "").strip()

    viewed_project_ids = request.session.get("viewed_project_ids", [])
    viewed_projects_queryset = (
        Project.objects.published()
        .filter(pk__in=viewed_project_ids)
        .select_related("owner")
        .prefetch_related("technologies", "vacancies__role")
    )
    viewed_projects_by_id = {
        project.pk: project for project in viewed_projects_queryset
    }
    recently_viewed_projects = [
        viewed_projects_by_id[project_id]
        for project_id in viewed_project_ids
        if project_id in viewed_projects_by_id
    ]

    projects = (
        Project.objects.published()
        .select_related("owner")
        .prefetch_related("technologies", "vacancies__role")
        .order_by("-created_at")
    )

    specialists = (
        SpecialistProfile.objects.select_related("user", "main_role")
        .prefetch_related("technologies")
        .filter(
            status__in=[
                SpecialistProfile.AvailabilityStatus.LOOKING,
                SpecialistProfile.AvailabilityStatus.OPEN,
            ]
        )
        .order_by("-created_at")
    )

    open_vacancies = (
        ProjectVacancy.objects.select_related("project", "role")
        .prefetch_related("project__technologies")
        .filter(
            project__status=Project.Status.PUBLISHED,
            status=ProjectVacancy.Status.OPEN,
            current_count__lt=models.F("required_count"),
        )
        .order_by("-created_at")
    )

    if query:
        projects = projects.filter(
            Q(title__icontains=query)
            | Q(short_description__icontains=query)
            | Q(description__icontains=query)
            | Q(goal__icontains=query)
            | Q(technologies__name__icontains=query)
            | Q(vacancies__title__icontains=query)
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

        open_vacancies = open_vacancies.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(role__name__icontains=query)
            | Q(project__title__icontains=query)
            | Q(project__short_description__icontains=query)
            | Q(project__technologies__name__icontains=query)
        ).distinct()

    featured_projects = (
        projects.with_open_vacancy_count()
        .filter(open_vacancy_count__gt=0)
        .order_by("-open_vacancy_count", "-created_at")[:3]
    )

    active_specialists = specialists[:3]
    featured_vacancies = open_vacancies[:4]

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

    cache_timeout = getattr(settings, "CACHE_TIMEOUT", 300)

    popular_technologies = cache.get("home_popular_technologies_v2")
    if popular_technologies is None:
        popular_technologies = list(
            Technology.objects.filter(is_active=True)
            .annotate(
                project_count=Count(
                    "projects",
                    filter=Q(projects__status=Project.Status.PUBLISHED),
                    distinct=True,
                )
            )
            .filter(project_count__gt=0)
            .order_by("-project_count", "name")[:10]
        )

        cache.set(
            "home_popular_technologies_v2",
            popular_technologies,
            cache_timeout,
        )

    hero_technologies = popular_technologies[:4]

    technology_rows = (
        Technology.objects.filter(is_active=True)
        .values("id", "name", "slug")
        .order_by("name")[:10]
    )

    statistics = cache.get("home_statistics_v2")

    if statistics is None:
        statistics = {
            "published_projects_count": Project.objects.published().count(),
            "open_vacancies_count": ProjectVacancy.objects.filter(
                project__status=Project.Status.PUBLISHED,
                status=ProjectVacancy.Status.OPEN,
                current_count__lt=models.F("required_count"),
            ).count(),
            "specialists_count": SpecialistProfile.objects.exclude(
                status=SpecialistProfile.AvailabilityStatus.HIDDEN,
            ).count(),
            "team_members_count": ProjectMembership.objects.filter(
                status=ProjectMembership.Status.ACTIVE,
            ).count(),
            "roles_count": Role.objects.filter(is_active=True).count(),
            "technologies_count": Technology.objects.filter(is_active=True).count(),
        }
        cache.set("home_statistics_v2", statistics, cache_timeout)

    context = {
        "query": query,
        "new_projects_page": new_projects_page,
        "urgent_projects_page": urgent_projects_page,
        "featured_projects": featured_projects,
        "featured_vacancies": featured_vacancies,
        "active_specialists": active_specialists,
        "popular_technologies": popular_technologies,
        "hero_technologies": hero_technologies,
        "statistics": statistics,
        "recently_viewed_projects": recently_viewed_projects,
        "technology_rows": technology_rows,
    }

    return render(request, "projects/home.html", context)


def project_list(request: HttpRequest) -> HttpResponse:
    """
    Каталог проектов с поиском, фильтрацией, сортировкой и пагинацией.
    Args:
        request: HTTP-запрос текущего пользователя
    """
    query = request.GET.get("q", "").strip()
    ordering = request.GET.get("ordering", "-created_at").strip()

    selected_roles = [value for value in request.GET.getlist("roles") if value]
    selected_technologies = [
        value for value in request.GET.getlist("technologies") if value
    ]
    selected_levels = [value for value in request.GET.getlist("levels") if value]
    selected_stages = [value for value in request.GET.getlist("stages") if value]
    selected_formats = [value for value in request.GET.getlist("formats") if value]
    has_open_roles = request.GET.get("has_open_roles") == "1"

    allowed_ordering = {
        "-created_at": "-created_at",
        "created_at": "created_at",
        "title": "title",
        "-title": "-title",
    }

    projects = (
        Project.objects.filter(
            status__in=[
                Project.Status.PUBLISHED,
                Project.Status.CLOSED,
            ]
        )
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
            | Q(vacancies__title__icontains=query)
            | Q(vacancies__role__name__icontains=query)
        ).distinct()

    if selected_roles:
        projects = projects.filter(vacancies__role__slug__in=selected_roles).distinct()

    if selected_technologies:
        projects = projects.filter(
            technologies__slug__in=selected_technologies
        ).distinct()

    if selected_levels:
        projects = projects.filter(
            vacancies__required_level__in=selected_levels
        ).distinct()

    if selected_stages:
        projects = projects.filter(stage__in=selected_stages)

    if selected_formats:
        projects = projects.filter(participation_format__in=selected_formats)

    if has_open_roles:
        projects = projects.filter(
            status=Project.Status.PUBLISHED,
            vacancies__status=ProjectVacancy.Status.OPEN,
            vacancies__current_count__lt=models.F("vacancies__required_count"),
        ).distinct()

    projects = projects.order_by(allowed_ordering.get(ordering, "-created_at"))

    paginator = Paginator(projects, 6)
    page_number = request.GET.get("page", 1)

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    level_labels = {
        SpecialistProfile.Level.INTERN: "Intern (0–1 год)",
        SpecialistProfile.Level.JUNIOR: "Junior (1–3 года)",
        SpecialistProfile.Level.MIDDLE: "Middle (3–5 лет)",
        SpecialistProfile.Level.SENIOR: "Senior (5+ лет)",
        SpecialistProfile.Level.LEAD: "Lead (7+ лет)",
    }

    level_choices = [
        (value, level_labels.get(value, label))
        for value, label in SpecialistProfile._meta.get_field("level").choices
    ]

    context = {
        "page_obj": page_obj,
        "query": query,
        "ordering": ordering,
        "selected_roles": selected_roles,
        "selected_technologies": selected_technologies,
        "selected_levels": selected_levels,
        "selected_stages": selected_stages,
        "selected_formats": selected_formats,
        "has_open_roles": has_open_roles,
        "roles": Role.objects.filter(is_active=True).order_by("name"),
        "technologies": Technology.objects.filter(is_active=True).order_by("name"),
        "level_choices": level_choices,
        "stage_choices": Project._meta.get_field("stage").choices,
        "format_choices": Project._meta.get_field("participation_format").choices,
    }

    return render(request, "projects/project_list.html", context)


def project_detail(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Детальная страница проекта.
    Args:
        request: HTTP-запрос текущего пользователя
        slug: URL-идентификатор проекта
    """
    project = get_object_or_404(
        Project.objects.select_related("owner").prefetch_related(
            "technologies",
            "vacancies__role",
            "memberships__specialist__user",
            "memberships__role",
            "memberships__vacancy__role",
            "files",
        ),
        slug=slug,
    )

    public_statuses = {
        Project.Status.PUBLISHED,
        Project.Status.CLOSED,
    }

    if project.status not in public_statuses:
        if not project.can_be_edited_by(request.user):
            raise Http404(_("Проект не найден."))

    viewed_project_ids = request.session.get("viewed_project_ids", [])
    viewed_project_ids = [
        project_id for project_id in viewed_project_ids if project_id != project.pk
    ]
    viewed_project_ids.insert(0, project.pk)
    request.session["viewed_project_ids"] = viewed_project_ids[:5]

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

    all_vacancies = project.vacancies.select_related("role").order_by(
        "status",
        "role__name",
        "title",
    )

    all_memberships = project.memberships.select_related(
        "specialist__user",
        "role",
        "vacancy",
        "vacancy__role",
    ).order_by(
        "status",
        "specialist__user__last_name",
        "specialist__user__first_name",
        "id",
    )

    memberships = all_memberships.exclude(
        status=ProjectMembership.Status.LEFT,
    )

    left_memberships = all_memberships.filter(
        status=ProjectMembership.Status.LEFT,
    )

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
                status__in=[
                    ProjectMembership.Status.ACTIVE,
                    ProjectMembership.Status.PAUSED,
                ],
            ).exists()

    context = {
        "project": project,
        "open_vacancies": open_vacancies,
        "memberships": memberships,
        "left_memberships": left_memberships,
        "files": files,
        "similar_projects": similar_projects,
        "is_favorite": is_favorite,
        "is_team_member": is_team_member,
        "can_manage_project": can_manage_project,
        "all_vacancies": all_vacancies,
    }

    return render(request, "projects/project_detail.html", context)


@login_required
def my_projects(request: HttpRequest) -> HttpResponse:
    """
    Проекты, которыми владеет текущий пользователь, и архив владельца.
    Args:
        request: HTTP-запрос текущего пользователя
    """
    active_projects = (
        Project.objects.select_related("owner")
        .prefetch_related("technologies", "vacancies__role")
        .filter(owner=request.user)
        .exclude(status=Project.Status.ARCHIVED)
        .order_by("-created_at")
    )

    archived_projects = (
        Project.objects.select_related("owner")
        .prefetch_related("technologies", "vacancies__role")
        .filter(
            owner=request.user,
            status=Project.Status.ARCHIVED,
        )
        .order_by("-updated_at", "-created_at")
    )

    active_paginator = Paginator(active_projects, 9)
    archive_paginator = Paginator(archived_projects, 9)

    active_page_number = request.GET.get("page", 1)
    archive_page_number = request.GET.get("archive_page", 1)

    try:
        active_projects_page = active_paginator.page(active_page_number)
    except PageNotAnInteger:
        active_projects_page = active_paginator.page(1)
    except EmptyPage:
        active_projects_page = active_paginator.page(active_paginator.num_pages)

    try:
        archived_projects_page = archive_paginator.page(archive_page_number)
    except PageNotAnInteger:
        archived_projects_page = archive_paginator.page(1)
    except EmptyPage:
        archived_projects_page = archive_paginator.page(archive_paginator.num_pages)

    context = {
        "projects": active_projects_page,
        "archived_projects": archived_projects_page,
        "projects_count": active_projects.count(),
        "archived_projects_count": archived_projects.count(),
    }
    return render(request, "projects/my_projects.html", context)


@login_required
def my_teams(request: HttpRequest) -> HttpResponse:
    """
    Проекты, в командах которых состоит или состоял текущий специалист.
    Args:
        request: HTTP-запрос текущего пользователя
    """
    specialist_profile = getattr(request.user, "specialist_profile", None)

    memberships = ProjectMembership.objects.none()
    archived_memberships = ProjectMembership.objects.none()

    if specialist_profile is not None:
        memberships = (
            ProjectMembership.objects.select_related(
                "project",
                "project__owner",
                "role",
            )
            .prefetch_related("project__technologies")
            .filter(
                specialist=specialist_profile,
                status=ProjectMembership.Status.ACTIVE,
            )
            .exclude(project__status=Project.Status.ARCHIVED)
            .order_by("-joined_at")
        )

        archived_memberships = (
            ProjectMembership.objects.select_related(
                "project",
                "project__owner",
                "role",
            )
            .prefetch_related("project__technologies")
            .filter(
                specialist=specialist_profile,
                project__status=Project.Status.ARCHIVED,
            )
            .order_by("-joined_at")
        )

    memberships_paginator = Paginator(memberships, 9)
    archived_memberships_paginator = Paginator(archived_memberships, 9)

    memberships_page_number = request.GET.get("page", 1)
    archive_page_number = request.GET.get("archive_page", 1)

    try:
        memberships_page = memberships_paginator.page(memberships_page_number)
    except PageNotAnInteger:
        memberships_page = memberships_paginator.page(1)
    except EmptyPage:
        memberships_page = memberships_paginator.page(memberships_paginator.num_pages)

    try:
        archived_memberships_page = archived_memberships_paginator.page(
            archive_page_number
        )
    except PageNotAnInteger:
        archived_memberships_page = archived_memberships_paginator.page(1)
    except EmptyPage:
        archived_memberships_page = archived_memberships_paginator.page(
            archived_memberships_paginator.num_pages
        )

    context = {
        "specialist_profile": specialist_profile,
        "memberships": memberships_page,
        "archived_memberships": archived_memberships_page,
        "memberships_count": memberships.count(),
        "archived_memberships_count": archived_memberships.count(),
    }
    return render(request, "projects/my_teams.html", context)


@login_required
def project_create(request: HttpRequest) -> HttpResponse:
    """
    Создание нового проекта вместе с первой открытой ролью.
    Args:
        request: HTTP-запрос текущего пользователя
    """
    if request.method == "POST":
        form = ProjectForm(
            request.POST,
            request.FILES,
            prefix="project",
        )
        vacancy_form = ProjectVacancyForm(
            request.POST,
            prefix="vacancy",
        )

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
                _("Проект создан как черновик. Первая открытая роль добавлена."),
            )
            return HttpResponseRedirect(project.get_absolute_url())
    else:
        form = ProjectForm(prefix="project")
        vacancy_form = ProjectVacancyForm(prefix="vacancy")

    context = {
        "form": form,
        "vacancy_form": vacancy_form,
        "page_title": _("Создать проект"),
        "submit_text": _("Создать проект"),
    }
    return render(request, "projects/project_form.html", context)


@login_required
def project_update(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Редактирование проекта владельцем или администратором.
    Args:
        request: HTTP-запрос текущего пользователя
        slug: URL-идентификатор проекта
    """
    project = get_object_or_404(Project, slug=slug)

    if not project.can_be_edited_by(request.user):
        raise PermissionDenied(
            _("Редактировать проект может только владелец или администратор.")
        )

    if project.status == Project.Status.ARCHIVED:
        raise Http404(_("Архивный проект нельзя редактировать."))

    if request.method == "POST":
        form = ProjectForm(request.POST, request.FILES, instance=project)

        if form.is_valid():
            project = form.save(commit=False)
            project.updated_by = request.user
            project.save()

            form.save_technologies(project)

            messages.success(request, _("Проект обновлён."))
            return redirect(project.get_absolute_url())
    else:
        form = ProjectForm(instance=project)

    context = {
        "form": form,
        "project": project,
        "page_title": _("Редактировать проект"),
        "submit_text": _("Сохранить изменения"),
    }
    return render(request, "projects/project_form.html", context)


@login_required
def project_delete(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Удаление проекта.
    Args:
        request: HTTP-запрос текущего пользователя
        slug: URL-идентификатор проекта
    """
    project = get_object_or_404(Project, slug=slug)

    if not project.can_be_edited_by(request.user):
        raise PermissionDenied(
            _("Удалить проект может только владелец или администратор.")
        )

    if not request.user.is_staff and project.status != Project.Status.DRAFT:
        messages.error(
            request,
            _(
                "Владелец может удалить только черновик. "
                "Опубликованный или закрытый проект нужно архивировать."
            ),
        )
        return redirect(project.get_absolute_url())

    if request.method == "POST":
        project_title = project.title
        project.delete()

        messages.info(
            request,
            _("Проект «%(title)s» удалён.") % {"title": project_title},
        )
        return redirect("projects:my_projects")

    context = {
        "project": project,
    }
    return render(request, "projects/project_confirm_delete.html", context)


@login_required
def project_vacancy_create(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Добавление открытой роли к проекту.
    Args:
        request: HTTP-запрос текущего пользователя
        slug: URL-идентификатор проекта
    """
    project = get_object_or_404(Project, slug=slug)

    if not project.can_be_edited_by(request.user):
        raise PermissionDenied(
            _("Добавлять роли может только владелец проекта или администратор.")
        )

    if project.status in [Project.Status.CLOSED, Project.Status.ARCHIVED]:
        raise Http404(_("Нельзя добавлять роли в закрытый или архивный проект."))

    if request.method == "POST":
        form = ProjectVacancyForm(request.POST)

        if form.is_valid():
            vacancy = form.save(commit=False)
            vacancy.project = project
            vacancy.save()

            messages.success(request, _("Открытая роль добавлена к проекту."))
            return redirect("projects:my_projects")
    else:
        form = ProjectVacancyForm()

    context = {
        "form": form,
        "project": project,
        "page_title": _("Добавить открытую роль"),
        "submit_text": _("Добавить роль"),
    }
    return render(request, "projects/vacancy_form.html", context)


@login_required
def project_vacancy_update(
    request: HttpRequest,
    slug: str,
    vacancy_id: int,
) -> HttpResponse:
    """
    Редактирование открытой роли проекта владельцем или администратором.
    Args:
        request: HTTP-запрос текущего пользователя
        slug: URL-идентификатор проекта
        vacancy_id: ID открытой роли
    """
    project = get_object_or_404(Project, slug=slug)

    if not project.can_be_edited_by(request.user):
        raise PermissionDenied(
            _("Редактировать роли может только владелец проекта или администратор.")
        )

    if project.status == Project.Status.ARCHIVED:
        raise Http404(_("Нельзя редактировать роли архивного проекта."))

    vacancy = get_object_or_404(
        ProjectVacancy,
        pk=vacancy_id,
        project=project,
    )

    if request.method == "POST":
        form = ProjectVacancyUpdateForm(request.POST, instance=vacancy)

        if form.is_valid():
            form.save()
            messages.success(request, _("Открытая роль обновлена."))
            return redirect(project.get_absolute_url())
    else:
        form = ProjectVacancyUpdateForm(instance=vacancy)

    context = {
        "form": form,
        "project": project,
        "vacancy": vacancy,
        "page_title": _("Редактировать открытую роль"),
        "submit_text": _("Сохранить роль"),
    }

    return render(request, "projects/vacancy_form.html", context)


@login_required
def project_membership_update(
    request: HttpRequest,
    slug: str,
    membership_id: int,
) -> HttpResponse:
    """
    Редактирование участника команды проекта владельцем или администратором.
    Args:
        request: HTTP-запрос текущего пользователя
        slug: URL-идентификатор проекта
        membership_id: ID участника команды
    """
    project = get_object_or_404(Project, slug=slug)

    if not project.can_be_edited_by(request.user):
        raise PermissionDenied(
            _("Редактировать команду может только владелец проекта или администратор.")
        )

    if project.status == Project.Status.ARCHIVED:
        raise Http404(_("Нельзя редактировать команду архивного проекта."))

    membership = get_object_or_404(
        ProjectMembership.objects.select_related(
            "project",
            "specialist",
            "specialist__user",
            "role",
            "vacancy",
            "vacancy__role",
        ),
        pk=membership_id,
        project=project,
    )

    if membership.status == ProjectMembership.Status.LEFT:
        messages.error(
            request,
            _(
                "Участник уже покинул проект. Эту историческую запись нельзя "
                "редактировать. При необходимости пригласи специалиста заново."
            ),
        )
        return redirect(project.get_absolute_url())

    if request.method == "POST":
        old_vacancy = membership.vacancy

        form = ProjectMembershipUpdateForm(request.POST, instance=membership)

        if form.is_valid():
            membership = form.save(commit=False)

            membership.role = membership.vacancy.role

            if membership.status == ProjectMembership.Status.LEFT:
                membership.left_at = timezone.now()
            else:
                membership.left_at = None

            membership.save()

            if old_vacancy is not None:
                old_vacancy.sync_current_count()

            membership.vacancy.sync_current_count()

            messages.success(request, _("Участник команды обновлён."))
            return redirect(project.get_absolute_url())
    else:
        form = ProjectMembershipUpdateForm(instance=membership)

    context = {
        "form": form,
        "project": project,
        "membership": membership,
        "page_title": _("Редактировать участника команды"),
        "submit_text": _("Сохранить участника"),
    }

    return render(request, "projects/membership_form.html", context)


@require_POST
@login_required
def project_submit_for_moderation(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Отправляет черновик проекта на модерацию.
    Args:
        request: HTTP-запрос текущего пользователя
        slug: URL-идентификатор проекта
    """
    project = get_object_or_404(Project, slug=slug)

    if not project.can_be_edited_by(request.user):
        raise PermissionDenied(
            _("Отправить проект на модерацию может только владелец или администратор.")
        )

    if request.method != "POST":
        return redirect(project.get_absolute_url())

    if project.status != Project.Status.DRAFT:
        messages.error(request, _("На модерацию можно отправить только черновик."))
        return redirect(project.get_absolute_url())

    has_open_vacancies = ProjectVacancy.objects.filter(
        project=project,
        status=ProjectVacancy.Status.OPEN,
        current_count__lt=models.F("required_count"),
    ).exists()

    if not has_open_vacancies:
        messages.error(
            request,
            _("Перед отправкой на модерацию добавь хотя бы одну открытую роль."),
        )
        return redirect(project.get_absolute_url())

    project.status = Project.Status.MODERATION
    project.updated_by = request.user
    project.save(update_fields=["status", "updated_by", "updated_at"])

    messages.success(request, _("Проект отправлен на рассмотрение модератору."))
    return redirect(project.get_absolute_url())


@require_POST
@login_required
def project_close(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Закрывает опубликованный проект для новых откликов и вакансий.
    Args:
        request: HTTP-запрос текущего пользователя
        slug: URL-идентификатор проекта
    """
    project = get_object_or_404(Project, slug=slug)

    if not project.can_be_edited_by(request.user):
        raise PermissionDenied(
            _("Закрыть проект может только владелец или администратор.")
        )

    if request.method != "POST":
        return redirect(project.get_absolute_url())

    if project.status != Project.Status.PUBLISHED:
        messages.error(request, _("Закрыть можно только опубликованный проект."))
        return redirect(project.get_absolute_url())

    project.status = Project.Status.CLOSED
    project.updated_by = request.user
    project.save(update_fields=["status", "updated_by", "updated_at"])

    messages.success(request, _("Проект закрыт для новых участников."))
    return redirect(project.get_absolute_url())


@require_POST
@login_required
def project_reopen(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Повторно открывает закрытый проект.
    Args:
        request: HTTP-запрос текущего пользователя
        slug: URL-идентификатор проекта
    """
    project = get_object_or_404(Project, slug=slug)

    if not project.can_be_edited_by(request.user):
        raise PermissionDenied(
            _("Открыть проект заново может только владелец или администратор.")
        )

    if request.method != "POST":
        return redirect(project.get_absolute_url())

    if project.status != Project.Status.CLOSED:
        messages.error(request, _("Повторно открыть можно только закрытый проект."))
        return redirect(project.get_absolute_url())

    project.status = Project.Status.PUBLISHED
    project.updated_by = request.user
    project.save(update_fields=["status", "updated_by", "updated_at"])

    messages.success(request, _("Проект снова открыт для набора участников."))
    return redirect(project.get_absolute_url())


@login_required
def project_archive(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Окончательно архивирует проект без возможности восстановления.
    Args:
        request: HTTP-запрос текущего пользователя
        slug: URL-идентификатор проекта
    """
    project = get_object_or_404(Project, slug=slug)

    if not project.can_be_edited_by(request.user):
        raise PermissionDenied(
            _("Архивировать проект может только владелец или администратор.")
        )

    if project.status not in [Project.Status.PUBLISHED, Project.Status.CLOSED]:
        messages.error(
            request,
            _("Архивировать можно только опубликованный или закрытый проект."),
        )
        return redirect(project.get_absolute_url())

    if request.method == "POST":
        confirmation_title = request.POST.get("confirmation_title", "").strip()

        if confirmation_title != project.title:
            messages.error(
                request,
                _("Название проекта введено неверно. Архивация отменена."),
            )
            return redirect("projects:project_archive", slug=project.slug)

        FavoriteProject.objects.filter(project=project).delete()

        ProjectVacancy.objects.filter(project=project).exclude(
            status=ProjectVacancy.Status.CLOSED
        ).update(status=ProjectVacancy.Status.CLOSED)

        project.status = Project.Status.ARCHIVED
        project.updated_by = request.user
        project.save(update_fields=["status", "updated_by", "updated_at"])

        messages.success(
            request,
            _("Проект окончательно перенесён в архив и удалён из избранного."),
        )
        return redirect("projects:my_projects")

    context = {
        "project": project,
    }
    return render(request, "projects/project_archive_confirm.html", context)
