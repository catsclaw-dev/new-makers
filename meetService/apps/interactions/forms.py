from django import forms
from django.core.exceptions import ValidationError
from django.db import models

from apps.interactions.models import Application
from apps.projects.models import ProjectVacancy


class ApplicationForm(forms.ModelForm):
    """Форма отклика специалиста на открытую роль проекта."""

    class Meta:
        model = Application
        fields = ("vacancy", "message")
        labels = {
            "vacancy": "Открытая роль",
            "message": "Сопроводительное сообщение",
        }
        help_texts = {
            "vacancy": "Выбери роль, на которую хочешь откликнуться.",
            "message": "Кратко расскажи, почему ты подходишь команде.",
        }
        error_messages = {
            "vacancy": {
                "required": "Выбери открытую роль проекта.",
            },
        }
        widgets = {
            "vacancy": forms.Select(attrs={"class": "form-control"}),
            "message": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": "Здравствуйте! Хочу присоединиться к проекту, потому что...",
                }
            ),
        }

    class Media:
        css = {
            "all": ("css/site.css",),
        }

    def __init__(self, *args, project=None, specialist=None, **kwargs):
        """Ограничивает выбор ролей только открытыми ролями конкретного проекта."""
        super().__init__(*args, **kwargs)

        self.project = project
        self.specialist = specialist

        if project is not None:
            self.fields["vacancy"].queryset = project.vacancies.filter(
                status=ProjectVacancy.Status.OPEN,
                current_count__lt=models.F("required_count"),
            ).select_related("role")
        else:
            self.fields["vacancy"].queryset = ProjectVacancy.objects.none()

    def clean_vacancy(self):
        """Проверяет, что выбранная роль относится к проекту и ещё открыта."""
        vacancy = self.cleaned_data["vacancy"]

        if self.project and vacancy.project_id != self.project.pk:
            raise ValidationError("Выбранная роль не относится к этому проекту.")

        if not vacancy.is_open():
            raise ValidationError("Эта роль уже закрыта или заполнена.")

        return vacancy

    def save(self, commit=True):
        """Создаёт отклик и подставляет проект со специалистом."""
        application = super().save(commit=False)
        application.project = self.project
        application.specialist = self.specialist

        if commit:
            application.save()

        return application
