from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.db.models import F
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.api.permissions import is_admin
from apps.directories.models import Role, Technology
from apps.interactions.emails import (
    enqueue_application_created_email,
    enqueue_invitation_created_email,
)
from apps.interactions.models import Application, FavoriteProject, Invitation
from apps.projects.models import (
    Project,
    ProjectMembership,
    ProjectTechnology,
    ProjectVacancy,
)
from apps.reviews.models import Review
from apps.specialists.models import SpecialistProfile, SpecialistTechnology

User = get_user_model()


def raise_serializer_validation(error: object) -> None:
    """
    Преобразует Django-ошибку в ошибку сериализатора.
    Args:
        error: Объект ошибки
    """
    if hasattr(error, "message_dict"):
        raise serializers.ValidationError(error.message_dict)

    raise serializers.ValidationError(getattr(error, "messages", error))


class UserBriefSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "display_name",
            "role",
        )
        read_only_fields = fields

    def get_display_name(self, obj: object) -> str:
        """
        Возвращает значение `name`.
        Args:
            obj: Объект модели
        """
        return obj.get_full_name() or obj.username


class RoleSerializer(serializers.ModelSerializer):
    open_vacancies_count = serializers.SerializerMethodField()
    main_specialists_count = serializers.SerializerMethodField()
    preferred_specialists_count = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "is_active",
            "open_vacancies_count",
            "main_specialists_count",
            "preferred_specialists_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")

    def get_open_vacancies_count(self, obj: object) -> int:
        """
        Возвращает значение `open vacancies count`.
        Args:
            obj: Объект модели
        """
        return getattr(
            obj,
            "open_vacancies_count",
            obj.project_vacancies.filter(status=ProjectVacancy.Status.OPEN).count(),
        )

    def get_main_specialists_count(self, obj: object) -> int:
        """
        Возвращает значение `main specialists count`.
        Args:
            obj: Объект модели
        """
        return getattr(
            obj,
            "main_specialists_count",
            obj.main_specialists.count(),
        )

    def get_preferred_specialists_count(self, obj: object) -> int:
        """
        Возвращает значение `preferred specialists count`.
        Args:
            obj: Объект модели
        """
        return getattr(
            obj,
            "preferred_specialists_count",
            obj.preferred_by_specialists.count(),
        )


class TechnologySerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    projects_count = serializers.SerializerMethodField()
    published_projects_count = serializers.SerializerMethodField()
    specialists_count = serializers.SerializerMethodField()

    class Meta:
        model = Technology
        fields = (
            "id",
            "name",
            "slug",
            "category",
            "category_display",
            "description",
            "is_active",
            "projects_count",
            "published_projects_count",
            "specialists_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")

    def get_projects_count(self, obj: object) -> int:
        """
        Возвращает значение `projects count`.
        Args:
            obj: Объект модели
        """
        return getattr(obj, "projects_count", obj.projects.count())

    def get_published_projects_count(self, obj: object) -> int:
        """
        Возвращает значение `published projects count`.
        Args:
            obj: Объект модели
        """
        return getattr(
            obj,
            "published_projects_count",
            obj.projects.filter(status=Project.Status.PUBLISHED).count(),
        )

    def get_specialists_count(self, obj: object) -> int:
        """
        Возвращает значение `specialists count`.
        Args:
            obj: Объект модели
        """
        return getattr(obj, "specialists_count", obj.specialists.count())


class ProjectBriefSerializer(serializers.ModelSerializer):
    owner_name = serializers.SerializerMethodField()
    open_vacancy_count = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = (
            "id",
            "title",
            "slug",
            "short_description",
            "status",
            "owner_name",
            "open_vacancy_count",
        )
        read_only_fields = fields

    def get_owner_name(self, obj: object) -> str:
        """
        Возвращает значение `owner name`.
        Args:
            obj: Объект модели
        """
        return obj.owner.get_full_name() or obj.owner.username

    def get_open_vacancy_count(self, obj: object) -> int:
        """
        Возвращает значение `open vacancy count`.
        Args:
            obj: Объект модели
        """
        return getattr(
            obj,
            "open_vacancy_count",
            obj.vacancies.filter(
                status=ProjectVacancy.Status.OPEN,
                current_count__lt=F("required_count"),
            ).count(),
        )


class ProjectVacancySerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(),
        required=False,
    )
    project_title = serializers.CharField(source="project.title", read_only=True)
    role_detail = RoleSerializer(source="role", read_only=True)
    required_level_display = serializers.CharField(
        source="get_required_level_display",
        read_only=True,
    )
    remaining_slots = serializers.SerializerMethodField()
    is_open = serializers.SerializerMethodField()

    class Meta:
        model = ProjectVacancy
        fields = (
            "id",
            "project",
            "project_title",
            "role",
            "role_detail",
            "title",
            "description",
            "required_level",
            "required_level_display",
            "required_count",
            "current_count",
            "status",
            "remaining_slots",
            "is_open",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "current_count",
            "status",
            "created_at",
            "updated_at",
        )

    def get_remaining_slots(self, obj: object) -> int:
        """
        Возвращает значение `remaining slots`.
        Args:
            obj: Объект модели
        """
        return obj.remaining_slots()

    def get_is_open(self, obj: object) -> bool:
        """
        Возвращает значение `is open`.
        Args:
            obj: Объект модели
        """
        return obj.is_open()

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        """
        Проверяет данные сериализатора.
        Args:
            attrs: Данные сериализатора
        """
        project = self.context.get("project") or attrs.get("project")

        if self.instance is not None and project is None:
            project = self.instance.project

        if project is None:
            raise serializers.ValidationError(
                {"project": _("Укажи проект для открытой роли.")}
            )

        if project.status in [Project.Status.CLOSED, Project.Status.ARCHIVED]:
            raise serializers.ValidationError(
                {"project": _("Нельзя добавлять роли в закрытый или архивный проект.")}
            )

        attrs["project"] = project
        return attrs

    def create(self, validated_data: dict[str, object]) -> object:
        """
        Создаёт объект из проверенных данных.
        Args:
            validated_data: Проверенные данные сериализатора
        """
        try:
            return super().create(validated_data)
        except DjangoValidationError as error:
            raise_serializer_validation(error)

    def update(self, instance: object, validated_data: dict[str, object]) -> object:
        """
        Обновляет объект проверенными данными.
        Args:
            instance: Экземпляр объекта для обновления
            validated_data: Проверенные данные сериализатора
        """
        try:
            return super().update(instance, validated_data)
        except DjangoValidationError as error:
            raise_serializer_validation(error)


