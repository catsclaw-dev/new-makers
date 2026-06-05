from __future__ import annotations

from django import template
from django.db.models import Count, Q

from apps.directories.models import Technology
from apps.projects.models import Project

register = template.Library()


@register.filter
def short_text(value: object, length: int = 120) -> object:
    """
    Обрезает длинный текст до указанной длины.
    Args:
        value: Проверяемое значение
        length: Значение параметра `length`
    """
    if not value:
        return ""

    text = str(value)

    if len(text) <= int(length):
        return text

    return f"{text[: int(length)].rstrip()}..."


@register.filter
def vacancy_word(count: int) -> object:
    """
    Возвращает слово 'роль' в правильной форме.
    Args:
        count: Количество объектов
    """
    try:
        count = int(count)
    except (TypeError, ValueError):
        return "ролей"

    if count % 10 == 1 and count % 100 != 11:
        return "роль"

    if 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
        return "роли"

    return "ролей"


@register.simple_tag
def service_name() -> object:
    """
    Простой шаблонный тег с названием сервиса.
    """
    return "MeetService"


@register.simple_tag(takes_context=True)
def current_query_string(context: dict[str, object], **kwargs: object) -> object:
    """
    Возвращает query string с учётом текущих GET-параметров.
    Args:
        context: Контекст шаблона или сериализатора
        **kwargs: Именованные аргументы
    """
    request = context.get("request")

    if request is None:
        return ""

    query_params = request.GET.copy()

    for key, value in kwargs.items():
        query_params[key] = value

    return query_params.urlencode()


@register.inclusion_tag("projects/tags/popular_technologies.html")
def show_popular_technologies(limit: int = 8) -> object:
    """
    Возвращает QuerySet популярных технологий для отдельного блока.
    Args:
        limit: Максимальное количество элементов
    """
    technologies = (
        Technology.objects.filter(is_active=True)
        .annotate(
            project_count=Count(
                "projects",
                filter=Q(projects__status=Project.Status.PUBLISHED),
            )
        )
        .order_by("-project_count", "name")[: int(limit)]
    )

    return {
        "technologies": technologies,
    }
