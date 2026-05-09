from django import forms
from django.core.exceptions import ValidationError
from django.db import models

from apps.interactions.models import Application, Invitation
from apps.projects.models import Project, ProjectVacancy


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

    def _post_clean(self):
        """Подставляет связанные объекты до модельной валидации."""
        if self.project is not None:
            self.instance.project = self.project

        if self.specialist is not None:
            self.instance.specialist = self.specialist

        super()._post_clean()

    def save(self, commit=True):
        """Создаёт отклик и подставляет проект со специалистом."""
        application = super().save(commit=False)
        application.project = self.project
        application.specialist = self.specialist

        if commit:
            application.save()

        return application


class InvitationForm(forms.ModelForm):
    """Форма приглашения специалиста в проект."""

    class Meta:
        model = Invitation
        fields = ("vacancy", "message")
        labels = {
            "vacancy": "Проект и открытая роль",
            "message": "Сообщение специалисту",
        }
        help_texts = {
            "vacancy": "Выбери открытую роль в одном из своих опубликованных проектов.",
            "message": "Кратко объясни, почему хочешь пригласить этого специалиста.",
        }
        error_messages = {
            "vacancy": {
                "required": "Выбери открытую роль для приглашения.",
            },
        }
        widgets = {
            "vacancy": forms.Select(attrs={"class": "form-control"}),
            "message": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": "Здравствуйте! Хочу пригласить вас в проект...",
                }
            ),
        }

    class Media:
        css = {
            "all": ("css/site.css",),
        }

    def __init__(self, *args, specialist=None, invited_by=None, **kwargs):
        """Показывает только открытые роли проектов текущего владельца."""
        super().__init__(*args, **kwargs)

        self.specialist = specialist
        self.invited_by = invited_by

        if invited_by is not None:
            self.fields["vacancy"].queryset = (
                ProjectVacancy.objects.select_related("project", "role")
                .filter(
                    project__owner=invited_by,
                    project__status=Project.Status.PUBLISHED,
                    status=ProjectVacancy.Status.OPEN,
                    current_count__lt=models.F("required_count"),
                )
                .order_by("project__title", "role__name", "title")
            )
        else:
            self.fields["vacancy"].queryset = ProjectVacancy.objects.none()

    def clean_vacancy(self):
        """Проверяет, что владелец приглашает только в свой опубликованный проект."""
        vacancy = self.cleaned_data["vacancy"]

        if vacancy.project.owner_id != self.invited_by.id:
            raise ValidationError("Можно приглашать только в свои проекты.")

        if not vacancy.is_open():
            raise ValidationError("Эта роль уже закрыта или заполнена.")

        return vacancy

    def _post_clean(self):
        """Подставляет связанные объекты до модельной валидации."""
        vacancy = self.cleaned_data.get("vacancy")

        if vacancy is not None:
            self.instance.vacancy = vacancy
            self.instance.project = vacancy.project

        if self.specialist is not None:
            self.instance.specialist = self.specialist

        if self.invited_by is not None:
            self.instance.invited_by = self.invited_by

        super()._post_clean()

    def save(self, commit=True):
        """Создаёт приглашение и подставляет проект, специалиста и автора."""
        invitation = super().save(commit=False)
        invitation.project = invitation.vacancy.project
        invitation.specialist = self.specialist
        invitation.invited_by = self.invited_by

        if commit:
            invitation.save()

        return invitation
