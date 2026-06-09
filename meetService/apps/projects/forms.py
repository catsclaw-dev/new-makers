from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _

from apps.directories.models import Role, Technology
from apps.projects.models import (
    Project,
    ProjectTechnology,
    ProjectVacancy,
    ProjectMembership,
)


class ProjectForm(forms.ModelForm):
    """Форма создания и редактирования проекта."""

    technologies = forms.ModelMultipleChoiceField(
        queryset=Technology.objects.filter(is_active=True).order_by("name"),
        required=False,
        label=_("Технологии"),
        help_text=_("Выбери технологии, которые используются в проекте."),
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Project
        fields = (
            "title",
            "short_description",
            "description",
            "goal",
            "cover_image",
            "stage",
            "participation_format",
            "technologies",
            "repository_url",
            "demo_url",
        )
        labels = {
            "title": _("Название проекта"),
            "short_description": _("Краткое описание"),
            "description": _("Подробное описание"),
            "goal": _("Цель проекта"),
            "cover_image": _("Обложка проекта"),
            "stage": _("Стадия"),
            "participation_format": _("Формат участия"),
            "repository_url": _("Ссылка на репозиторий"),
            "demo_url": _("Демо-ссылка"),
        }
        help_texts = {
            "title": _("Короткое и понятное название проекта."),
            "short_description": _("Текст для карточки проекта."),
            "description": _("Расскажи, что делает проект и кому он полезен."),
            "goal": _("Опиши, какого результата должна добиться команда."),
            "cover_image": _(
                "Изображение будет показано в карточке и на странице проекта."
            ),
        }
        error_messages = {
            "title": {
                "required": _("Укажи название проекта."),
                "max_length": _("Название слишком длинное."),
            },
            "short_description": {
                "required": _("Добавь краткое описание проекта."),
                "max_length": _("Краткое описание слишком длинное."),
            },
            "description": {
                "required": _("Добавь подробное описание проекта."),
            },
            "goal": {
                "required": _("Укажи цель проекта."),
            },
        }
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Например: сервис подбора IT-команды"),
                }
            ),
            "short_description": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Короткое описание для карточки"),
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                    "placeholder": _("Опиши идею, аудиторию и особенности проекта"),
                }
            ),
            "goal": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": _("Какой результат должна получить команда?"),
                }
            ),
            "cover_image": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                }
            ),
            "stage": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),
            "participation_format": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),
            "repository_url": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "https://github.com/...",
                }
            ),
            "demo_url": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "https://...",
                }
            ),
        }

    class Media:
        css = {
            "all": ("css/site.css",),
        }

    def __init__(self, *args: object, **kwargs: object) -> object:
        """
        Подставляет выбранные технологии при редактировании проекта.
        Args:
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы
        """
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            self.fields["technologies"].initial = self.instance.technologies.all()

    def clean_title(self) -> object:
        """
        Очищает название проекта.
        """
        return self.cleaned_data["title"].strip()

    def save_technologies(self, project: Project) -> object:
        """
        Сохраняет выбранные технологии через промежуточную модель.
        Args:
            project: Объект проекта
        """
        selected_technologies = self.cleaned_data.get("technologies", [])

        ProjectTechnology.objects.filter(project=project).exclude(
            technology__in=selected_technologies
        ).delete()

        for technology in selected_technologies:
            ProjectTechnology.objects.get_or_create(
                project=project,
                technology=technology,
                defaults={
                    "is_required": True,
                },
            )


class ProjectVacancyForm(forms.ModelForm):
    """Форма создания открытой роли проекта."""

    class Meta:
        model = ProjectVacancy
        fields = (
            "role",
            "title",
            "description",
            "required_level",
            "required_count",
        )
        labels = {
            "role": _("Роль"),
            "title": _("Название открытой роли"),
            "description": _("Описание роли"),
            "required_level": _("Требуемый уровень"),
            "required_count": _("Сколько человек нужно"),
        }
        help_texts = {
            "role": _("Выбери роль из справочника."),
            "title": _("Например: Junior Backend-разработчик."),
            "description": _("Опиши задачи, ожидания и стек для участника."),
            "required_count": _("Сколько специалистов нужно на эту роль."),
        }
        error_messages = {
            "title": {
                "required": _("Укажи название открытой роли."),
            },
            "description": {
                "required": _("Добавь описание роли."),
            },
        }
        widgets = {
            "role": forms.Select(attrs={"class": "form-control"}),
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Например: Backend-разработчик"),
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": _("Опиши задачи и требования к участнику"),
                }
            ),
            "required_level": forms.Select(attrs={"class": "form-control"}),
            "required_count": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 1,
                    "max": 20,
                }
            ),
        }

    class Media:
        css = {
            "all": ("css/site.css",),
        }

    def __init__(self, *args: object, **kwargs: object) -> object:
        """
        Показывает только активные роли.
        Args:
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы
        """
        super().__init__(*args, **kwargs)
        self.fields["role"].queryset = Role.objects.filter(is_active=True).order_by(
            "name"
        )

    def clean_title(self) -> object:
        """
        Очищает название роли.
        """
        return self.cleaned_data["title"].strip()


