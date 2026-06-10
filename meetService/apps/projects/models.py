from __future__ import annotations

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db import IntegrityError
from django.urls import reverse
from django.db.models import F, Q, constraints, Count, QuerySet
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords

from apps.accounts.models import User
from apps.directories.models import Role, Technology
from apps.specialists.models import SpecialistProfile
from apps.common_validators import validate_project_cover_image, validate_project_file


class ProjectQuerySet(models.QuerySet):
    """Набор запросов для проектов."""

    def published(self) -> QuerySet:
        """
        Возвращает только опубликованные проекты.
        """
        return self.filter(status="published")

    def with_open_vacancy_count(self) -> QuerySet:
        """
        Добавляет количество открытых ролей к каждому проекту.
        """
        return self.annotate(
            open_vacancy_count=Count(
                "vacancies",
                filter=Q(
                    vacancies__status="open",
                    vacancies__current_count__lt=F("vacancies__required_count"),
                ),
            )
        )

    def urgent(self) -> QuerySet:
        """
        Возвращает опубликованные проекты, где есть открытые роли.
        """
        return (
            self.published().with_open_vacancy_count().filter(open_vacancy_count__gt=0)
        )


class ProjectManager(models.Manager):
    """Собственный менеджер модели Project."""

    def get_queryset(self) -> QuerySet:
        """
        Возвращает queryset с нужными фильтрами и оптимизациями.
        """
        return ProjectQuerySet(self.model, using=self._db)

    def published(self) -> QuerySet:
        """
        Возвращает только опубликованные проекты.
        """
        return self.get_queryset().published()

    def with_open_vacancy_count(self) -> QuerySet:
        """
        Добавляет количество открытых ролей к каждому проекту.
        """
        return self.get_queryset().with_open_vacancy_count()

    def urgent(self) -> QuerySet:
        """
        Возвращает опубликованные проекты с открытыми ролями.
        """
        return self.get_queryset().urgent()


