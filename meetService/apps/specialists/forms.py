from django import forms

from apps.directories.models import Role, Technology
from apps.common_validators import validate_iana_timezone
from apps.specialists.models import SpecialistProfile, SpecialistTechnology


class SpecialistProfileForm(forms.ModelForm):
    """Форма создания и редактирования профиля специалиста."""

    technologies = forms.ModelMultipleChoiceField(
        label="Технологии",
        queryset=Technology.objects.none(),
        required=True,
        help_text="Выбери технологии, с которыми готов участвовать в проектах.",
        widget=forms.CheckboxSelectMultiple(
            attrs={
                "class": "choice-list choice-list--roles",
            }
        ),
        error_messages={
            "required": "Выбери хотя бы одну технологию.",
        },
    )

    preferred_roles = forms.ModelMultipleChoiceField(
        label="Интересующие роли",
        queryset=Role.objects.none(),
        required=False,
        help_text="Можно выбрать несколько ролей, которые тебе интересны в проектах.",
        widget=forms.CheckboxSelectMultiple(
            attrs={
                "class": "choice-list",
            }
        ),
    )

    field_order = [
        "avatar",
        "main_role",
        "level",
        "technologies",
        "preferred_roles",
        "participation_format",
        "status",
        "experience_years",
        "weekly_hours",
        "city",
        "timezone",
        "github_url",
        "gitlab_url",
        "portfolio_url",
        "telegram",
        "bio",
    ]

    class Meta:
        model = SpecialistProfile
        fields = (
            "avatar",
            "main_role",
            "level",
            "technologies",
            "preferred_roles",
            "participation_format",
            "status",
            "experience_years",
            "weekly_hours",
            "city",
            "timezone",
            "github_url",
            "gitlab_url",
            "portfolio_url",
            "telegram",
            "bio",
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
            "participation_format": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),
            "experience_years": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 0,
                    "max": 60,
                }
            ),
            "weekly_hours": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 1,
                    "max": 80,
                }
            ),
            "city": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Москва",
                }
            ),
            "timezone": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Europe/Moscow",
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
            "telegram": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "@username",
                }
            ),
            "bio": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 6,
                    "placeholder": "Расскажи о своём опыте, интересах и проектах.",
                }
            ),
        }

        labels = {
            "avatar": "Аватар",
            "main_role": "Основная роль",
            "level": "Уровень",
            "participation_format": "Формат участия",
            "status": "Доступность",
            "experience_years": "Опыт, лет",
            "weekly_hours": "Готов уделять часов в неделю",
            "city": "Город",
            "timezone": "Часовой пояс",
            "github_url": "GitHub",
            "gitlab_url": "GitLab",
            "portfolio_url": "Портфолио",
            "telegram": "Telegram",
            "bio": "О себе",
        }

        help_texts = {
            "main_role": "Выбери основную роль, по которой тебя будут чаще всего искать.",
            "level": "Укажи текущий профессиональный уровень.",
            "participation_format": "Укажи, какой формат участия в проектах тебе удобен.",
            "status": "Например: ищу проект, открыт к предложениям или занят.",
            "experience_years": "Укажи общий опыт в IT или выбранной роли.",
            "weekly_hours": "Сколько часов в неделю ты готов уделять проектам.",
            "city": "Можно оставить пустым, если город не важен.",
            "timezone": "Например: Europe/Moscow.",
            "telegram": "Контакт для связи, если хочешь его показывать.",
            "bio": "Коротко опиши стек, опыт и тип проектов, которые тебе интересны.",
        }

        error_messages = {
            "main_role": {
                "required": "Выбери основную роль.",
            },
            "bio": {
                "required": "Расскажи немного о себе.",
            },
            "experience_years": {
                "min_value": "Опыт не может быть отрицательным.",
                "max_value": "Проверь значение опыта.",
            },
            "weekly_hours": {
                "min_value": "Количество часов должно быть не меньше 1.",
                "max_value": "Количество часов не может быть больше 80.",
            },
        }

    class Media:
        css = {
            "all": ("css/site.css",),
        }

    @staticmethod
    def _alphabet_sort_key(value: str) -> tuple[int, str]:
        """Сортирует значения: цифры, латиница, кириллица, остальные символы."""
        text = (value or "").strip()
        normalized = text.casefold()

        first_char = ""
        for char in normalized:
            if char.isalnum():
                first_char = char
                break

        if first_char.isdigit():
            group = 0
        elif "a" <= first_char <= "z":
            group = 1
        elif "а" <= first_char <= "я" or first_char == "ё":
            group = 2
        else:
            group = 3

        return group, normalized

    @classmethod
    def _sorted_choices(cls, queryset):
        """Возвращает choices в нужном алфавитном порядке."""
        objects = sorted(
            queryset,
            key=lambda obj: cls._alphabet_sort_key(obj.name),
        )

        return [(obj.pk, obj.name) for obj in objects]

    def __init__(self, *args, **kwargs):
        """Настраивает queryset и начальные значения для связанных полей."""
        super().__init__(*args, **kwargs)

        roles_queryset = Role.objects.filter(is_active=True)
        technologies_queryset = Technology.objects.filter(is_active=True)

        self.fields["main_role"].queryset = roles_queryset
        self.fields["main_role"].choices = self._sorted_choices(roles_queryset)
        self.fields["main_role"].required = True

        self.fields["preferred_roles"].queryset = roles_queryset
        self.fields["preferred_roles"].choices = self._sorted_choices(roles_queryset)

        self.fields["technologies"].queryset = technologies_queryset
        self.fields["technologies"].choices = self._sorted_choices(
            technologies_queryset
        )

        if self.instance and self.instance.pk:
            self.fields["preferred_roles"].initial = self.instance.preferred_roles.all()
            self.fields["technologies"].initial = self.instance.technologies.all()

    def clean_experience_years(self):
        """Проверяет корректность опыта."""
        experience_years = self.cleaned_data.get("experience_years")

        if experience_years is not None and experience_years > 60:
            raise forms.ValidationError("Опыт не может быть больше 60 лет.")

        return experience_years

    def clean_weekly_hours(self):
        """Проверяет количество часов в неделю."""
        weekly_hours = self.cleaned_data.get("weekly_hours")

        if weekly_hours is not None and weekly_hours < 1:
            raise forms.ValidationError("Укажи хотя бы 1 час в неделю.")

        if weekly_hours is not None and weekly_hours > 80:
            raise forms.ValidationError("Количество часов не может быть больше 80.")

        return weekly_hours

    def clean_technologies(self):
        """Проверяет список технологий."""
        technologies = self.cleaned_data.get("technologies")

        if not technologies:
            raise forms.ValidationError("Выбери хотя бы одну технологию.")

        if len(technologies) > 12:
            raise forms.ValidationError("Выбери не больше 12 основных технологий.")

        return technologies

    def clean_bio(self):
        """Очищает описание специалиста."""
        bio = self.cleaned_data.get("bio", "").strip()

        if bio and len(bio) < 20:
            raise forms.ValidationError(
                "Если заполняешь описание, оно должно быть не короче 20 символов."
            )

        return bio

    def clean_telegram(self):
        """Очищает контакт Telegram."""
        telegram = self.cleaned_data.get("telegram", "").strip()

        return telegram

    def clean_city(self):
        """Очищает город."""
        city = self.cleaned_data.get("city", "").strip()

        return city

    def clean_timezone(self):
        """Очищает часовой пояс."""
        timezone = self.cleaned_data.get("timezone", "").strip()
        validate_iana_timezone(timezone)
        return timezone

    def save(self, commit=True):
        """Сохраняет профиль специалиста."""
        profile = super().save(commit=False)

        if profile.bio:
            profile.bio = profile.bio.strip()

        if profile.city:
            profile.city = profile.city.strip()

        if profile.timezone:
            profile.timezone = profile.timezone.strip()

        if profile.telegram:
            profile.telegram = profile.telegram.strip()

        if commit:
            profile.save()
            self._save_m2m()

        return profile

    def _save_m2m(self):
        """Сохраняет интересующие роли и технологии специалиста."""
        if "preferred_roles" in self.cleaned_data:
            self.instance.preferred_roles.set(self.cleaned_data["preferred_roles"])

        if "technologies" in self.cleaned_data:
            selected_technologies = self.cleaned_data["technologies"]

            SpecialistTechnology.objects.filter(
                specialist=self.instance,
            ).exclude(
                technology__in=selected_technologies,
            ).delete()

            for technology in selected_technologies:
                SpecialistTechnology.objects.get_or_create(
                    specialist=self.instance,
                    technology=technology,
                    defaults={
                        "level": SpecialistTechnology.SkillLevel.CONFIDENT,
                    },
                )
