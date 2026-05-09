from django.urls import path

from apps.interactions import views

app_name = "interactions"

urlpatterns = [
    path("applications/", views.application_list, name="application_list"),
    path("favorites/", views.favorite_project_list, name="favorite_project_list"),
    path("projects/<str:slug>/apply/", views.project_apply, name="project_apply"),
    path(
        "projects/<str:slug>/favorite/",
        views.favorite_project_toggle,
        name="favorite_project_toggle",
    ),
]
