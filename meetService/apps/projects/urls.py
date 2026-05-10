from django.urls import path

from apps.projects import views

app_name = "projects"

urlpatterns = [
    path("", views.home, name="home"),
    path("projects/", views.project_list, name="project_list"),
    path("projects/my/", views.my_projects, name="my_projects"),
    path("projects/create/", views.project_create, name="project_create"),
    path(
        "projects/<str:slug>/submit-for-moderation",
        views.project_submit_for_moderation,
        name="project_submit_for_moderation",
    ),
    path(
        "projects/<str:slug>/close/",
        views.project_close,
        name="project_close",
    ),
    path(
        "projects/<str:slug>/reopen/",
        views.project_reopen,
        name="project_reopen",
    ),
    path("projects/<str:slug>/edit/", views.project_update, name="project_update"),
    path("projects/<str:slug>/delete/", views.project_delete, name="project_delete"),
    path(
        "projects/<str:slug>/vacancies/create/",
        views.project_vacancy_create,
        name="project_vacancy_create",
    ),
    path("teams/my/", views.my_teams, name="my_teams"),
    path("projects/<str:slug>/", views.project_detail, name="project_detail"),
    path(
        "projects/<str:slug>/archive",
        views.project_archive,
        name="project_archive",
    ),
]