class ProjectVacancyUpdateForm(forms.ModelForm):
    """Форма редактирования открытой роли проекта."""

    class Meta:
        model = ProjectVacancy
        fields = (
            "role",
            "title",
            "description",
            "required_level",
            "required_count",
            "status",
        )

        labels = {
            "role": _("Роль"),
            "title": _("Название открытой роли"),
            "description": _("Описание роли"),
            "required_level": _("Требуемый уровень"),
            "required_count": _("Сколько человек нужно"),
            "status": _("Статус роли"),
        }

        help_texts = {
            "role": _("Выбери роль из справочника."),
            "title": _("Например: Junior Backend-разработчик."),
            "description": _("Опиши задачи, ожидания и стек для участника."),
            "required_count": _(
                "Количество мест не может быть меньше уже набранных участников."
            ),
            "status": _(
                "Открытая роль доступна для откликов. Роль на паузе или закрытая недоступна для новых откликов."
            ),
        }

        error_messages = {
            "title": {
                "required": _("Укажи название открытой роли."),
            },
            "description": {
                "required": _("Добавь описание роли."),
            },
        }

        widgets = {
            "role": forms.Select(attrs={"class": "form-control"}),
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Например: Backend-разработчик"),
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": _("Опиши задачи и требования к участнику"),
                }
            ),
            "required_level": forms.Select(attrs={"class": "form-control"}),
            "required_count": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 1,
                    "max": 20,
                }
            ),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    class Media:
        css = {
            "all": ("css/site.css",),
        }

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Показывает только активные роли."""
        super().__init__(*args, **kwargs)

        self.fields["role"].queryset = Role.objects.filter(is_active=True).order_by(
            "name"
        )

    def clean_title(self) -> str:
        """Очищает название роли."""
        return self.cleaned_data["title"].strip()

    def clean(self) -> dict[str, object]:
        """Проверяет бизнес-правила редактирования роли."""
        cleaned_data = super().clean()

        required_count = cleaned_data.get("required_count")
        status = cleaned_data.get("status")

        if self.instance and self.instance.pk and required_count is not None:
            if required_count < self.instance.current_count:
                raise forms.ValidationError(
                    _(
                        "Количество мест не может быть меньше уже набранных участников: %(count)s."
                    )
                    % {"count": self.instance.current_count}
                )

            if (
                required_count == self.instance.current_count
                and status == ProjectVacancy.Status.OPEN
            ):
                raise forms.ValidationError(
                    _(
                        "Роль уже заполнена. Увеличь количество мест или выбери статус «Закрыта»."
                    )
                )

        return cleaned_data


class ProjectMembershipUpdateForm(forms.ModelForm):
    """Форма редактирования участника команды проекта."""

    class Meta:
        model = ProjectMembership
        fields = (
            "vacancy",
            "status",
        )

        labels = {
            "vacancy": _("Роль проекта"),
            "status": _("Статус участия"),
        }

        help_texts = {
            "vacancy": _(
                "Выбери конкретную открытую роль проекта, которую занимает участник."
            ),
            "status": _(
                "Активный участник и участник на паузе занимают место в роли. Статус «покинул проект» освобождает место."
            ),
        }

        widgets = {
            "vacancy": forms.Select(attrs={"class": "form-control"}),
            "status": forms.Select(attrs={"class": "form-control"}),
        }

    class Media:
        css = {
            "all": ("css/site.css",),
        }

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)

        project = self.instance.project

        vacancies = (
            ProjectVacancy.objects.select_related("role")
            .filter(project=project)
            .order_by("role__name", "title")
        )

        self.fields["vacancy"].queryset = vacancies

        def vacancy_label(vacancy: ProjectVacancy) -> str:
            return (
                f"{vacancy.title} — {vacancy.role.name} — "
                f"{vacancy.get_required_level_display()} — "
                f"мест: {vacancy.current_count}/{vacancy.required_count} — "
                f"{vacancy.get_status_display()}"
            )

        self.fields["vacancy"].label_from_instance = vacancy_label

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()

        if self.instance.status == ProjectMembership.Status.LEFT:
            raise forms.ValidationError(
                _(
                    "Участник уже покинул проект. Эту историческую запись нельзя редактировать."
                )
            )

        vacancy = cleaned_data.get("vacancy")
        status = cleaned_data.get("status")

        if vacancy is None or status is None:
            return cleaned_data

        project = self.instance.project

        if vacancy.project_id != project.id:
            raise forms.ValidationError(
                _("Выбранная роль не относится к этому проекту.")
            )

        active_statuses = [
            ProjectMembership.Status.ACTIVE,
            ProjectMembership.Status.PAUSED,
        ]

        will_occupy_place = status in active_statuses
        currently_occupies_place = self.instance.status in active_statuses
        same_vacancy = self.instance.vacancy_id == vacancy.id

        if status == ProjectMembership.Status.LEFT and not same_vacancy:
            raise forms.ValidationError(
                _("При выходе участника из проекта оставь его текущую роль проекта.")
            )

        if will_occupy_place:
            needs_free_slot = not same_vacancy or not currently_occupies_place

            if needs_free_slot:
                if vacancy.status != ProjectVacancy.Status.OPEN:
                    raise forms.ValidationError(
                        _("Перевести участника можно только на открытую роль проекта.")
                    )

                if vacancy.remaining_slots() <= 0:
                    raise forms.ValidationError(
                        _("В выбранной роли проекта нет свободных мест.")
                    )

        return cleaned_data
