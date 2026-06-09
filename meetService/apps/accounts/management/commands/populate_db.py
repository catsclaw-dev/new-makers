from __future__ import annotations

import random
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from faker import Faker
from PIL import Image, ImageDraw

from apps.directories.models import Role, Technology
from apps.interactions.models import Application, FavoriteProject, Invitation
from apps.projects.models import (
    Project,
    ProjectFile,
    ProjectMembership,
    ProjectTechnology,
    ProjectVacancy,
)
from apps.specialists.models import SpecialistProfile, SpecialistTechnology


fake = Faker("ru_RU")
User = get_user_model()


ROLE_DATA = [
    (
        "Frontend-разработчик",
        "frontend-developer",
        "Разрабатывает пользовательский интерфейс и клиентскую часть приложения.",
    ),
    (
        "Backend-разработчик",
        "backend-developer",
        "Отвечает за серверную логику, API и интеграции.",
    ),
    (
        "Fullstack-разработчик",
        "fullstack-developer",
        "Работает и с frontend, и с backend частью проекта.",
    ),
    (
        "UI/UX-дизайнер",
        "ui-ux-designer",
        "Проектирует интерфейсы, пользовательские сценарии и визуальный стиль.",
    ),
    (
        "QA-инженер",
        "qa-engineer",
        "Тестирует продукт, находит ошибки и контролирует качество.",
    ),
    (
        "DevOps-инженер",
        "devops-engineer",
        "Настраивает инфраструктуру, деплой, CI/CD и окружения.",
    ),
    (
        "Project Manager",
        "project-manager",
        "Управляет задачами, сроками, командой и коммуникацией.",
    ),
    ("Data Scientist", "data-scientist", "Анализирует данные и создаёт ML-модели."),
    ("Mobile-разработчик", "mobile-developer", "Разрабатывает мобильные приложения."),
    (
        "Product Owner",
        "product-owner",
        "Формирует видение продукта, цели и приоритеты.",
    ),
]


TECHNOLOGY_DATA = [
    ("Python", "python", Technology.TechnologyCategory.LANGUAGE),
    ("Django", "django", Technology.TechnologyCategory.FRAMEWORK),
    (
        "Django REST Framework",
        "django-rest-framework",
        Technology.TechnologyCategory.FRAMEWORK,
    ),
    ("JavaScript", "javascript", Technology.TechnologyCategory.LANGUAGE),
    ("TypeScript", "typescript", Technology.TechnologyCategory.LANGUAGE),
    ("React", "react", Technology.TechnologyCategory.FRAMEWORK),
    ("Vue.js", "vue-js", Technology.TechnologyCategory.FRAMEWORK),
    ("PostgreSQL", "postgresql", Technology.TechnologyCategory.DATABASE),
    ("SQLite", "sqlite", Technology.TechnologyCategory.DATABASE),
    ("Docker", "docker", Technology.TechnologyCategory.DEVOPS),
    ("Git", "git", Technology.TechnologyCategory.DEVOPS),
    ("Figma", "figma", Technology.TechnologyCategory.DESIGN),
    ("Pytest", "pytest", Technology.TechnologyCategory.TESTING),
    ("Selenium", "selenium", Technology.TechnologyCategory.TESTING),
    ("FastAPI", "fastapi", Technology.TechnologyCategory.FRAMEWORK),
]


PROJECT_IDEAS = [
    "Платформа для поиска pet-проектов",
    "Сервис командной работы для студентов",
    "Трекер задач для стартап-команд",
    "Маркетплейс наставников по программированию",
    "Сервис подбора учебных команд",
    "CRM для маленьких IT-команд",
    "Платформа проведения хакатонов",
    "Сервис поиска дизайнеров для MVP",
    "AI-помощник для планирования спринтов",
    "Каталог open-source инициатив",
    "Платформа обмена код-ревью",
    "Сервис портфолио для начинающих разработчиков",
]