class Project(models.Model):
    """Проект, для которого владелец собирает IT-команду."""

    class Stage(models.TextChoices):
        IDEA = "idea", _("Идея")
        PROTOTYPE = "prototype", _("Прототип")
        MVP = "mvp", _("MVP")
        DEVELOPMENT = "development", _("Разработка")
        LAUNCH = "launch", _("Запуск")
        GROWTH = "growth", _("Развитие")
        PAUSED = "paused", _("Пауза")
        FINISHED = "finished", _("Завершён")

    class ParticipationFormat(models.TextChoices):
        FREE = "free", _("Энтузиазм")
        PAID = "paid", _("Оплачиваемо")
        EQUITY = "equity", _("Доля")
        MIXED = "mixed", _("Смешанный формат")
        EDUCATIONAL = "educational", _("Учебный проект")

    class Status(models.TextChoices):
        DRAFT = "draft", _("Черновик")
        MODERATION = "moderation", _("На модерации")
        PUBLISHED = "published", _("Опубликован")
        CLOSED = "closed", _("Закрыт")
        ARCHIVED = "archived", _("Архив")

    objects = ProjectManager()

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_projects",
        verbose_name=_("владелец проекта"),
        help_text=_("Пользователь, который создал и ведёт проект."),
    )
    title = models.CharField(
        max_length=200,
        verbose_name=_("название проекта"),
    )
    slug = models.SlugField(
        max_length=220,
        unique=True,
        blank=True,
        allow_unicode=True,
        verbose_name=_("URL-идентификатор"),
        help_text=_("Используется для будущей детальной страницы проекта."),
    )
    short_description = models.CharField(
        max_length=300,
        verbose_name=_("краткое описание"),
        help_text=_("Короткое описание для карточки проекта."),
    )
    description = models.TextField(
        verbose_name=_("подробное описание"),
    )
    goal = models.TextField(
        verbose_name=_("цель проекта"),
        help_text=_("Что проект должен решить или какой результат должен получить."),
    )
    cover_image = models.ImageField(
        upload_to="projects/covers/",
        blank=True,
        null=True,
        validators=[validate_project_cover_image],
        verbose_name=_("обложка проекта"),
    )
    stage = models.CharField(
        max_length=30,
        choices=Stage.choices,
        default=Stage.IDEA,
        verbose_name=_("стадия"),
    )
    participation_format = models.CharField(
        max_length=30,
        choices=ParticipationFormat.choices,
        default=ParticipationFormat.FREE,
        verbose_name=_("формат участия"),
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name=_("статус"),
    )
    technologies = models.ManyToManyField(
        Technology,
        through="ProjectTechnology",
        related_name="projects",
        verbose_name=_("технологии"),
    )
    members = models.ManyToManyField(
        SpecialistProfile,
        through="ProjectMembership",
        related_name="team_projects",
        verbose_name=_("участники команды"),
    )
    repository_url = models.URLField(
        blank=True,
        verbose_name=_("ссылка на репозиторий"),
    )
    demo_url = models.URLField(
        blank=True,
        verbose_name=_("демо-ссылка"),
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("дата создания"),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("дата изменения"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_projects",
        verbose_name=_("создал"),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_projects",
        verbose_name=_("изменил"),
    )

    history = HistoricalRecords(verbose_name=_("история изменений"))

    class Meta:
        verbose_name = _("проект")
        verbose_name_plural = _("проекты")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """
        Возвращает строковое представление объекта.
        """
        return self.title

    def get_absolute_url(self) -> str:
        """
        Возвращает значение `absolute url`.
        """
        return reverse("projects:project_detail", kwargs={"slug": self.slug})

    def is_published(self) -> bool:
        """
        Проверяет, опубликован ли проект.
        """
        return self.status == self.Status.PUBLISHED

    def has_open_vacancies(self) -> bool:
        """
        Проверяет, есть ли у проекта открытые роли.
        """
        return self.vacancies.filter(
            status=ProjectVacancy.Status.OPEN,
            current_count__lt=F("required_count"),
        ).exists()

    def can_publish(self) -> bool:
        """
        Проект можно публиковать только при наличии открытых ролей.
        """
        return self.has_open_vacancies()

    def can_be_edited_by(self, user: User | None) -> bool:
        """
        Редактировать проект может владелец или администратор.
        Args:
            user: Объект пользователя
        """
        return bool(user and (user.is_staff or self.owner_id == user.id))

    def archive(self, *, archived_by: User) -> None:
        """Атомарно архивирует проект и завершает связанные ожидания."""
        from apps.interactions.emails import enqueue_application_status_email
        from apps.interactions.models import Application, FavoriteProject, Invitation

        with transaction.atomic():
            project = Project.objects.select_for_update().get(pk=self.pk)
            archived_at = timezone.now()

            FavoriteProject.objects.filter(project=project).delete()

            vacancies = ProjectVacancy.objects.select_for_update().filter(
                project=project
            )
            for vacancy in vacancies:
                if vacancy.status != ProjectVacancy.Status.CLOSED:
                    vacancy.status = ProjectVacancy.Status.CLOSED
                    vacancy.save(update_fields=["status", "updated_at"])

            applications = Application.objects.select_for_update().filter(
                project=project,
                status=Application.Status.PENDING,
            )
            for application in applications:
                application.status = Application.Status.REJECTED
                application.reviewed_at = archived_at
                application.reviewed_by = archived_by
                application.save(
                    update_fields=["status", "reviewed_at", "reviewed_by"]
                )
                enqueue_application_status_email(application.pk)

            invitations = Invitation.objects.select_for_update().filter(
                project=project,
                status=Invitation.Status.PENDING,
            )
            for invitation in invitations:
                invitation.status = Invitation.Status.EXPIRED
                invitation.responded_at = archived_at
                invitation.save(update_fields=["status", "responded_at"])

            project.status = self.Status.ARCHIVED
            project.updated_by = archived_by
            project.save(update_fields=["status", "updated_by", "updated_at"])

        self.status = project.status
        self.updated_by = project.updated_by
        self.updated_at = project.updated_at

    def save(self, *args: object, **kwargs: object) -> None:
        """
        Очищает текстовые поля и создаёт slug, если он не указан.
        Args:
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы
        """
        self.title = self.title.strip()
        self.short_description = self.short_description.strip()
        self.description = self.description.strip()
        self.goal = self.goal.strip()

        if self.slug or self.pk:
            super().save(*args, **kwargs)
            return

        base_slug = slugify(self.title, allow_unicode=True)[:180] or "project"

        for counter in range(1, 1001):
            self.slug = base_slug if counter == 1 else f"{base_slug}-{counter}"
            try:
                with transaction.atomic():
                    super().save(*args, **kwargs)
                return
            except IntegrityError:
                if not Project.objects.filter(slug=self.slug).exists():
                    raise
                self.pk = None
                self._state.adding = True

        raise ValidationError(_("Не удалось подобрать уникальный URL проекта."))


class ProjectTechnology(models.Model):
    """Промежуточная таблица технологий проекта."""

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="project_technologies",
        verbose_name=_("проект"),
    )
    technology = models.ForeignKey(
        Technology,
        on_delete=models.CASCADE,
        related_name="project_technologies",
        verbose_name=_("технология"),
    )
    is_required = models.BooleanField(
        default=True,
        verbose_name=_("обязательная технология"),
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("дата добавления"),
    )

    class Meta:
        verbose_name = _("технология проекта")
        verbose_name_plural = _("технологии проектов")
        ordering = ["project", "technology__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "technology"],
                name="unique_project_technology",
            ),
        ]

    def __str__(self) -> str:
        """
        Возвращает строковое представление объекта.
        """
        return f"{self.project} — {self.technology}"


