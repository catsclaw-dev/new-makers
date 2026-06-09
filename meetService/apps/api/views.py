from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.db.models import Count, Exists, F, OuterRef, Q, QuerySet
from django.utils.translation import gettext_lazy as _
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.serializers import AuthTokenSerializer
from rest_framework.decorators import action
from rest_framework.exceptions import (
    NotAuthenticated,
    PermissionDenied,
    ValidationError,
)
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.serializers import BaseSerializer as Serializer

from apps.api.filters import (
    ApplicationFilter,
    InvitationFilter,
    ProjectFilter,
    ProjectVacancyFilter,
    SpecialistProfileFilter,
)
from apps.api.permissions import (
    IsAdminOrReadOnly,
    IsApplicationReviewer,
    IsFavoriteOwner,
    IsInvitationRecipientOrAdmin,
    IsProjectOwnerOrAdmin,
    IsSpecialistOwnerOrAdmin,
    is_admin,
)
from apps.api.serializers import (
    ApplicationSerializer,
    FavoriteProjectSerializer,
    InvitationSerializer,
    ProjectSerializer,
    ProjectVacancySerializer,
    RoleSerializer,
    SpecialistProfileSerializer,
    TechnologySerializer,
    raise_serializer_validation,
)
from apps.directories.models import Role, Technology
from apps.interactions.models import Application, FavoriteProject, Invitation
from apps.projects.models import Project, ProjectMembership, ProjectVacancy
from apps.specialists.models import SpecialistProfile


PUBLIC_PROJECT_STATUSES = [
    Project.Status.PUBLISHED,
    Project.Status.CLOSED,
]


class CustomAuthToken(APIView):
    """Выдаёт API-токен по логину и паролю."""

    permission_classes = [AllowAny]
    serializer_class = AuthTokenSerializer

    def post(self, request: Request) -> Response:
        """
        Возвращает токен для авторизации в API.
        Args:
            request: HTTP-запрос с username и password
        """
        serializer = self.serializer_class(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)

        return Response(
            {
                "token": token.key,
                "user": {
                    "id": user.pk,
                    "username": user.get_username(),
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                },
            }
        )


