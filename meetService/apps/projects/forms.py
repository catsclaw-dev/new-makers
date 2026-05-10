from django import forms

from apps.directories.models import Role, Technology
from apps.projects.models import Project, ProjectTechnology, ProjectVacancy


class ProjectForm(forms.ModelForm):
    """Форма создания и редактирования проекта."""

    technologies = forms.ModelMultipleChoiceField(
        queryset=Technology.objects.filter(is_active=True).order_by("name"),
        required=False,
        label="Технологии",
        help_text="Выбери технологии, которые используются в проекте.",
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
            "title": "Название проекта",
            "short_description": "Краткое описание",
            "description": "Подробное описание",
            "goal": "Цель проекта",
            "cover_image": "Обложка проекта",
            "stage": "Стадия",
            "participation_format": "Формат участия",
            "repository_url": "Ссылка на репозиторий",
            "demo_url": "Демо-ссылка",
        }
        help_texts = {
            "title": "Короткое и понятное название проекта.",
            "short_description": "Текст для карточки проекта.",
            "description": "Расскажи, что делает проект и кому он полезен.",
            "goal": "Опиши, какого результата должна добиться команда.",
            "cover_image": "Изображение будет показано в карточке и на странице проекта.",
        }
        error_messages = {
            "title": {
                "required": "Укажи название проекта.",
                "max_length": "Название слишком длинное.",
            },
            "short_description": {
                "required": "Добавь краткое описание проекта.",
                "max_length": "Краткое описание слишком длинное.",
            },
            "description": {
                "required": "Добавь подробное описание проекта.",
            },
            "goal": {
                "required": "Укажи цель проекта.",
            },
        }
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Например: сервис подбора IT-команды",
                }
            ),
            "short_description": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Короткое описание для карточки",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                    "placeholder": "Опиши идею, аудиторию и особенности проекта",
                }
            ),
            "goal": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Какой результат должна получить команда?",
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

    def __init__(self, *args, **kwargs):
        """Подставляет выбранные технологии при редактировании проекта."""
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            self.fields["technologies"].initial = self.instance.technologies.all()

    def clean_title(self):
        """Очищает название проекта."""
        return self.cleaned_data["title"].strip()

    def save_technologies(self, project):
        """Сохраняет выбранные технологии через промежуточную модель."""
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
            "role": "Роль",
            "title": "Название открытой роли",
            "description": "Описание роли",
            "required_level": "Требуемый уровень",
            "required_count": "Сколько человек нужно",
        }
        help_texts = {
            "role": "Выбери роль из справочника.",
            "title": "Например: Junior Backend-разработчик.",
            "description": "Опиши задачи, ожидания и стек для участника.",
            "required_count": "Сколько специалистов нужно на эту роль.",
        }
        error_messages = {
            "title": {
                "required": "Укажи название открытой роли.",
            },
            "description": {
                "required": "Добавь описание роли.",
            },
        }
        widgets = {
            "role": forms.Select(attrs={"class": "form-control"}),
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Например: Backend-разработчик",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": "Опиши задачи и требования к участнику",
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

    def __init__(self, *args, **kwargs):
        """Показывает только активные роли."""
        super().__init__(*args, **kwargs)
        self.fields["role"].queryset = Role.objects.filter(is_active=True).order_by(
            "name"
        )

    def clean_title(self):
        """Очищает название роли."""
        return self.cleaned_data["title"].strip()