class ProjectVacancy(models.Model):
    """Открытая роль в проекте."""

    class Status(models.TextChoices):
        OPEN = "open", _("Открыта")
        PAUSED = "paused", _("На паузе")
        CLOSED = "closed", _("Закрыта")

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="vacancies",
        verbose_name=_("проект"),
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="project_vacancies",
        verbose_name=_("роль"),
    )
    title = models.CharField(
        max_length=200,
        verbose_name=_("название открытой роли"),
        help_text=_("Например: Junior Frontend-разработчик."),
    )
    description = models.TextField(
        verbose_name=_("описание роли"),
    )
    required_level = models.CharField(
        max_length=20,
        choices=SpecialistProfile.Level.choices,
        default=SpecialistProfile.Level.JUNIOR,
        verbose_name=_("требуемый уровень"),
    )
    required_count = models.PositiveSmallIntegerField(
        default=1,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(20),
        ],
        verbose_name=_("требуется человек"),
    )
    current_count = models.PositiveSmallIntegerField(
        default=0,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(20),
        ],
        verbose_name=_("уже набрано"),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        verbose_name=_("статус"),
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("дата создания"),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("дата изменения"),
    )

    history = HistoricalRecords(verbose_name=_("история изменений"))

    class Meta:
        verbose_name = _("открытая роль проекта")
        verbose_name_plural = _("открытые роли проектов")
        ordering = ["project", "role__name", "title"]
        constraints = [
            models.CheckConstraint(
                condition=Q(current_count__lte=F("required_count")),
                name="vacancy_current_count_lte_required_count",
            ),
        ]

    def __str__(self) -> str:
        """
        Возвращает строковое представление объекта.
        """
        return f"{self.project} — {self.title}"

    def is_open(self) -> bool:
        """
        Проверяет, открыта ли роль для откликов.
        """
        return (
            self.project.status == Project.Status.PUBLISHED
            and self.status == self.Status.OPEN
            and self.current_count < self.required_count
        )

    def remaining_slots(self) -> int:
        """
        Возвращает количество свободных мест по роли.
        """
        return max(self.required_count - self.current_count, 0)

    def close_if_filled(self) -> None:
        """
        Закрывает роль, если нужное количество участников уже набрано.
        """
        if self.current_count >= self.required_count:
            self.status = self.Status.CLOSED
            self.save(update_fields=["current_count", "status", "updated_at"])

    def add_specialist(
        self,
        *,
        specialist: SpecialistProfile,
        added_by: User | None = None,
    ) -> ProjectMembership:
        """
        Атомарное добавление специалиста на конкретную роль проекта.
        Args:
            specialist: Профиль специалиста
            added_by: Пользователь, добавивший участника
        """
        with transaction.atomic():
            vacancy = (
                ProjectVacancy.objects.select_for_update()
                .select_related("project", "role")
                .get(pk=self.pk)
            )
            vacancy.project = Project.objects.select_for_update().get(
                pk=vacancy.project_id
            )

            if not vacancy.is_open():
                raise ValidationError(_("Роль уже закрыта или заполнена."))

            already_member = ProjectMembership.objects.filter(
                project=vacancy.project,
                specialist=specialist,
                status__in=[
                    ProjectMembership.Status.ACTIVE,
                    ProjectMembership.Status.PAUSED,
                ],
            ).first()

            if already_member:
                raise ValidationError(_("Специалист уже состоит в команде проекта."))

            membership = ProjectMembership.objects.create(
                project=vacancy.project,
                specialist=specialist,
                vacancy=vacancy,
                role=vacancy.role,
                status=ProjectMembership.Status.ACTIVE,
                left_at=None,
                added_by=added_by,
            )

            vacancy.sync_current_count()

            return membership

    def save(self, *args: object, **kwargs: object) -> None:
        """
        Сохраняет объект с учетом бизнес-правил.
        Args:
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы
        """
        self.title = self.title.strip()
        self.description = self.description.strip()

        if self.current_count >= self.required_count:
            self.status = self.Status.CLOSED

        super().save(*args, **kwargs)

    def sync_current_count(self) -> None:
        """Пересчитывает количество занятых мест по фактическим участникам команды."""
        active_statuses = [
            ProjectMembership.Status.ACTIVE,
            ProjectMembership.Status.PAUSED,
        ]

        actual_count = self.memberships.filter(status__in=active_statuses).count()

        if self.current_count != actual_count:
            self.current_count = actual_count
            self.save(update_fields=["current_count", "updated_at"])

        self.close_if_filled()


