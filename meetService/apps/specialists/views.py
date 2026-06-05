from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q

from apps.directories.models import Role, Technology
from apps.projects.models import ProjectMembership
from apps.specialists.models import SpecialistProfile
from apps.specialists.forms import SpecialistProfileForm


def specialist_list(request: HttpRequest) -> HttpResponse:
    """
    Каталог специалистов с поиском, фильтрами и пагинацией.
    Args:
        request: HTTP-запрос текущего пользователя
    """
    query = request.GET.get("q", "").strip()
    role_slug = request.GET.get("role", "").strip()
    technology_slug = request.GET.get("technology", "").strip()
    level = request.GET.get("level", "").strip()
    status = request.GET.get("status", "").strip()

    specialists = (
        SpecialistProfile.objects.select_related("user", "main_role")
        .prefetch_related("technologies")
        .exclude(status=SpecialistProfile.AvailabilityStatus.HIDDEN)
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


def specialist_detail(request: HttpRequest, pk: int | None) -> HttpResponse:
    """
    Детальная страница специалиста.
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

    if specialist.status == SpecialistProfile.AvailabilityStatus.HIDDEN:
        can_view_hidden = (
            request.user.is_authenticated
            and (request.user.is_staff or specialist.user_id == request.user.id)
        )

        if not can_view_hidden:
            raise Http404("Профиль специалиста не найден.")

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


@login_required
def specialist_profile_edit(request: HttpRequest) -> HttpResponse:
    """
    Создание или редактирование профиля специалиста текущего пользователя.
    Args:
        request: HTTP-запрос текущего пользователя
    """
    profile = SpecialistProfile.objects.filter(user=request.user).first()

    if request.method == "POST":
        form = SpecialistProfileForm(
            request.POST,
            request.FILES,
            instance=profile,
        )

        if form.is_valid():
            specialist_profile = form.save(commit=False)
            specialist_profile.user = request.user

            if profile is None:
                specialist_profile.created_by = request.user

            specialist_profile.updated_by = request.user
            specialist_profile.save()
            form.save_m2m()

            messages.success(request, "Профиль специалиста сохранён.")
            return redirect("projects:my_teams")

        messages.error(
            request,
            "Профиль специалиста не сохранён. Проверь ошибки в форме.",
        )
    else:
        form = SpecialistProfileForm(instance=profile)

    context = {
        "form": form,
        "profile": profile,
        "page_title": (
            "Редактировать профиль специалиста"
            if profile
            else "Заполнить профиль специалиста"
        ),
        "submit_text": "Сохранить профиль",
    }
    return render(request, "specialists/specialist_profile_form.html", context)
