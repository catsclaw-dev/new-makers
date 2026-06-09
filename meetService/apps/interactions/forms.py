from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.interactions.emails import (
    enqueue_application_created_email,
    enqueue_invitation_created_email,
)
from apps.interactions.models import Application, Invitation
from apps.projects.models import Project, ProjectVacancy
from apps.specialists.models import SpecialistProfile


class ApplicationForm(forms.ModelForm):
    """Форма отклика специалиста на открытую роль проекта."""

    message = forms.CharField(
        label=_("Комментарий к отклику"),
        required=True,
        max_length=1000,
        help_text=_("Кратко расскажи, почему ты подходишь команде. До 1000 символов."),
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 5,
                "maxlength": 1000,
                "placeholder": _(
                    "Напиши, почему хочешь присоединиться к проекту и чем можешь быть полезен."
                ),
            }
        ),
        error_messages={
            "required": _("Добавь комментарий к отклику."),
            "max_length": _(
                "Комментарий к отклику не должен быть длиннее 1000 символов."
            ),
        },
    )

    class Meta:
        model = Application
        fields = ("vacancy", "message")
        labels = {
            "vacancy": _("Открытая роль"),
        }
        help_texts = {
            "vacancy": _("Выбери роль, на которую хочешь откликнуться."),
        }
        error_messages = {
            "vacancy": {
                "required": _("Выбери открытую роль проекта."),
            },
        }
        widgets = {
            "vacancy": forms.Select(attrs={"class": "form-control"}),
        }

    class Media:
        css = {
            "all": ("css/site.css",),
        }

    def __init__(
        self,
        *args: object,
        project: Project | None = None,
        specialist: SpecialistProfile | None = None,
        **kwargs: object,
    ) -> object:
        """
        Ограничивает выбор ролей только открытыми ролями конкретного проекта.
        Args:
            project: Объект проекта
            specialist: Профиль специалиста
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы
        """
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

    def clean_vacancy(self) -> object:
        """
        Проверяет, что выбранная роль относится к проекту и ещё открыта.
        """
        vacancy = self.cleaned_data["vacancy"]

        if self.project and vacancy.project_id != self.project.pk:
            raise ValidationError(_("Выбранная роль не относится к этому проекту."))

        if not vacancy.is_open():
            raise ValidationError(_("Эта роль уже закрыта или заполнена."))

        return vacancy

    def _post_clean(self) -> None:
        """
        Подставляет связанные объекты до модельной валидации.
        """
        if self.project is not None:
            self.instance.project = self.project

        if self.specialist is not None:
            self.instance.specialist = self.specialist

        super()._post_clean()

    def save(self, commit: bool = True) -> object:
        """
        Создаёт отклик и подставляет проект со специалистом.
        Args:
            commit: Признак необходимости сохранить объект в базе данных
        """
        application = super().save(commit=False)
        application.project = self.project
        application.specialist = self.specialist

        if commit:
            application.save()
            enqueue_application_created_email(application.pk)

        return application


class InvitationForm(forms.ModelForm):
    """Форма приглашения специалиста в проект."""

    class Meta:
        model = Invitation
        exclude = {
            "project",
            "specialist",
            "invited_by",
            "status",
            "invited_at",
            "responded_at",
        }
        labels = {
            "vacancy": _("Проект и открытая роль"),
            "message": _("Текст приглашения"),
        }
        help_texts = {
            "vacancy": _(
                "Выбери открытую роль в одном из своих опубликованных проектов."
            ),
            "message": _(
                "Кратко объясни, почему хочешь пригласить этого специалиста. До 1000 символов"
            ),
        }
        error_messages = {
            "vacancy": {
                "required": _("Выбери открытую роль для приглашения."),
            },
        }
        widgets = {
            "vacancy": forms.Select(attrs={"class": "form-control"}),
            "message": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "maxlength": 1000,
                    "placeholder": _("Здравствуйте! Хочу пригласить вас в проект..."),
                }
            ),
        }

    class Media:
        css = {
            "all": ("css/site.css",),
        }

    def __init__(
        self,
        *args: object,
        specialist: SpecialistProfile | None = None,
        invited_by: User | None = None,
        **kwargs: object,
    ) -> object:
        """
        Показывает только открытые роли проектов текущего владельца.
        Args:
            specialist: Профиль специалиста
            invited_by: Значение параметра `invited_by`
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы
        """
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

    def clean_vacancy(self) -> object:
        """
        Проверяет, что владелец приглашает только в свой опубликованный проект.
        """
        vacancy = self.cleaned_data["vacancy"]

        if vacancy.project.owner_id != self.invited_by.id:
            raise ValidationError(_("Можно приглашать только в свои проекты."))

        if not vacancy.is_open():
            raise ValidationError(_("Эта роль уже закрыта или заполнена."))

        return vacancy

    def _post_clean(self) -> None:
        """
        Подставляет связанные объекты до модельной валидации.
        """
        vacancy = self.cleaned_data.get("vacancy")

        if vacancy is not None:
            self.instance.vacancy = vacancy
            self.instance.project = vacancy.project

        if self.specialist is not None:
            self.instance.specialist = self.specialist

        if self.invited_by is not None:
            self.instance.invited_by = self.invited_by

        super()._post_clean()

    def save(self, commit: bool = True) -> object:
        """
        Создаёт приглашение и подставляет проект, специалиста и автора.
        Args:
            commit: Признак необходимости сохранить объект в базе данных
        """
        invitation = super().save(commit=False)
        invitation.project = invitation.vacancy.project
        invitation.specialist = self.specialist
        invitation.invited_by = self.invited_by

        if commit:
            invitation.save()
            enqueue_invitation_created_email(invitation.pk)

        return invitation