class CurrentUserAPIView(APIView):
    """Возвращает данные текущего пользователя по токену."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        """
        Возвращает текущего авторизованного пользователя.
        Args:
            request: HTTP-запрос текущего пользователя
        """
        user = request.user

        return Response(
            {
                "id": user.pk,
                "username": user.get_username(),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
            }
        )


class LogoutAPIView(APIView):
    """Удаляет API-токен текущего пользователя."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        """
        Удаляет токен текущего пользователя.
        Args:
            request: HTTP-запрос текущего пользователя
        """
        Token.objects.filter(user=request.user).delete()

        return Response(
            {
                "detail": _("API-токен удалён."),
            }
        )


class RoleViewSet(viewsets.ModelViewSet):
    serializer_class = RoleSerializer
    permission_classes = [IsAdminOrReadOnly]
    search_fields = ("name", "slug", "description")
    ordering_fields = ("name", "created_at", "updated_at")
    ordering = ("name",)
    filterset_fields = ("is_active",)

    def get_queryset(self) -> QuerySet:
        """
        Возвращает queryset с нужными фильтрами и оптимизациями.
        """
        queryset = Role.objects.annotate(
            open_vacancies_count=Count(
                "project_vacancies",
                filter=Q(project_vacancies__status=ProjectVacancy.Status.OPEN),
                distinct=True,
            ),
            main_specialists_count=Count("main_specialists", distinct=True),
            preferred_specialists_count=Count(
                "preferred_by_specialists",
                distinct=True,
            ),
        )

        if is_admin(self.request.user):
            return queryset

        return queryset.filter(is_active=True)


class TechnologyViewSet(viewsets.ModelViewSet):
    serializer_class = TechnologySerializer
    permission_classes = [IsAdminOrReadOnly]
    search_fields = ("name", "slug", "description")
    ordering_fields = ("category", "name", "created_at", "updated_at")
    ordering = ("category", "name")
    filterset_fields = ("category", "is_active")

    def get_queryset(self) -> QuerySet:
        """
        Возвращает queryset с нужными фильтрами и оптимизациями.
        """
        queryset = Technology.objects.annotate(
            projects_count=Count("projects", distinct=True),
            published_projects_count=Count(
                "projects",
                filter=Q(projects__status=Project.Status.PUBLISHED),
                distinct=True,
            ),
            specialists_count=Count("specialists", distinct=True),
        )

        if is_admin(self.request.user):
            return queryset

        return queryset.filter(is_active=True)


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    filterset_class = ProjectFilter
    search_fields = (
        "title",
        "short_description",
        "description",
        "goal",
        "technologies__name",
        "vacancies__title",
        "vacancies__role__name",
    )
    ordering_fields = (
        "created_at",
        "updated_at",
        "title",
        "open_vacancy_count",
        "members_count",
        "favorite_count",
    )
    ordering = ("-created_at",)

    def get_permissions(self) -> list[object]:
        """
        Возвращает права доступа для текущего действия.
        """
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]

        if self.action in ["create", "favorite", "vacancies"]:
            return [IsAuthenticatedOrReadOnly()]

        return [IsAuthenticated(), IsProjectOwnerOrAdmin()]

    def get_queryset(self) -> QuerySet:
        """
        Возвращает queryset с нужными фильтрами и оптимизациями.
        """
        queryset = (
            Project.objects.select_related("owner", "created_by", "updated_by")
            .prefetch_related(
                "technologies",
                "vacancies__role",
                "memberships__specialist__user",
                "memberships__role",
            )
            .annotate(
                open_vacancy_count=Count(
                    "vacancies",
                    filter=Q(
                        vacancies__status=ProjectVacancy.Status.OPEN,
                        vacancies__current_count__lt=F("vacancies__required_count"),
                    ),
                    distinct=True,
                ),
                members_count=Count(
                    "memberships",
                    filter=Q(memberships__status=ProjectMembership.Status.ACTIVE),
                    distinct=True,
                ),
                favorite_count=Count("favorited_by", distinct=True),
            )
        )

        user = self.request.user

        if user.is_authenticated:
            queryset = queryset.annotate(
                is_favorited=Exists(
                    FavoriteProject.objects.filter(
                        user=user,
                        project_id=OuterRef("pk"),
                    )
                )
            )

        if is_admin(user):
            return queryset

        if user.is_authenticated:
            return queryset.filter(
                Q(status__in=PUBLIC_PROJECT_STATUSES) | Q(owner=user)
            ).distinct()

        return queryset.filter(status__in=PUBLIC_PROJECT_STATUSES)

    def perform_create(self, serializer: Serializer) -> None:
        """
        Создаёт проект от имени текущего пользователя.
        Args:
            serializer: Сериализатор с проверенными данными
        """
        serializer.save(
            owner=self.request.user,
            status=Project.Status.DRAFT,
            created_by=self.request.user,
            updated_by=self.request.user,
        )

    def perform_update(self, serializer: Serializer) -> None:
        """
        Обновляет проект и фиксирует пользователя, который внёс изменения.
        Args:
            serializer: Сериализатор с проверенными данными
        """
        serializer.save(updated_by=self.request.user)

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        """
        Удаляет объект или отменяет действие через API.
        Args:
            request: HTTP-запрос текущего пользователя
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы
        """
        project = self.get_object()

        if not is_admin(request.user) and project.status != Project.Status.DRAFT:
            raise ValidationError(
                _(
                    "Владелец может удалить только черновик. "
                    "Опубликованный или закрытый проект нужно архивировать."
                )
            )

        project.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=["get", "post"],
        permission_classes=[IsAuthenticatedOrReadOnly],
    )
    def vacancies(self, request: Request, pk: int | None = None) -> Response:
        """
        Выполняет API-действие `vacancies`.
        Args:
            request: HTTP-запрос текущего пользователя
            pk: Идентификатор объекта
        """
        project = self.get_object()

        if request.method == "GET":
            vacancies = project.vacancies.select_related("role").order_by(
                "status",
                "role__name",
                "title",
            )
            serializer = ProjectVacancySerializer(
                vacancies,
                many=True,
                context=self.get_serializer_context(),
            )
            return Response(serializer.data)

        if not project.can_be_edited_by(request.user):
            raise PermissionDenied(
                _("Добавлять роли может только владелец проекта или администратор.")
            )

        serializer = ProjectVacancySerializer(
            data=request.data,
            context={
                **self.get_serializer_context(),
                "project": project,
            },
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(project=project)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def submit_for_moderation(
        self, request: Request, pk: int | None = None
    ) -> Response:
        """
        Выполняет API-действие `submit_for_moderation`.
        Args:
            request: HTTP-запрос текущего пользователя
            pk: Идентификатор объекта
        """
        project = self.get_object()

        if project.status != Project.Status.DRAFT:
            raise ValidationError(_("На модерацию можно отправить только черновик."))

        has_open_vacancies = project.vacancies.filter(
            status=ProjectVacancy.Status.OPEN,
            current_count__lt=F("required_count"),
        ).exists()

        if not has_open_vacancies:
            raise ValidationError(
                _("Перед отправкой на модерацию добавь хотя бы одну открытую роль.")
            )

        project.status = Project.Status.MODERATION
        project.updated_by = request.user
        project.save(update_fields=["status", "updated_by", "updated_at"])

        serializer = self.get_serializer(project)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def close(self, request: Request, pk: int | None = None) -> Response:
        """
        Выполняет API-действие `close`.
        Args:
            request: HTTP-запрос текущего пользователя
            pk: Идентификатор объекта
        """
        project = self.get_object()

        if project.status != Project.Status.PUBLISHED:
            raise ValidationError(_("Закрыть можно только опубликованный проект."))

        project.status = Project.Status.CLOSED
        project.updated_by = request.user
        project.save(update_fields=["status", "updated_by", "updated_at"])

        serializer = self.get_serializer(project)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def reopen(self, request: Request, pk: int | None = None) -> Response:
        """
        Выполняет API-действие `reopen`.
        Args:
            request: HTTP-запрос текущего пользователя
            pk: Идентификатор объекта
        """
        project = self.get_object()

        if project.status != Project.Status.CLOSED:
            raise ValidationError(_("Повторно открыть можно только закрытый проект."))

        project.status = Project.Status.PUBLISHED
        project.updated_by = request.user
        project.save(update_fields=["status", "updated_by", "updated_at"])

        serializer = self.get_serializer(project)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def archive(self, request: Request, pk: int | None = None) -> Response:
        """
        Выполняет API-действие `archive`.
        Args:
            request: HTTP-запрос текущего пользователя
            pk: Идентификатор объекта
        """
        project = self.get_object()

        if project.status not in [Project.Status.PUBLISHED, Project.Status.CLOSED]:
            raise ValidationError(
                _("Архивировать можно только опубликованный или закрытый проект.")
            )

        confirmation_title = request.data.get("confirmation_title", "").strip()

        if confirmation_title != project.title:
            raise ValidationError(
                {
                    "confirmation_title": (
                        _("Название проекта введено неверно. Архивация отменена.")
                    )
                }
            )

        FavoriteProject.objects.filter(project=project).delete()

        ProjectVacancy.objects.filter(project=project).exclude(
            status=ProjectVacancy.Status.CLOSED
        ).update(status=ProjectVacancy.Status.CLOSED)

        project.status = Project.Status.ARCHIVED
        project.updated_by = request.user
        project.save(update_fields=["status", "updated_by", "updated_at"])

        serializer = self.get_serializer(project)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def favorite(self, request: Request, pk: int | None = None) -> Response:
        """
        Выполняет API-действие `favorite`.
        Args:
            request: HTTP-запрос текущего пользователя
            pk: Идентификатор объекта
        """
        project = self.get_object()

        if project.status not in PUBLIC_PROJECT_STATUSES:
            raise ValidationError(
                _(
                    "В избранное можно добавить только опубликованный или закрытый проект."
                )
            )

        favorite = FavoriteProject.objects.filter(
            user=request.user,
            project=project,
        ).first()

        if favorite:
            favorite.delete()
            return Response({"is_favorite": False})

        FavoriteProject.objects.create(user=request.user, project=project)
        return Response({"is_favorite": True}, status=status.HTTP_201_CREATED)


class ProjectVacancyViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectVacancySerializer
    filterset_class = ProjectVacancyFilter
    search_fields = (
        "title",
        "description",
        "role__name",
        "project__title",
    )
    ordering_fields = (
        "created_at",
        "updated_at",
        "required_count",
        "current_count",
        "title",
    )
    ordering = ("project", "role__name", "title")

    def get_permissions(self) -> list[object]:
        """
        Возвращает права доступа для текущего действия.
        """
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]

        if self.action == "create":
            return [IsAuthenticated()]

        return [IsAuthenticated(), IsProjectOwnerOrAdmin()]

    def get_queryset(self) -> QuerySet:
        """
        Возвращает queryset с нужными фильтрами и оптимизациями.
        """
        queryset = ProjectVacancy.objects.select_related(
            "project",
            "project__owner",
            "role",
        ).prefetch_related("project__technologies")

        user = self.request.user

        if is_admin(user):
            return queryset

        if user.is_authenticated:
            return queryset.filter(
                Q(project__status__in=PUBLIC_PROJECT_STATUSES) | Q(project__owner=user)
            ).distinct()

        return queryset.filter(project__status__in=PUBLIC_PROJECT_STATUSES)

    def perform_create(self, serializer: Serializer) -> None:
        """
        Создаёт открытую роль после проверки доступа к проекту.
        Args:
            serializer: Сериализатор с проверенными данными
        """
        project = serializer.validated_data["project"]

        if not project.can_be_edited_by(self.request.user):
            raise PermissionDenied(
                _("Добавлять роли может только владелец проекта или администратор.")
            )

        serializer.save()


class SpecialistProfileViewSet(viewsets.ModelViewSet):
    serializer_class = SpecialistProfileSerializer
    filterset_class = SpecialistProfileFilter
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "bio",
        "main_role__name",
        "technologies__name",
        "city",
    )
    ordering_fields = (
        "created_at",
        "updated_at",
        "experience_years",
        "weekly_hours",
        "active_projects_count",
    )
    ordering = ("-created_at",)

    def get_permissions(self) -> list[object]:
        """
        Возвращает права доступа для текущего действия.
        """
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]

        if self.action in ["create", "me"]:
            return [IsAuthenticated()]

        return [IsAuthenticated(), IsSpecialistOwnerOrAdmin()]

    def get_queryset(self) -> QuerySet:
        """
        Возвращает queryset с нужными фильтрами и оптимизациями.
        """
        queryset = (
            SpecialistProfile.objects.select_related("user", "main_role")
            .prefetch_related("preferred_roles", "technologies")
            .annotate(
                active_projects_count=Count(
                    "project_memberships",
                    filter=Q(
                        project_memberships__status=ProjectMembership.Status.ACTIVE,
                    ),
                    distinct=True,
                ),
                applications_count=Count("applications", distinct=True),
                invitations_count=Count("invitations", distinct=True),
            )
        )

        user = self.request.user

        if is_admin(user):
            return queryset

        if user.is_authenticated:
            return queryset.filter(
                Q(user=user) | ~Q(status=SpecialistProfile.AvailabilityStatus.HIDDEN)
            ).distinct()

        return queryset.exclude(status=SpecialistProfile.AvailabilityStatus.HIDDEN)

    def perform_create(self, serializer: Serializer) -> None:
        """
        Создаёт профиль специалиста для текущего пользователя.
        Args:
            serializer: Сериализатор с проверенными данными
        """
        if SpecialistProfile.objects.filter(user=self.request.user).exists():
            raise ValidationError(_("У пользователя уже есть профиль специалиста."))

        serializer.save(
            user=self.request.user,
            created_by=self.request.user,
            updated_by=self.request.user,
        )

    def perform_update(self, serializer: Serializer) -> None:
        """
        Обновляет профиль специалиста и автора изменений.
        Args:
            serializer: Сериализатор с проверенными данными
        """
        serializer.save(updated_by=self.request.user)

    @action(detail=False, methods=["get", "put", "patch"])
    def me(self, request: Request) -> Response:
        """
        Выполняет API-действие `me`.
        Args:
            request: HTTP-запрос текущего пользователя
        """
        profile, created = SpecialistProfile.objects.get_or_create(
            user=request.user,
            defaults={
                "created_by": request.user,
                "updated_by": request.user,
            },
        )

        if request.method == "GET":
            serializer = self.get_serializer(profile)
            return Response(serializer.data)

        serializer = self.get_serializer(
            profile,
            data=request.data,
            partial=request.method == "PATCH",
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)

        if created:
            serializer.instance.created_by = request.user

        return Response(serializer.data)


class ApplicationViewSet(viewsets.ModelViewSet):
    serializer_class = ApplicationSerializer
    filterset_class = ApplicationFilter
    permission_classes = [IsAuthenticated]
    search_fields = (
        "message",
        "project__title",
        "vacancy__title",
        "vacancy__role__name",
        "specialist__user__username",
    )
    ordering_fields = ("applied_at", "reviewed_at", "status")
    ordering = ("-applied_at",)
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self) -> list[object]:
        """
        Возвращает права доступа для текущего действия.
        """
        if self.action in ["accept", "reject"]:
            return [IsAuthenticated(), IsApplicationReviewer()]

        return super().get_permissions()

    def get_queryset(self) -> QuerySet:
        """
        Возвращает queryset с нужными фильтрами и оптимизациями.
        """
        queryset = Application.objects.select_related(
            "project",
            "project__owner",
            "vacancy",
            "vacancy__role",
            "specialist",
            "specialist__user",
            "reviewed_by",
        )

        user = self.request.user

        if is_admin(user):
            return queryset

        return queryset.filter(
            Q(specialist__user=user) | Q(project__owner=user)
        ).distinct()

    @action(detail=True, methods=["post"])
    def accept(self, request: Request, pk: int | None = None) -> Response:
        """
        Выполняет API-действие `accept`.
        Args:
            request: HTTP-запрос текущего пользователя
            pk: Идентификатор объекта
        """
        application = self.get_object()

        try:
            application.accept(reviewed_by=request.user)
        except (DjangoValidationError, IntegrityError) as error:
            raise_serializer_validation(error)

        serializer = self.get_serializer(application)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def reject(self, request: Request, pk: int | None = None) -> Response:
        """
        Выполняет API-действие `reject`.
        Args:
            request: HTTP-запрос текущего пользователя
            pk: Идентификатор объекта
        """
        application = self.get_object()

        try:
            application.reject(reviewed_by=request.user)
        except DjangoValidationError as error:
            raise_serializer_validation(error)

        serializer = self.get_serializer(application)
        return Response(serializer.data)


class InvitationViewSet(viewsets.ModelViewSet):
    serializer_class = InvitationSerializer
    filterset_class = InvitationFilter
    permission_classes = [IsAuthenticated]
    search_fields = (
        "message",
        "project__title",
        "vacancy__title",
        "vacancy__role__name",
        "specialist__user__username",
    )
    ordering_fields = ("invited_at", "responded_at", "status")
    ordering = ("-invited_at",)
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self) -> list[object]:
        """
        Возвращает права доступа для текущего действия.
        """
        if self.action in ["accept", "decline"]:
            return [IsAuthenticated(), IsInvitationRecipientOrAdmin()]

        return super().get_permissions()

    def get_queryset(self) -> QuerySet:
        """
        Возвращает queryset с нужными фильтрами и оптимизациями.
        """
        queryset = Invitation.objects.select_related(
            "project",
            "project__owner",
            "vacancy",
            "vacancy__role",
            "specialist",
            "specialist__user",
            "specialist__main_role",
            "invited_by",
        ).prefetch_related("specialist__technologies")

        user = self.request.user

        if is_admin(user):
            return queryset

        return queryset.filter(
            Q(specialist__user=user) | Q(invited_by=user) | Q(project__owner=user)
        ).distinct()

    @action(detail=True, methods=["post"])
    def accept(self, request: Request, pk: int | None = None) -> Response:
        """
        Выполняет API-действие `accept`.
        Args:
            request: HTTP-запрос текущего пользователя
            pk: Идентификатор объекта
        """
        invitation = self.get_object()

        try:
            invitation.accept()
        except (DjangoValidationError, IntegrityError) as error:
            raise_serializer_validation(error)

        serializer = self.get_serializer(invitation)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def decline(self, request: Request, pk: int | None = None) -> Response:
        """
        Выполняет API-действие `decline`.
        Args:
            request: HTTP-запрос текущего пользователя
            pk: Идентификатор объекта
        """
        invitation = self.get_object()

        try:
            invitation.decline()
        except DjangoValidationError as error:
            raise_serializer_validation(error)

        serializer = self.get_serializer(invitation)
        return Response(serializer.data)


class FavoriteProjectViewSet(viewsets.ModelViewSet):
    serializer_class = FavoriteProjectSerializer
    permission_classes = [IsAuthenticated, IsFavoriteOwner]
    ordering = ("-added_at",)
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self) -> QuerySet:
        """
        Возвращает queryset с нужными фильтрами и оптимизациями.
        """
        return (
            FavoriteProject.objects.select_related("project", "project__owner", "user")
            .prefetch_related("project__technologies", "project__vacancies__role")
            .filter(user=self.request.user)
        )