class ProjectMembership(models.Model):
    """Участник команды проекта."""

    class Status(models.TextChoices):
        ACTIVE = "active", _("Активен")
        PAUSED = "paused", _("На паузе")
        LEFT = "left", _("Покинул проект")

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name=_("проект"),
    )
    specialist = models.ForeignKey(
        SpecialistProfile,
        on_delete=models.CASCADE,
        related_name="project_memberships",
        verbose_name=_("специалист"),
    )

    vacancy = models.ForeignKey(
        ProjectVacancy,
        on_delete=models.PROTECT,
        related_name="memberships",
        null=True,
        blank=True,
        verbose_name=_("открытая роль проекта"),
        help_text=_(
            "Конкретная роль проекта, через которую специалист попал в команду."
        ),
    )

    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="project_memberships",
        verbose_name=_("роль в команде"),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name=_("статус участия"),
    )
    joined_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("дата вступления"),
    )
    left_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("дата выхода"),
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="added_project_memberships",
        verbose_name=_("добавил"),
    )

    history = HistoricalRecords(verbose_name=_("история изменений"))

    class Meta:
        verbose_name = _("участник команды")
        verbose_name_plural = _("участники команд")
        ordering = ["project", "role__name", "specialist"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "specialist", "role"],
                condition=Q(status__in=["active", "paused"]),
                name="unique_active_project_specialist_role",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status="left", left_at__isnull=False)
                    | (~Q(status="left") & Q(left_at__isnull=True))
                ),
                name="membership_left_at_matches_status",
            ),
        ]

    def __str__(self) -> str:
        """
        Возвращает строковое представление объекта.
        """
        return f"{self.specialist} в проекте {self.project}"

    def is_active(self) -> bool:
        """
        Проверяет, является ли участник активным.
        """
        return self.status == self.Status.ACTIVE

    def clean(self) -> None:
        """Проверяет согласованность проекта, роли, вакансии и статуса."""
        errors = {}
        active_statuses = [self.Status.ACTIVE, self.Status.PAUSED]

        if self.vacancy_id:
            vacancy = self.vacancy

            if self.project_id and vacancy.project_id != self.project_id:
                errors["vacancy"] = _("Выбранная роль относится к другому проекту.")

            if self.role_id and vacancy.role_id != self.role_id:
                errors["role"] = _("Роль участника не совпадает с ролью вакансии.")

            previous = None
            if self.pk:
                previous = ProjectMembership.objects.filter(pk=self.pk).values(
                    "vacancy_id",
                    "status",
                ).first()

            needs_free_slot = self.status in active_statuses and (
                previous is None
                or previous["vacancy_id"] != self.vacancy_id
                or previous["status"] not in active_statuses
            )

            if needs_free_slot:
                if not vacancy.is_open():
                    errors["vacancy"] = _(
                        "Занять место можно только в открытой роли опубликованного проекта."
                    )
                else:
                    occupied_count = ProjectMembership.objects.filter(
                        vacancy=vacancy,
                        status__in=active_statuses,
                    ).exclude(pk=self.pk).count()

                    if occupied_count >= vacancy.required_count:
                        errors["vacancy"] = _("В выбранной роли проекта нет свободных мест.")

        if self.status == self.Status.LEFT and self.left_at is None:
            errors["left_at"] = _("Для покинувшего проект участника нужна дата выхода.")

        if self.status != self.Status.LEFT and self.left_at is not None:
            errors["left_at"] = _(
                "Дата выхода допустима только для покинувшего проект участника."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args: object, **kwargs: object) -> None:
        """Нормализует дату выхода и валидирует бизнес-инварианты."""
        if self.status == self.Status.LEFT:
            self.left_at = self.left_at or timezone.now()
        else:
            self.left_at = None

        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"left_at"}

        self.full_clean()
        super().save(*args, **kwargs)

    def move_to(
        self,
        *,
        vacancy: ProjectVacancy,
        status: str,
    ) -> ProjectMembership:
        """Атомарно меняет вакансию или статус участия и пересчитывает места."""
        with transaction.atomic():
            membership = ProjectMembership.objects.select_for_update().get(pk=self.pk)

            if membership.status == self.Status.LEFT:
                raise ValidationError(
                    _("Историческую запись покинувшего проект участника нельзя менять.")
                )

            vacancy_ids = sorted(
                {
                    vacancy.pk,
                    *(
                        [membership.vacancy_id]
                        if membership.vacancy_id is not None
                        else []
                    ),
                }
            )
            locked_vacancies = {
                item.pk: item
                for item in ProjectVacancy.objects.select_for_update()
                .select_related("project", "role")
                .filter(pk__in=vacancy_ids)
                .order_by("pk")
            }
            target_vacancy = locked_vacancies[vacancy.pk]
            old_vacancy = locked_vacancies.get(membership.vacancy_id)

            if target_vacancy.project_id != membership.project_id:
                raise ValidationError(_("Выбранная роль относится к другому проекту."))

            if status == self.Status.LEFT and target_vacancy.pk != membership.vacancy_id:
                raise ValidationError(
                    _("При выходе участника оставь его текущую роль проекта.")
                )

            membership.vacancy = target_vacancy
            membership.role = target_vacancy.role
            membership.status = status
            membership.save()

            if old_vacancy is not None:
                old_vacancy.sync_current_count()

            if old_vacancy is None or old_vacancy.pk != target_vacancy.pk:
                target_vacancy.sync_current_count()

            self.project = membership.project
            self.specialist = membership.specialist
            self.vacancy = membership.vacancy
            self.role = membership.role
            self.status = membership.status
            self.left_at = membership.left_at

            return membership


