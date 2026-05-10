from django.urls import path

from apps.specialists import views

app_name = "specialists"

urlpatterns = [
    path("", views.specialist_list, name="specialist_list"),
    path(
        "profile/edit/",
        views.specialist_profile_edit,
        name="specialist_profile_edit",
    ),
    path("<int:pk>/", views.specialist_detail, name="specialist_detail"),
]
