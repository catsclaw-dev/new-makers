from __future__ import annotations

from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.projects.models import Project
from apps.specialists.models import SpecialistProfile


def global_search(request: HttpRequest) -> HttpResponse:
    """
    Выполняет глобальный поиск по проектам и специалистам.
    Args:
        request: HTTP-запрос текущего пользователя
    """
    raw_query = request.GET.get("q", "").strip()
    query = raw_query
    search_mode = "all"
    unknown_command = False

    if raw_query.startswith("/"):
        parts = raw_query.split(maxsplit=1)
        command = parts[0].lower()
        command_query = parts[1].strip() if len(parts) > 1 else ""

        if command in {"/projects", "/project", "/p"}:
            if command_query:
                search_mode = "projects"
                query = command_query
            else:
                return redirect("projects:project_list")

        elif command in {"/specialists", "/specialist", "/s"}:
            if command_query:
                search_mode = "specialists"
                query = command_query
            else:
                return redirect("specialists:specialist_list")

        elif command in {"/profile", "/cabinet", "/me"}:
            if request.user.is_authenticated:
                return redirect("accounts:profile")
            return redirect("accounts:login")

        elif command in {"/applications", "/application", "/apps", "/отклики"}:
            if request.user.is_authenticated:
                return redirect("interactions:application_list")
            return redirect("accounts:login")

        elif command in {"/invites", "/invitations", "/invite", "/приглашения"}:
            if request.user.is_authenticated:
                return redirect("interactions:invitation_list")
            return redirect("accounts:login")

        elif command in {"/favorites", "/favorite", "/fav", "/избранное"}:
            if request.user.is_authenticated:
                return redirect("interactions:favorite_project_list")
            return redirect("accounts:login")

        elif command in {"/teams", "/team", "/команды"}:
            if request.user.is_authenticated:
                return redirect("projects:my_teams")
            return redirect("accounts:login")

        elif command in {"/myprojects", "/my-projects", "/моипроекты"}:
            if request.user.is_authenticated:
                return redirect("projects:my_projects")
            return redirect("accounts:login")

        else:
            unknown_command = True
            query = command_query or raw_query.lstrip("/")

    projects = Project.objects.none()
    specialists = SpecialistProfile.objects.none()

    if query:
        if search_mode in {"all", "projects"}:
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

        if search_mode in {"all", "specialists"}:
            specialists = (
                SpecialistProfile.objects.exclude(
                    status=SpecialistProfile.AvailabilityStatus.HIDDEN,
                )
                .filter(
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
        "raw_query": raw_query,
        "query": query,
        "search_mode": search_mode,
        "unknown_command": unknown_command,
        "projects": projects,
        "specialists": specialists,
    }

    return render(request, "search/global_search.html", context)
