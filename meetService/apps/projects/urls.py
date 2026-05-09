from django.urls import path

from apps.projects import views

app_name = "projects"

urlpatterns = [
    path("", views.home, name="home"),
    path("projects/", views.project_list, name="project_list"),
    path("projects/<str:slug>/", views.project_detail, name="project_detail"),
]
