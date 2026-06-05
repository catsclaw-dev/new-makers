from __future__ import annotations

from celery import shared_task

from apps.projects.models import ProjectMembership, ProjectVacancy


@shared_task
def sync_project_vacancy_counts() -> int:
    """
    Синхронизирует счетчики участников и статусы открытых ролей.
    """
    changed_count = 0

    vacancies = ProjectVacancy.objects.select_related("project", "role").order_by("pk")

    for vacancy in vacancies:
        active_count = ProjectMembership.objects.filter(
            project=vacancy.project,
            role=vacancy.role,
            status=ProjectMembership.Status.ACTIVE,
        ).count()
        new_status = vacancy.status

        if active_count >= vacancy.required_count:
            new_status = ProjectVacancy.Status.CLOSED

        if vacancy.current_count == active_count and vacancy.status == new_status:
            continue

        vacancy.current_count = active_count
        vacancy.status = new_status
        vacancy.save(update_fields=["current_count", "status", "updated_at"])
        changed_count += 1

    return changed_count