class ProjectSerializer(serializers.ModelSerializer):
    owner = UserBriefSerializer(read_only=True)
    stage_display = serializers.CharField(source="get_stage_display", read_only=True)
    participation_format_display = serializers.CharField(
        source="get_participation_format_display",
        read_only=True,
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    technologies = TechnologySerializer(many=True, read_only=True)
    technology_ids = serializers.PrimaryKeyRelatedField(
        queryset=Technology.objects.filter(is_active=True),
        many=True,
        required=False,
        write_only=True,
    )
    vacancies = ProjectVacancySerializer(many=True, read_only=True)
    open_vacancy_count = serializers.SerializerMethodField()
    members_count = serializers.SerializerMethodField()
    favorite_count = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()
    can_apply = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = (
            "id",
            "owner",
            "title",
            "slug",
            "short_description",
            "description",
            "goal",
            "cover_image",
            "stage",
            "stage_display",
            "participation_format",
            "participation_format_display",
            "status",
            "status_display",
            "technologies",
            "technology_ids",
            "vacancies",
            "repository_url",
            "demo_url",
            "created_at",
            "updated_at",
            "open_vacancy_count",
            "members_count",
            "favorite_count",
            "is_favorite",
            "can_manage",
            "can_apply",
        )
        read_only_fields = (
            "owner",
            "slug",
            "status",
            "created_at",
            "updated_at",
        )

    def get_open_vacancy_count(self, obj: object) -> int:
        """
        Возвращает значение `open vacancy count`.
        Args:
            obj: Объект модели
        """
        return getattr(
            obj,
            "open_vacancy_count",
            obj.vacancies.filter(
                status=ProjectVacancy.Status.OPEN,
                current_count__lt=F("required_count"),
            ).count(),
        )

    def get_members_count(self, obj: object) -> int:
        """
        Возвращает значение `members count`.
        Args:
            obj: Объект модели
        """
        return getattr(obj, "members_count", obj.memberships.count())

    def get_favorite_count(self, obj: object) -> int:
        """
        Возвращает значение `favorite count`.
        Args:
            obj: Объект модели
        """
        return getattr(obj, "favorite_count", obj.favorited_by.count())

    def get_is_favorite(self, obj: object) -> bool:
        """
        Возвращает значение `is favorite`.
        Args:
            obj: Объект модели
        """
        annotated_value = getattr(obj, "is_favorited", None)

        if annotated_value is not None:
            return bool(annotated_value)

        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            return False

        return FavoriteProject.objects.filter(
            user=request.user,
            project=obj,
        ).exists()

    def get_can_manage(self, obj: object) -> bool:
        """
        Возвращает значение `can manage`.
        Args:
            obj: Объект модели
        """
        request = self.context.get("request")
        return bool(request and obj.can_be_edited_by(request.user))

    def get_can_apply(self, obj: object) -> bool:
        """
        Возвращает значение `can apply`.
        Args:
            obj: Объект модели
        """
        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            return False

        if obj.owner_id == request.user.id or obj.status != Project.Status.PUBLISHED:
            return False

        specialist = getattr(request.user, "specialist_profile", None)

        if specialist is None:
            return False

        if ProjectMembership.objects.filter(
            project=obj,
            specialist=specialist,
            status=ProjectMembership.Status.ACTIVE,
        ).exists():
            return False

        return obj.vacancies.filter(
            status=ProjectVacancy.Status.OPEN,
            current_count__lt=F("required_count"),
        ).exists()

    def validate_title(self, value: str) -> str:
        """
        Проверяет поле `title`.
        Args:
            value: Проверяемое значение
        """
        return value.strip()

    def validate_short_description(self, value: str) -> str:
        """
        Проверяет поле `short description`.
        Args:
            value: Проверяемое значение
        """
        return value.strip()

    def validate_description(self, value: str) -> str:
        """
        Проверяет поле `description`.
        Args:
            value: Проверяемое значение
        """
        return value.strip()

    def validate_goal(self, value: str) -> str:
        """
        Проверяет поле `goal`.
        Args:
            value: Проверяемое значение
        """
        return value.strip()

    def create(self, validated_data: dict[str, object]) -> object:
        """
        Создаёт объект из проверенных данных.
        Args:
            validated_data: Проверенные данные сериализатора
        """
        technology_ids = validated_data.pop("technology_ids", [])

        try:
            project = super().create(validated_data)
        except DjangoValidationError as error:
            raise_serializer_validation(error)

        self._sync_technologies(project, technology_ids)
        return project

    def update(self, instance: object, validated_data: dict[str, object]) -> object:
        """
        Обновляет объект проверенными данными.
        Args:
            instance: Экземпляр объекта для обновления
            validated_data: Проверенные данные сериализатора
        """
        technology_ids = validated_data.pop("technology_ids", None)

        try:
            project = super().update(instance, validated_data)
        except DjangoValidationError as error:
            raise_serializer_validation(error)

        if technology_ids is not None:
            self._sync_technologies(project, technology_ids)

        return project

    def _sync_technologies(self, project: Project, technologies: list[Technology]) -> None:
        """
        Синхронизирует связанные данные объекта.
        Args:
            project: Объект проекта
            technologies: Список технологий
        """
        ProjectTechnology.objects.filter(project=project).exclude(
            technology__in=technologies
        ).delete()

        for technology in technologies:
            ProjectTechnology.objects.get_or_create(
                project=project,
                technology=technology,
                defaults={"is_required": True},
            )


class SpecialistProfileSerializer(serializers.ModelSerializer):
    user = UserBriefSerializer(read_only=True)
    display_name = serializers.SerializerMethodField()
    main_role_detail = RoleSerializer(source="main_role", read_only=True)
    preferred_roles = RoleSerializer(many=True, read_only=True)
    preferred_role_ids = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.filter(is_active=True),
        many=True,
        required=False,
        write_only=True,
    )
    technologies = TechnologySerializer(many=True, read_only=True)
    technology_ids = serializers.PrimaryKeyRelatedField(
        queryset=Technology.objects.filter(is_active=True),
        many=True,
        required=False,
        write_only=True,
    )
    level_display = serializers.CharField(source="get_level_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    participation_format_display = serializers.CharField(
        source="get_participation_format_display",
        read_only=True,
    )
    is_available = serializers.SerializerMethodField()
    active_projects_count = serializers.SerializerMethodField()
    applications_count = serializers.SerializerMethodField()
    invitations_count = serializers.SerializerMethodField()
    reviews_count = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()

    class Meta:
        model = SpecialistProfile
        fields = (
            "id",
            "user",
            "display_name",
            "main_role",
            "main_role_detail",
            "preferred_roles",
            "preferred_role_ids",
            "technologies",
            "technology_ids",
            "avatar",
            "level",
            "level_display",
            "status",
            "status_display",
            "participation_format",
            "participation_format_display",
            "bio",
            "experience_years",
            "weekly_hours",
            "city",
            "timezone",
            "github_url",
            "gitlab_url",
            "portfolio_url",
            "telegram",
            "created_at",
            "updated_at",
            "is_available",
            "active_projects_count",
            "applications_count",
            "invitations_count",
            "reviews_count",
            "average_rating",
            "can_edit",
        )
        read_only_fields = (
            "user",
            "created_at",
            "updated_at",
        )

    def get_display_name(self, obj: object) -> str:
        """
        Возвращает значение `name`.
        Args:
            obj: Объект модели
        """
        return obj.get_display_name()

    def get_is_available(self, obj: object) -> bool:
        """
        Возвращает значение `is available`.
        Args:
            obj: Объект модели
        """
        return obj.is_available_for_project()

    def get_active_projects_count(self, obj: object) -> int:
        """
        Возвращает значение `active projects count`.
        Args:
            obj: Объект модели
        """
        return getattr(
            obj,
            "active_projects_count",
            obj.project_memberships.filter(
                status=ProjectMembership.Status.ACTIVE,
            ).count(),
        )

    def get_applications_count(self, obj: object) -> int:
        """
        Возвращает значение `applications count`.
        Args:
            obj: Объект модели
        """
        return getattr(obj, "applications_count", obj.applications.count())

    def get_invitations_count(self, obj: object) -> int:
        """
        Возвращает значение `invitations count`.
        Args:
            obj: Объект модели
        """
        return getattr(obj, "invitations_count", obj.invitations.count())

    def get_reviews_count(self, obj: object) -> int:
        """
        Возвращает значение `reviews count`.
        Args:
            obj: Объект модели
        """
        return getattr(obj, "reviews_count", obj.received_reviews.count())

    def get_average_rating(self, obj: object) -> float | None:
        """
        Возвращает значение `average rating`.
        Args:
            obj: Объект модели
        """
        average_rating = getattr(obj, "average_rating", None)

        if average_rating is None:
            return None

        return round(float(average_rating), 2)

    def get_can_edit(self, obj: object) -> bool:
        """
        Возвращает значение `can edit`.
        Args:
            obj: Объект модели
        """
        request = self.context.get("request")
        return bool(
            request
            and request.user.is_authenticated
            and (is_admin(request.user) or obj.user_id == request.user.id)
        )

    def validate_bio(self, value: str) -> str:
        """
        Проверяет поле `bio`.
        Args:
            value: Проверяемое значение
        """
        value = value.strip()

        if value and len(value) < 20:
            raise serializers.ValidationError(
                _("Если заполняешь описание, оно должно быть не короче 20 символов.")
            )

        return value

    def create(self, validated_data: dict[str, object]) -> object:
        """
        Создаёт объект из проверенных данных.
        Args:
            validated_data: Проверенные данные сериализатора
        """
        preferred_role_ids = validated_data.pop("preferred_role_ids", [])
        technology_ids = validated_data.pop("technology_ids", [])

        try:
            profile = super().create(validated_data)
        except DjangoValidationError as error:
            raise_serializer_validation(error)

        profile.preferred_roles.set(preferred_role_ids)
        self._sync_technologies(profile, technology_ids)
        return profile

    def update(self, instance: object, validated_data: dict[str, object]) -> object:
        """
        Обновляет объект проверенными данными.
        Args:
            instance: Экземпляр объекта для обновления
            validated_data: Проверенные данные сериализатора
        """
        preferred_role_ids = validated_data.pop("preferred_role_ids", None)
        technology_ids = validated_data.pop("technology_ids", None)

        try:
            profile = super().update(instance, validated_data)
        except DjangoValidationError as error:
            raise_serializer_validation(error)

        if preferred_role_ids is not None:
            profile.preferred_roles.set(preferred_role_ids)

        if technology_ids is not None:
            self._sync_technologies(profile, technology_ids)

        return profile

    def _sync_technologies(self, profile: SpecialistProfile, technologies: list[Technology]) -> None:
        """
        Синхронизирует связанные данные объекта.
        Args:
            profile: Значение параметра `profile`
            technologies: Список технологий
        """
        SpecialistTechnology.objects.filter(specialist=profile).exclude(
            technology__in=technologies
        ).delete()

        for technology in technologies:
            SpecialistTechnology.objects.get_or_create(
                specialist=profile,
                technology=technology,
                defaults={
                    "level": SpecialistTechnology.SkillLevel.CONFIDENT,
                },
            )


class ApplicationSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(read_only=True)
    project_detail = ProjectBriefSerializer(source="project", read_only=True)
    vacancy_detail = ProjectVacancySerializer(source="vacancy", read_only=True)
    specialist = serializers.PrimaryKeyRelatedField(read_only=True)
    specialist_name = serializers.SerializerMethodField()
    reviewed_by = UserBriefSerializer(read_only=True)

    class Meta:
        model = Application
        fields = (
            "id",
            "project",
            "project_detail",
            "vacancy",
            "vacancy_detail",
            "specialist",
            "specialist_name",
            "message",
            "status",
            "applied_at",
            "reviewed_at",
            "reviewed_by",
        )
        read_only_fields = (
            "project",
            "specialist",
            "status",
            "applied_at",
            "reviewed_at",
            "reviewed_by",
        )

    def get_specialist_name(self, obj: object) -> str:
        """
        Возвращает значение `specialist name`.
        Args:
            obj: Объект модели
        """
        return obj.specialist.get_display_name()

    def validate_message(self, value: str) -> str:
        """
        Проверяет поле `message`.
        Args:
            value: Проверяемое значение
        """
        value = value.strip()

        if not value:
            raise serializers.ValidationError(_("Добавь сопроводительное сообщение."))

        return value

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        """
        Проверяет данные сериализатора.
        Args:
            attrs: Данные сериализатора
        """
        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(_("Для отклика нужно войти в систему."))

        specialist = getattr(request.user, "specialist_profile", None)

        if specialist is None:
            raise serializers.ValidationError(
                _("Чтобы откликнуться на проект, сначала нужен профиль специалиста.")
            )

        vacancy = attrs.get("vacancy")

        if vacancy is None:
            raise serializers.ValidationError({"vacancy": _("Выбери открытую роль.")})

        project = vacancy.project

        if project.owner_id == request.user.id:
            raise serializers.ValidationError(
                {"project": _("Нельзя откликаться на собственный проект.")}
            )

        if project.status != Project.Status.PUBLISHED:
            raise serializers.ValidationError(
                {"project": _("Нельзя откликаться на неопубликованный проект.")}
            )

        if not vacancy.is_open():
            raise serializers.ValidationError(
                {"vacancy": _("Нельзя откликаться на закрытую или заполненную роль.")}
            )

        already_member = ProjectMembership.objects.filter(
            project=project,
            specialist=specialist,
            status=ProjectMembership.Status.ACTIVE,
        ).exists()

        if already_member:
            raise serializers.ValidationError(
                _("Специалист уже состоит в команде проекта.")
            )

        duplicate_exists = Application.objects.filter(
            project=project,
            vacancy=vacancy,
            specialist=specialist,
            status__in=Application.ACTIVE_STATUSES,
        ).exists()

        if duplicate_exists:
            raise serializers.ValidationError(
                _("У специалиста уже есть активный отклик на эту роль.")
            )

        return attrs

    def create(self, validated_data: dict[str, object]) -> object:
        """
        Создаёт объект из проверенных данных.
        Args:
            validated_data: Проверенные данные сериализатора
        """
        request = self.context["request"]
        vacancy = validated_data["vacancy"]

        try:
            application = Application.objects.create(
                project=vacancy.project,
                specialist=request.user.specialist_profile,
                **validated_data,
            )
            enqueue_application_created_email(application.pk)
            return application
        except (DjangoValidationError, IntegrityError) as error:
            raise_serializer_validation(error)


class InvitationSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(read_only=True)
    project_detail = ProjectBriefSerializer(source="project", read_only=True)
    vacancy_detail = ProjectVacancySerializer(source="vacancy", read_only=True)
    specialist_detail = SpecialistProfileSerializer(source="specialist", read_only=True)
    invited_by = UserBriefSerializer(read_only=True)

    class Meta:
        model = Invitation
        fields = (
            "id",
            "project",
            "project_detail",
            "vacancy",
            "vacancy_detail",
            "specialist",
            "specialist_detail",
            "invited_by",
            "message",
            "status",
            "invited_at",
            "responded_at",
        )
        read_only_fields = (
            "project",
            "invited_by",
            "status",
            "invited_at",
            "responded_at",
        )

    def validate_message(self, value: str) -> str:
        """
        Проверяет поле `message`.
        Args:
            value: Проверяемое значение
        """
        return value.strip()

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        """
        Проверяет данные сериализатора.
        Args:
            attrs: Данные сериализатора
        """
        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(
                _("Для приглашения специалиста нужно войти в систему.")
            )

        vacancy = attrs.get("vacancy")
        specialist = attrs.get("specialist")

        if vacancy is None:
            raise serializers.ValidationError({"vacancy": _("Выбери открытую роль.")})

        if specialist is None:
            raise serializers.ValidationError({"specialist": _("Выбери специалиста.")})

        project = vacancy.project

        if not is_admin(request.user) and project.owner_id != request.user.id:
            raise serializers.ValidationError(
                {"project": _("Можно приглашать только в свои проекты.")}
            )

        if specialist.user_id == request.user.id:
            raise serializers.ValidationError(
                {"specialist": _("Нельзя пригласить самого себя в свой проект.")}
            )

        if project.status != Project.Status.PUBLISHED:
            raise serializers.ValidationError(
                {"project": _("Приглашать можно только в опубликованный проект.")}
            )

        if not vacancy.is_open():
            raise serializers.ValidationError(
                {"vacancy": _("Приглашать можно только на открытую роль.")}
            )

        already_member = ProjectMembership.objects.filter(
            project=project,
            specialist=specialist,
            status=ProjectMembership.Status.ACTIVE,
        ).exists()

        if already_member:
            raise serializers.ValidationError(
                _("Специалист уже состоит в команде этого проекта.")
            )

        duplicate_exists = Invitation.objects.filter(
            project=project,
            vacancy=vacancy,
            specialist=specialist,
            status=Invitation.Status.PENDING,
        ).exists()

        if duplicate_exists:
            raise serializers.ValidationError(
                _("Для этой роли уже есть активное приглашение специалисту.")
            )

        return attrs

    def create(self, validated_data: dict[str, object]) -> object:
        """
        Создаёт объект из проверенных данных.
        Args:
            validated_data: Проверенные данные сериализатора
        """
        request = self.context["request"]
        vacancy = validated_data["vacancy"]

        try:
            invitation = Invitation.objects.create(
                project=vacancy.project,
                invited_by=request.user,
                **validated_data,
            )
            enqueue_invitation_created_email(invitation.pk)
            return invitation
        except (DjangoValidationError, IntegrityError) as error:
            raise_serializer_validation(error)


