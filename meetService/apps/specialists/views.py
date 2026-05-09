from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from apps.directories.models import Role, Technology
from apps.projects.models import ProjectMembership
from apps.specialists.models import SpecialistProfile


def specialist_list(request):
    """Каталог специалистов с поиском, фильтрами и пагинацией."""
    query = request.GET.get("q", "").strip()
    role_slug = request.GET.get("role", "").strip()
    technology_slug = request.GET.get("technology", "").strip()
    level = request.GET.get("level", "").strip()
    status = request.GET.get("status", "").strip()

    specialists = (
        SpecialistProfile.objects.select_related("user", "main_role")
        .prefetch_related("technologies")
        .order_by("-created_at")
    )

    if query:
        specialists = specialists.filter(
            Q(user__username__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(bio__icontains=query)
            | Q(main_role__name__icontains=query)
            | Q(technologies__name__icontains=query)
        ).distinct()

    if role_slug:
        specialists = specialists.filter(main_role__slug=role_slug)

    if technology_slug:
        specialists = specialists.filter(technologies__slug=technology_slug)

    if level:
        specialists = specialists.filter(level=level)

    if status:
        specialists = specialists.filter(status=status)

    paginator = Paginator(specialists, 6)
    page_number = request.GET.get("page", 1)

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        "page_obj": page_obj,
        "query": query,
        "role_slug": role_slug,
        "technology_slug": technology_slug,
        "level": level,
        "status": status,
        "roles": Role.objects.filter(is_active=True).order_by("name"),
        "technologies": Technology.objects.filter(is_active=True).order_by("name"),
        "level_choices": SpecialistProfile._meta.get_field("level").choices,
        "status_choices": SpecialistProfile._meta.get_field("status").choices,
    }
    return render(request, "specialists/specialist_list.html", context)


def specialist_detail(request, pk):
    """Детальная страница специалиста."""
    specialist = get_object_or_404(
        SpecialistProfile.objects.select_related("user", "main_role").prefetch_related(
            "technologies"
        ),
        pk=pk,
    )

    memberships = (
        ProjectMembership.objects.select_related("project", "role")
        .filter(specialist=specialist)
        .order_by("-joined_at")
    )

    context = {
        "specialist": specialist,
        "memberships": memberships,
    }
    return render(request, "specialists/specialist_detail.html", context)
