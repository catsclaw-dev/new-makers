from django import template
from django.db.models import Count, Q

from apps.directories.models import Technology
from apps.projects.models import Project

register = template.Library()


@register.filter
def short_text(value, length=120):
    """Обрезает длинный текст до указанной длины."""
    if not value:
        return ""

    text = str(value)

    if len(text) <= int(length):
        return text

    return f"{text[: int(length)].rstrip()}..."


@register.filter
def vacancy_word(count):
    """Возвращает слово 'роль' в правильной форме."""
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
def service_name():
    """Простой шаблонный тег с названием сервиса."""
    return "MeetService"


@register.simple_tag(takes_context=True)
def current_query_string(context, **kwargs):
    """Возвращает query string с учётом текущих GET-параметров."""
    request = context.get("request")

    if request is None:
        return ""

    query_params = request.GET.copy()

    for key, value in kwargs.items():
        query_params[key] = value

    return query_params.urlencode()


@register.inclusion_tag("projects/tags/popular_technologies.html")
def show_popular_technologies(limit=8):
    """Возвращает QuerySet популярных технологий для отдельного блока."""
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
