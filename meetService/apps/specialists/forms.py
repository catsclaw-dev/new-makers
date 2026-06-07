from __future__ import annotations

from django import forms
from django.utils.translation import gettext_lazy as _

from apps.specialists.models import SpecialistProfile


class SpecialistProfileForm(forms.ModelForm):
    """Форма создания и редактирования профиля специалиста."""

    field_order = [
        "avatar",
        "main_role",
        "level",
        "status",
        "bio",
        "experience_years",
        "github_url",
        "gitlab_url",
        "portfolio_url",
    ]

    class Meta:
        model = SpecialistProfile

        exclude = (
            "user",
            "preferred_roles",
            "technologies",
            "participation_format",
            "weekly_hours",
            "city",
            "timezone",
            "telegram",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        )

        widgets = {
            "avatar": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                }
            ),
            "main_role": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),
            "level": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),
            "bio": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                    "placeholder": _("Расскажи о своём опыте, интересах и проектах."),
                }
            ),
            "experience_years": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 0,
                    "max": 60,
                }
            ),
            "github_url": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "https://github.com/username",
                }
            ),
            "gitlab_url": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "https://gitlab.com/username",
                }
            ),
            "portfolio_url": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "https://example.com",
                }
            ),
        }

        labels = {
            "avatar": _("Аватар"),
            "main_role": _("Основная роль"),
            "level": _("Уровень"),
            "status": _("Статус поиска"),
            "bio": _("О себе"),
            "experience_years": _("Опыт, лет"),
            "github_url": "GitHub",
            "gitlab_url": "GitLab",
            "portfolio_url": _("Портфолио"),
        }

        help_texts = {
            "main_role": _("Выбери роль, по которой тебя будут чаще всего искать."),
            "status": _("Например: ищу проект, открыт к предложениям или занят."),
            "bio": _("Коротко опиши стек, опыт и тип проектов, которые тебе интересны."),
        }

        error_messages = {
            "bio": {
                "required": _("Расскажи немного о себе."),
            },
            "experience_years": {
                "min_value": _("Опыт не может быть отрицательным."),
                "max_value": _("Проверь значение опыта."),
            },
        }

    class Media:
        css = {
            "all": ("css/site.css",),
        }

    def clean_experience_years(self) -> object:
        """
        Проверяет корректность опыта.
        """
        experience_years = self.cleaned_data.get("experience_years")

        if experience_years is not None and experience_years > 60:
            raise forms.ValidationError(_("Опыт не может быть больше 60 лет."))

        return experience_years

    def clean_bio(self) -> object:
        """
        Очищает описание специалиста.
        """
        bio = self.cleaned_data.get("bio", "").strip()

        if bio and len(bio) < 20:
            raise forms.ValidationError(
                _("Если заполняешь описание, оно должно быть не короче 20 символов.")
            )

        return bio

    def save(self, commit: bool = True) -> object:
        """
        Сохраняет профиль специалиста через commit=False.
        Args:
            commit: Признак необходимости сохранить объект в базе данных
        """
        profile = super().save(commit=False)

        if profile.bio:
            profile.bio = profile.bio.strip()

        if commit:
            profile.save()
            self.save_m2m()

        return profile