class FavoriteProjectSerializer(serializers.ModelSerializer):
    project_detail = ProjectBriefSerializer(source="project", read_only=True)

    class Meta:
        model = FavoriteProject
        fields = (
            "id",
            "project",
            "project_detail",
            "added_at",
        )
        read_only_fields = ("added_at",)

    def validate_project(self, project: Project) -> Project:
        """
        Проверяет поле `project`.
        Args:
            project: Объект проекта
        """
        request = self.context.get("request")

        if project.status not in [Project.Status.PUBLISHED, Project.Status.CLOSED]:
            raise serializers.ValidationError(
                _("В избранное можно добавить только опубликованный или закрытый проект.")
            )

        if request and request.user.is_authenticated:
            duplicate_exists = FavoriteProject.objects.filter(
                user=request.user,
                project=project,
            ).exists()

            if duplicate_exists:
                raise serializers.ValidationError(_("Проект уже есть в избранном."))

        return project

    def create(self, validated_data: dict[str, object]) -> object:
        """
        Создаёт объект из проверенных данных.
        Args:
            validated_data: Проверенные данные сериализатора
        """
        request = self.context["request"]

        try:
            return FavoriteProject.objects.create(
                user=request.user,
                **validated_data,
            )
        except IntegrityError as error:
            raise_serializer_validation(error)