class ProjectFile(models.Model):
    """Файл, прикреплённый к проекту."""

    class FileType(models.TextChoices):
        DOCUMENT = "document", _("Документ")
        IMAGE = "image", _("Изображение")
        PRESENTATION = "presentation", _("Презентация")
        ARCHIVE = "archive", _("Архив")
        OTHER = "other", _("Другое")

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="files",
        verbose_name=_("проект"),
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_project_files",
        verbose_name=_("загрузил"),
    )
    file = models.FileField(
        upload_to="projects/files/",
        validators=[validate_project_file],
        verbose_name=_("файл"),
    )
    file_type = models.CharField(
        max_length=30,
        choices=FileType.choices,
        default=FileType.OTHER,
        verbose_name=_("тип файла"),
    )
    title = models.CharField(
        max_length=200,
        verbose_name=_("название файла"),
    )
    uploaded_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("дата загрузки"),
    )

    class Meta:
        verbose_name = _("файл проекта")
        verbose_name_plural = _("файлы проектов")
        ordering = ["-uploaded_at"]

    def __str__(self) -> str:
        """
        Возвращает строковое представление объекта.
        """
        return f"{self.project} — {self.title}"

    def save(self, *args: object, **kwargs: object) -> None:
        """
        Сохраняет объект с учетом бизнес-правил.
        Args:
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы
        """
        self.title = self.title.strip()
        super().save(*args, **kwargs)
