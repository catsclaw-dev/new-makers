from django.urls import path

from apps.interactions import views

app_name = "interactions"

urlpatterns = [
    path("applications/", views.application_list, name="application_list"),
    path(
        "applications/<int:pk>/accept/",
        views.application_accept,
        name="application_accept",
    ),
    path(
        "applications/<int:pk>/reject/",
        views.application_reject,
        name="application_reject",
    ),
    path("favorites/", views.favorite_project_list, name="favorite_project_list"),
    path("invitations/", views.invitation_list, name="invitation_list"),
    path(
        "invitations/<int:pk>/accept/",
        views.invitation_accept,
        name="invitation_accept",
    ),
    path(
        "invitations/<int:pk>/decline/",
        views.invitation_decline,
        name="invitation_decline",
    ),
    path("projects/<str:slug>/apply/", views.project_apply, name="project_apply"),
    path(
        "projects/<str:slug>/favorite/",
        views.favorite_project_toggle,
        name="favorite_project_toggle",
    ),
    path(
        "specialists/<int:pk>/invite/",
        views.invite_specialist,
        name="invite_specialist",
    ),
]