class ReviewSerializer(serializers.ModelSerializer):
    project_detail = ProjectBriefSerializer(source="project", read_only=True)
    specialist_detail = SpecialistProfileSerializer(source="specialist", read_only=True)
    author = UserBriefSerializer(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_public = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = (
            "id",
            "project",
            "project_detail",
            "author",
            "specialist",
            "specialist_detail",
            "rating",
            "text",
            "status",
            "status_display",
            "is_public",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "author",
            "status",
            "created_at",
            "updated_at",
        )

    def get_is_public(self, obj: object) -> bool:
        """
        Возвращает значение `is public`.
        Args:
            obj: Объект модели
        """
        return obj.is_public()

    def validate_text(self, value: str) -> str:
        """
        Проверяет поле `text`.
        Args:
            value: Проверяемое значение
        """
        value = value.strip()

        if not value:
            raise serializers.ValidationError(_("Текст отзыва обязателен."))

        return value

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        """
        Проверяет данные сериализатора.
        Args:
            attrs: Данные сериализатора
        """
        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(_("Для создания отзыва нужно войти."))

        project = attrs.get("project")
        specialist = attrs.get("specialist")

        if project is None or specialist is None:
            return attrs

        if not is_admin(request.user) and project.owner_id != request.user.id:
            raise serializers.ValidationError(
                {"project": _("Оставить отзыв может владелец проекта или администратор.")}
            )

        if specialist.user_id == request.user.id:
            raise serializers.ValidationError(
                {"specialist": _("Нельзя оставить отзыв самому себе.")}
            )

        if not ProjectMembership.objects.filter(
            project=project,
            specialist=specialist,
        ).exists():
            raise serializers.ValidationError(
                {
                    "specialist": (
                        _("Отзыв можно оставить только специалисту, который участвовал "
                        "в проекте.")
                    )
                }
            )

        return attrs

    def create(self, validated_data: dict[str, object]) -> object:
        """
        Создаёт объект из проверенных данных.
        Args:
            validated_data: Проверенные данные сериализатора
        """
        request = self.context["request"]

        try:
            return Review.objects.create(
                author=request.user,
                **validated_data,
            )
        except (DjangoValidationError, IntegrityError) as error:
            raise_serializer_validation(error)
