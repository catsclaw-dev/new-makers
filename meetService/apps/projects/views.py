"""HTML-представления для проектов и главной страницы."""

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import models
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render

from apps.directories.models import Role, Technology
from apps.interactions.models import FavoriteProject
from apps.projects.models import Project
from apps.specialists.models import SpecialistProfile


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
    """Детальная страница проекта."""
    project = get_object_or_404(
        Project.objects.select_related("owner")
        .prefetch_related(
            "technologies",
            "vacancies__role",
            "memberships__specialist__user",
            "memberships__role",
            "files",
        )
        .filter(status=Project.Status.PUBLISHED),
        slug=slug,
    )

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
        status="open",
        current_count__lt=models.F("required_count"),
    ).select_related("role")

    memberships = project.memberships.select_related("specialist__user", "role")
    files = project.files.all()

    is_favorite = False

    if request.user.is_authenticated:
        is_favorite = FavoriteProject.objects.filter(
            user=request.user,
            project=project,
        ).exists()

    context = {
        "project": project,
        "open_vacancies": open_vacancies,
        "memberships": memberships,
        "files": files,
        "similar_projects": similar_projects,
        "is_favorite": is_favorite,
    }
    return render(request, "projects/project_detail.html", context)