class Command(BaseCommand):
    help = "Заполняет базу данных демонстрационными данными через Faker."

    def add_arguments(self, parser: object) -> None:
        """
        Добавляет аргументы management-команды.
        Args:
            parser: Парсер аргументов команды
        """
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Удалить старые демонстрационные данные перед заполнением.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Seed для повторяемой генерации данных.",
        )

    @transaction.atomic
    def handle(self, *args: object, **options: dict[str, object]) -> None:
        """
        Выполняет management-команду.
        Args:
            *args: Позиционные аргументы
            **options: Дополнительные параметры выполнения
        """
        random.seed(options["seed"])
        Faker.seed(options["seed"])

        if options["clear"]:
            self.clear_data()

        roles = self.create_roles()
        technologies = self.create_technologies()

        users = self.create_users(count=24, prefix="user")
        owners = users[:6]

        specialists = self.create_specialist_profiles(users, roles, technologies)

        projects = self.create_projects(owners, technologies)
        vacancies = self.create_project_vacancies(projects, roles)
        memberships = self.create_memberships(projects, vacancies, specialists, owners)
        applications = self.create_applications(
            projects, vacancies, specialists, memberships
        )
        invitations = self.create_invitations(
            projects, vacancies, specialists, owners, memberships
        )
        favorites = self.create_favorites(projects, users)
        files = self.create_project_files(projects)

        self.sync_vacancy_counts(vacancies)

        self.stdout.write(self.style.SUCCESS("База данных успешно заполнена."))
        self.stdout.write(f"Ролей: {len(roles)}")
        self.stdout.write(f"Технологий: {len(technologies)}")
        self.stdout.write(f"Пользователей: {len(users)}")
        self.stdout.write(f"Динамических владельцев проектов: {len(owners)}")
        self.stdout.write(f"Профилей специалистов: {len(specialists)}")
        self.stdout.write(f"Проектов: {len(projects)}")
        self.stdout.write(f"Открытых ролей: {len(vacancies)}")
        self.stdout.write(f"Участников команд: {len(memberships)}")
        self.stdout.write(f"Откликов: {len(applications)}")
        self.stdout.write(f"Приглашений: {len(invitations)}")
        self.stdout.write(f"Избранных проектов: {len(favorites)}")
        self.stdout.write(f"Файлов проектов: {len(files)}")

    def clear_data(self) -> None:
        """
        Очищает демонстрационные данные, не удаляя суперпользователей.
        """
        FavoriteProject.objects.all().delete()
        Invitation.objects.all().delete()
        Application.objects.all().delete()

        ProjectFile.objects.all().delete()
        ProjectMembership.objects.all().delete()
        ProjectVacancy.objects.all().delete()
        ProjectTechnology.objects.all().delete()
        Project.objects.all().delete()

        SpecialistTechnology.objects.all().delete()
        SpecialistProfile.objects.all().delete()

        Role.objects.all().delete()
        Technology.objects.all().delete()

        User.objects.filter(is_superuser=False).delete()

        self.stdout.write(self.style.WARNING("Старые демонстрационные данные удалены."))

    def create_roles(self) -> list[object]:
        """
        Создает связанные данные приложения.
        """
        roles = []

        for name, slug, description in ROLE_DATA:
            role, _ = Role.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "description": description,
                    "is_active": True,
                },
            )
            roles.append(role)

        return roles

    def create_technologies(self) -> list[object]:
        """
        Создает связанные данные приложения.
        """
        technologies = []

        for name, slug, category in TECHNOLOGY_DATA:
            technology, _ = Technology.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "category": category,
                    "description": f"{name} используется в IT-проектах для разработки, тестирования или поддержки продукта.",
                    "is_active": True,
                },
            )
            technologies.append(technology)

        return technologies

    def create_users(self, count: int, prefix: str) -> list[object]:
        """
        Создаёт пользователей как специалистов по умолчанию.
        Args:
            count: Количество объектов
            prefix: Префикс для создаваемых объектов
        """
        users = []

        for index in range(1, count + 1):
            username = f"{prefix}_{index}_{fake.unique.user_name()}"
            email = fake.unique.email()

            user = User.objects.create_user(
                username=username,
                email=email,
                password="Qwerty12345!",
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                role=User.UserRole.SPECIALIST,
                is_active=True,
            )
            users.append(user)

        return users

    def create_specialist_profiles(
        self, users: object, roles: list[Role], technologies: list[Technology]
    ) -> list[object]:
        """
        Создает связанные данные приложения.
        Args:
            users: Список пользователей
            roles: Список ролей
            technologies: Список технологий
        """
        profiles = []

        for user in users:
            main_role = random.choice(roles)
            profile = SpecialistProfile.objects.create(
                user=user,
                main_role=main_role,
                avatar=self.generate_image_file(
                    text=user.first_name[:1] or "S",
                    filename=f"avatar_{user.username}.png",
                    size=(300, 300),
                ),
                level=random.choice(
                    [
                        SpecialistProfile.Level.INTERN,
                        SpecialistProfile.Level.JUNIOR,
                        SpecialistProfile.Level.MIDDLE,
                        SpecialistProfile.Level.SENIOR,
                    ]
                ),
                status=random.choice(
                    [
                        SpecialistProfile.AvailabilityStatus.LOOKING,
                        SpecialistProfile.AvailabilityStatus.OPEN,
                        SpecialistProfile.AvailabilityStatus.BUSY,
                    ]
                ),
                participation_format=random.choice(
                    [
                        SpecialistProfile.ParticipationFormat.REMOTE,
                        SpecialistProfile.ParticipationFormat.HYBRID,
                        SpecialistProfile.ParticipationFormat.ANY,
                    ]
                ),
                bio=f"{fake.text(max_nb_chars=220)} Интересуюсь командной разработкой, pet-проектами и продуктовым подходом.",
                experience_years=random.randint(0, 8),
                weekly_hours=random.randint(5, 35),
                city=fake.city_name(),
                timezone="Europe/Moscow",
                github_url=f"https://github.com/{user.username}",
                gitlab_url=f"https://gitlab.com/{user.username}",
                portfolio_url=fake.url(),
                telegram=f"@{user.username}",
                created_by=user,
                updated_by=user,
            )

            preferred_roles = random.sample(roles, k=random.randint(1, 3))
            profile.preferred_roles.set(preferred_roles)

            selected_technologies = random.sample(technologies, k=random.randint(3, 7))
            for technology in selected_technologies:
                SpecialistTechnology.objects.create(
                    specialist=profile,
                    technology=technology,
                    level=random.choice(
                        [
                            SpecialistTechnology.SkillLevel.BASIC,
                            SpecialistTechnology.SkillLevel.CONFIDENT,
                            SpecialistTechnology.SkillLevel.ADVANCED,
                            SpecialistTechnology.SkillLevel.EXPERT,
                        ]
                    ),
                    years_of_experience=random.randint(0, 6),
                    is_primary=random.choice([True, False, False]),
                )

            profiles.append(profile)

        return profiles

    def create_projects(
        self, owners: list[User], technologies: list[Technology]
    ) -> list[object]:
        """
        Создает связанные данные приложения.
        Args:
            owners: Список владельцев проектов
            technologies: Список технологий
        """
        projects = []

        for index, title in enumerate(PROJECT_IDEAS, start=1):
            owner = random.choice(owners)
            slug = slugify(title, allow_unicode=True)

            project = Project.objects.create(
                owner=owner,
                title=title,
                slug=f"{slug}-{index}",
                short_description=fake.sentence(nb_words=14),
                description=(
                    f"{fake.text(max_nb_chars=420)} "
                    "Проект ориентирован на командную разработку, прозрачные роли и быстрый запуск MVP."
                ),
                goal=f"Создать рабочий прототип: {fake.catch_phrase()}.",
                cover_image=self.generate_image_file(
                    text=f"P{index}",
                    filename=f"project_cover_{index}.png",
                    size=(900, 500),
                ),
                stage=random.choice(
                    [
                        Project.Stage.IDEA,
                        Project.Stage.PROTOTYPE,
                        Project.Stage.MVP,
                        Project.Stage.DEVELOPMENT,
                        Project.Stage.LAUNCH,
                    ]
                ),
                participation_format=random.choice(
                    [
                        Project.ParticipationFormat.FREE,
                        Project.ParticipationFormat.PAID,
                        Project.ParticipationFormat.EQUITY,
                        Project.ParticipationFormat.MIXED,
                        Project.ParticipationFormat.EDUCATIONAL,
                    ]
                ),
                status=random.choice(
                    [
                        Project.Status.PUBLISHED,
                        Project.Status.PUBLISHED,
                        Project.Status.PUBLISHED,
                        Project.Status.CLOSED,
                        Project.Status.MODERATION,
                        Project.Status.DRAFT,
                        Project.Status.ARCHIVED,
                    ]
                ),
                repository_url=f"https://github.com/{owner.username}/{slug}",
                demo_url=fake.url(),
                created_by=owner,
                updated_by=owner,
            )

            selected_technologies = random.sample(technologies, k=random.randint(3, 6))
            for technology in selected_technologies:
                ProjectTechnology.objects.create(
                    project=project,
                    technology=technology,
                    is_required=random.choice([True, True, False]),
                )

            projects.append(project)

        return projects

    def create_project_vacancies(
        self, projects: list[Project], roles: list[Role]
    ) -> list[object]:
        """
        Создает связанные данные приложения.
        Args:
            projects: Список проектов
            roles: Список ролей
        """
        vacancies = []

        for project in projects:
            selected_roles = random.sample(roles, k=random.randint(2, 4))

            for role in selected_roles:
                vacancy = ProjectVacancy.objects.create(
                    project=project,
                    role=role,
                    title=f"{role.name} в команду проекта",
                    description=(
                        f"{fake.text(max_nb_chars=240)} "
                        "Нужно участвовать в обсуждении задач, делать небольшие итерации и поддерживать коммуникацию."
                    ),
                    required_level=random.choice(
                        [
                            SpecialistProfile.Level.INTERN,
                            SpecialistProfile.Level.JUNIOR,
                            SpecialistProfile.Level.MIDDLE,
                            SpecialistProfile.Level.SENIOR,
                        ]
                    ),
                    required_count=random.randint(1, 3),
                    current_count=0,
                    status=ProjectVacancy.Status.OPEN,
                )
                vacancies.append(vacancy)

        return vacancies

    def create_memberships(
        self,
        projects: list[Project],
        vacancies: list[ProjectVacancy],
        specialists: list[SpecialistProfile],
        owners: list[User],
    ) -> list[object]:
        """
        Создает связанные данные приложения.
        Args:
            projects: Список проектов
            vacancies: Список открытых ролей
            specialists: Список профилей специалистов
            owners: Список владельцев проектов
        """
        memberships = []
        used_pairs = set()

        published_projects = [
            project
            for project in projects
            if project.status == Project.Status.PUBLISHED
        ]

        for project in published_projects:
            project_vacancies = [
                vacancy for vacancy in vacancies if vacancy.project_id == project.id
            ]
            random.shuffle(project_vacancies)

            for vacancy in project_vacancies[
                : random.randint(1, min(2, len(project_vacancies)))
            ]:
                available_specialists = [
                    specialist
                    for specialist in specialists
                    if specialist.user_id != project.owner_id
                    and (project.id, specialist.id, vacancy.role_id) not in used_pairs
                ]

                if not available_specialists:
                    continue

                specialist = random.choice(available_specialists)

                membership = ProjectMembership.objects.create(
                    project=project,
                    specialist=specialist,
                    vacancy=vacancy,
                    role=vacancy.role,
                    status=random.choice(
                        [
                            ProjectMembership.Status.ACTIVE,
                            ProjectMembership.Status.ACTIVE,
                            ProjectMembership.Status.PAUSED,
                        ]
                    ),
                    added_by=random.choice(owners),
                )
                used_pairs.add((project.id, specialist.id, vacancy.role_id))
                memberships.append(membership)

        return memberships

    def create_applications(
        self,
        projects: list[Project],
        vacancies: list[ProjectVacancy],
        specialists: list[SpecialistProfile],
        memberships: list[ProjectMembership],
    ) -> list[object]:
        """
        Создает связанные данные приложения.
        Args:
            projects: Список проектов
            vacancies: Список открытых ролей
            specialists: Список профилей специалистов
            memberships: Список участников проектов
        """
        applications = []
        membership_pairs = {(m.project_id, m.specialist_id) for m in memberships}
        used_active = set()

        published_projects = [
            project
            for project in projects
            if project.status == Project.Status.PUBLISHED
        ]

        for _ in range(28):
            project = random.choice(published_projects)
            project_vacancies = [
                vacancy
                for vacancy in vacancies
                if vacancy.project_id == project.id
                and vacancy.status == ProjectVacancy.Status.OPEN
            ]

            if not project_vacancies:
                continue

            vacancy = random.choice(project_vacancies)
            candidates = [
                specialist
                for specialist in specialists
                if specialist.user_id != project.owner_id
                and (project.id, specialist.id) not in membership_pairs
            ]

            if not candidates:
                continue

            specialist = random.choice(candidates)
            active_key = (project.id, vacancy.id, specialist.id)

            status = random.choice(
                [
                    Application.Status.PENDING,
                    Application.Status.PENDING,
                    Application.Status.REJECTED,
                    Application.Status.CANCELLED,
                ]
            )

            if status in Application.ACTIVE_STATUSES and active_key in used_active:
                status = Application.Status.REJECTED

            try:
                application = Application.objects.create(
                    project=project,
                    vacancy=vacancy,
                    specialist=specialist,
                    message=(
                        f"Здравствуйте! Хочу присоединиться к проекту. "
                        f"Мой опыт: {fake.sentence(nb_words=12)}"
                    ),
                    status=status,
                    reviewed_at=timezone.now()
                    if status
                    in [Application.Status.REJECTED, Application.Status.CANCELLED]
                    else None,
                    reviewed_by=project.owner
                    if status
                    in [Application.Status.REJECTED, Application.Status.CANCELLED]
                    else None,
                )
            except Exception:
                continue

            if status in Application.ACTIVE_STATUSES:
                used_active.add(active_key)

            applications.append(application)

        return applications

    def create_invitations(
        self,
        projects: list[Project],
        vacancies: list[ProjectVacancy],
        specialists: list[SpecialistProfile],
        owners: list[User],
        memberships: list[ProjectMembership],
    ) -> list[object]:
        """
        Создает связанные данные приложения.
        Args:
            projects: Список проектов
            vacancies: Список открытых ролей
            specialists: Список профилей специалистов
            owners: Список владельцев проектов
            memberships: Список участников проектов
        """
        invitations = []
        membership_pairs = {(m.project_id, m.specialist_id) for m in memberships}
        used_pending = set()

        published_projects = [
            project
            for project in projects
            if project.status == Project.Status.PUBLISHED
        ]

        for _ in range(24):
            project = random.choice(published_projects)
            project_vacancies = [
                vacancy
                for vacancy in vacancies
                if vacancy.project_id == project.id
                and vacancy.status == ProjectVacancy.Status.OPEN
            ]

            if not project_vacancies:
                continue

            vacancy = random.choice(project_vacancies)
            candidates = [
                specialist
                for specialist in specialists
                if specialist.user_id != project.owner_id
                and (project.id, specialist.id) not in membership_pairs
            ]

            if not candidates:
                continue

            specialist = random.choice(candidates)
            pending_key = (project.id, vacancy.id, specialist.id)

            status = random.choice(
                [
                    Invitation.Status.PENDING,
                    Invitation.Status.PENDING,
                    Invitation.Status.DECLINED,
                    Invitation.Status.CANCELLED,
                ]
            )

            if status == Invitation.Status.PENDING and pending_key in used_pending:
                status = Invitation.Status.DECLINED

            try:
                invitation = Invitation.objects.create(
                    project=project,
                    vacancy=vacancy,
                    specialist=specialist,
                    invited_by=project.owner,
                    message=(
                        f"Здравствуйте! Ваш профиль подходит для роли «{vacancy.title}». "
                        f"Будем рады видеть вас в команде."
                    ),
                    status=status,
                    responded_at=timezone.now()
                    if status
                    in [Invitation.Status.DECLINED, Invitation.Status.CANCELLED]
                    else None,
                )
            except Exception:
                continue

            if status == Invitation.Status.PENDING:
                used_pending.add(pending_key)

            invitations.append(invitation)

        return invitations

    def create_favorites(self, projects: list[Project], users: object) -> list[object]:
        """
        Создает связанные данные приложения.
        Args:
            projects: Список проектов
            users: Список пользователей
        """
        favorites = []
        used_pairs = set()

        available_projects = [
            project
            for project in projects
            if project.status in [Project.Status.PUBLISHED, Project.Status.CLOSED]
        ]

        if not available_projects:
            return favorites

        for _ in range(45):
            user = random.choice(users)
            project = random.choice(available_projects)
            key = (user.id, project.id)

            if key in used_pairs:
                continue

            favorite = FavoriteProject.objects.create(
                user=user,
                project=project,
            )

            used_pairs.add(key)
            favorites.append(favorite)

        return favorites

    def create_project_files(
        self,
        projects: list[Project],
    ) -> list[object]:
        """
        Создает связанные данные приложения.
        Args:
            projects: Список проектов
        """
        files = []

        for project in projects:
            for index in range(random.randint(1, 3)):
                content = (
                    f"Файл проекта: {project.title}\n"
                    f"Описание: {fake.text(max_nb_chars=300)}\n"
                    f"Дата генерации: {timezone.now()}\n"
                )

                project_file = ProjectFile.objects.create(
                    project=project,
                    uploaded_by=project.owner,
                    file=ContentFile(
                        content.encode("utf-8"),
                        name=f"project_{project.id}_file_{index + 1}.txt",
                    ),
                    file_type=ProjectFile.FileType.DOCUMENT,
                    title=f"Документ проекта {index + 1}",
                )
                files.append(project_file)

        return files

    def sync_vacancy_counts(self, vacancies: list[ProjectVacancy]) -> None:
        """
        Синхронизирует current_count у ролей проекта после генерации участников.
        Args:
            vacancies: Список ролей проекта
        """
        for vacancy in vacancies:
            vacancy.sync_current_count()

    def generate_image_file(
        self, text: str, filename: str, size: tuple[int, int]
    ) -> ContentFile:
        """
        Генерирует простую PNG-картинку для avatar/cover_image.
        Args:
            text: Текстовое значение
            filename: Имя файла
            size: Размер изображения
        """
        image = Image.new(
            "RGB",
            size,
            (
                random.randint(20, 80),
                random.randint(80, 160),
                random.randint(160, 230),
            ),
        )

        draw = ImageDraw.Draw(image)
        draw.text(
            (size[0] // 2 - 20, size[1] // 2 - 10),
            text,
            fill=(255, 255, 255),
        )

        buffer = BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)

        return ContentFile(buffer.read(), name=filename)
