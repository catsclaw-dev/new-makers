from django.urls import path

from apps.specialists import views

app_name = "specialists"

urlpatterns = [
    path("", views.specialist_list, name="specialist_list"),
    path("<int:pk>/", views.specialist_detail, name="specialist_detail"),
]
