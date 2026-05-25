from django.db.models import Q
from django.shortcuts import render

from apps.projects.models import Project
from apps.specialists.models import SpecialistProfile


def global_search(request):
    query = request.GET.get("q", "").strip()

    projects = Project.objects.none()
    specialists = SpecialistProfile.objects.none()

    if query:
        projects = (
            Project.objects.published()
            .filter(
                Q(title__icontains=query)
                | Q(short_description__icontains=query)
                | Q(description__icontains=query)
                | Q(goal__icontains=query)
                | Q(technologies__name__icontains=query)
                | Q(vacancies__title__icontains=query)
                | Q(vacancies__role__name__icontains=query)
            )
            .select_related("owner")
            .prefetch_related("technologies", "vacancies__role")
            .distinct()[:6]
        )

        specialists = (
            SpecialistProfile.objects.filter(
                Q(user__username__icontains=query)
                | Q(user__first_name__icontains=query)
                | Q(user__last_name__icontains=query)
                | Q(bio__icontains=query)
                | Q(main_role__name__icontains=query)
                | Q(technologies__name__icontains=query)
            )
            .select_related("user", "main_role")
            .prefetch_related("technologies")
            .distinct()[:6]
        )

    context = {
        "query": query,
        "projects": projects,
        "specialists": specialists,
    }

    return render(request, "search/global_search.html", context)
