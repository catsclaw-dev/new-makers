from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

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
    city = request.GET.get("city", "").strip()

    selected_roles = [value for value in request.GET.getlist("roles") if value]
    selected_technologies = [value for value in request.GET.getlist("technologies") if value]
    selected_levels = [value for value in request.GET.getlist("levels") if value]
    selected_statuses = [value for value in request.GET.getlist("statuses") if value]
    selected_formats = [value for value in request.GET.getlist("formats") if value]
    selected_timezones = [value for value in request.GET.getlist("timezones") if value]

    timezone_groups = [
        {
            "value": "utc_0_2",
            "label": "UTC +0...+2",
            "values": ["UTC", "Etc/UTC", "Europe/London", "Europe/Kaliningrad"],
        },
        {
            "value": "utc_3_5",
            "label": "UTC +3...+5",
            "values": ["Europe/Moscow", "Europe/Samara", "Asia/Yekaterinburg"],
        },
        {
            "value": "utc_6_8",
            "label": "UTC +6...+8",
            "values": ["Asia/Omsk", "Asia/Novosibirsk", "Asia/Krasnoyarsk", "Asia/Irkutsk"],
        },
        {
            "value": "utc_9_12",
            "label": "UTC +9...+12",
            "values": ["Asia/Yakutsk", "Asia/Vladivostok", "Asia/Magadan", "Asia/Kamchatka"],
        },
    ]

    specialists = (
        SpecialistProfile.objects.select_related("user", "main_role")
        .prefetch_related("technologies", "preferred_roles")
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
            | Q(preferred_roles__name__icontains=query)
            | Q(technologies__name__icontains=query)
        ).distinct()

    if selected_roles:
        specialists = specialists.filter(
            Q(main_role__slug__in=selected_roles)
            | Q(preferred_roles__slug__in=selected_roles)
        ).distinct()

    if selected_technologies:
        specialists = specialists.filter(
            technologies__slug__in=selected_technologies,
        ).distinct()

    if selected_levels:
        specialists = specialists.filter(level__in=selected_levels)

    if selected_statuses:
        specialists = specialists.filter(status__in=selected_statuses)

    if selected_formats:
        specialists = specialists.filter(participation_format__in=selected_formats)

    if selected_timezones:
        timezone_values = []

        for group in timezone_groups:
            if group["value"] in selected_timezones:
                timezone_values.extend(group["values"])

        if timezone_values:
            specialists = specialists.filter(timezone__in=timezone_values)

    if city:
        specialists = specialists.filter(city__icontains=city)

    paginator = Paginator(specialists, 6)
    page_number = request.GET.get("page", 1)

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    status_choices = [
        (value, label)
        for value, label in SpecialistProfile._meta.get_field("status").choices
        if value != SpecialistProfile.AvailabilityStatus.HIDDEN
    ]

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
        "city": city,
        "selected_roles": selected_roles,
        "selected_technologies": selected_technologies,
        "selected_levels": selected_levels,
        "selected_statuses": selected_statuses,
        "selected_formats": selected_formats,
        "selected_timezones": selected_timezones,
        "roles": Role.objects.filter(is_active=True).order_by("name"),
        "technologies": Technology.objects.filter(is_active=True).order_by("name"),
        "level_choices": level_choices,
        "status_choices": status_choices,
        "format_choices": SpecialistProfile._meta.get_field("participation_format").choices,
        "timezone_groups": timezone_groups,
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
            raise Http404(_("Профиль специалиста не найден."))

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

            messages.success(request, _("Профиль специалиста сохранён."))
            return redirect("projects:my_teams")

        messages.error(
            request,
            _("Профиль специалиста не сохранён. Проверь ошибки в форме."),
        )
    else:
        form = SpecialistProfileForm(instance=profile)

    context = {
        "form": form,
        "profile": profile,
        "page_title": (
            _("Редактировать профиль специалиста")
            if profile
            else _("Заполнить профиль специалиста")
        ),
        "submit_text": _("Сохранить профиль"),
    }
    return render(request, "specialists/specialist_profile_form.html", context)
