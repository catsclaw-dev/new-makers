from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.api.views import (
    ApplicationViewSet,
    FavoriteProjectViewSet,
    InvitationViewSet,
    ProjectVacancyViewSet,
    ProjectViewSet,
    ReviewViewSet,
    RoleViewSet,
    SpecialistProfileViewSet,
    TechnologyViewSet,
)

app_name = "api"

router = DefaultRouter()
router.register("roles", RoleViewSet, basename="role")
router.register("technologies", TechnologyViewSet, basename="technology")
router.register("projects", ProjectViewSet, basename="project")
router.register("vacancies", ProjectVacancyViewSet, basename="vacancy")
router.register("specialists", SpecialistProfileViewSet, basename="specialist")
router.register("applications", ApplicationViewSet, basename="application")
router.register("invitations", InvitationViewSet, basename="invitation")
router.register("favorites", FavoriteProjectViewSet, basename="favorite")
router.register("reviews", ReviewViewSet, basename="review")

urlpatterns = [
    path("", include(router.urls)),
]
