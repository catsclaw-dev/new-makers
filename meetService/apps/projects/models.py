from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F, Q, constraints
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords

from apps.directories.models import Role, Technology
from apps.specialists.models import SpecialistProfile


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
        return self.title

    def get_absolute_url(self) -> str:
        return f"/projects/{self.slug}/"

    def is_published(self) -> bool:
        """Проверяет, опубликован ли проект."""
        return self.status == self.Status.PUBLISHED

    def has_open_vacancies(self) -> bool:
        """Проверяет, есть ли у проекта открытые роли."""
        return self.vacancies.filter(status=ProjectVacancy.Status.OPEN).exists()

    def can_publish(self) -> bool:
        """Проект можно публиковать только при наличии открытых ролей."""
        return self.has_open_vacancies()

    def can_be_edited_by(self, user) -> bool:
        """Редактировать проект может владелец или администратор."""
        return bool(user and (user.is_staff or self.owner_id == user.id))

    def save(self, *args, **kwargs):
        """Очищает текстовые поля и создаёт slug, если он не указан."""
        self.title = self.title.strip()
        self.short_description = self.short_description.strip()
        self.description = self.description.strip()
        self.goal = self.goal.strip()

        if not self.slug:
            base_slug = slugify(self.title, allow_unicode=True)[:180] or "project"
            slug = base_slug
            counter = 1

            queryset = Project.objects.filter(slug=slug)
            if self.pk:
                queryset = queryset.exclude(pk=self.pk)

            while queryset.exists():
                counter += 1
                slug = f"{base_slug}-{counter}"
                queryset = Project.objects.filter(slug=slug)
                if self.pk:
                    queryset = queryset.exclude(pk=self.pk)

            self.slug = slug

        super().save(*args, **kwargs)


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
        return f"{self.project} — {self.title}"

    def is_open(self) -> bool:
        """Проверяет, открыта ли роль для откликов."""
        return (
            self.status == self.Status.OPEN and self.current_count < self.required_count
        )

    def remaining_slots(self) -> int:
        """Возвращает количество свободных мест по роли."""
        return max(self.required_count - self.current_count, 0)

    def close_if_filled(self) -> None:
        """Закрывает роль, если нужное количество участников уже набрано."""
        if self.current_count >= self.required_count:
            self.status = self.Status.CLOSED
            self.save(update_fields=["current_count", "status", "updated_at"])

    def add_specialist(self, *, specialist, added_by=None):
        "Атомарное добавление специалиста на вакансию"
        with transaction.atomic():
            vacancy = (
                ProjectVacancy.objects.select_for_update()
                .select_related("project", "role")
                .get(pk=self.pk)
            )

            if not vacancy.is_open():
                raise ValidationError("Вакансия уже закрыта или заполнена.")

            already_member = ProjectMembership.objects.filter(
                project=vacancy.project,
                specialist=specialist,
                status=ProjectMembership.Status.ACTIVE,
            ).exists()

            if already_member:
                raise ValidationError("Специалист уже состоит в команде проекта.")

            membership = ProjectMembership.objects.create(
                project=vacancy.project,
                specialist=specialist,
                role=vacancy.role,
                added_by=added_by,
            )

            vacancy.current_count += 1

            if vacancy.current_count >= vacancy.required_count:
                vacancy.status = ProjectVacancy.Status.CLOSED

            vacancy.save(update_fields=["current_count", "status", "updated_at"])

            return membership

    def save(self, *args, **kwargs):
        self.title = self.title.strip()
        self.description = self.description.strip()

        if self.current_count >= self.required_count:
            self.status = self.Status.CLOSED

        super().save(*args, **kwargs)


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
                name="unique_project_specialist_role",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.specialist} в проекте {self.project}"

    def is_active(self) -> bool:
        """Проверяет, является ли участник активным."""
        return self.status == self.Status.ACTIVE


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
        return f"{self.project} — {self.title}"

    def save(self, *args, **kwargs):
        self.title = self.title.strip()
        super().save(*args, **kwargs)
