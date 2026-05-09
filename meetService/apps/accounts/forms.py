"""Формы приложения accounts."""

from django import forms
from django.contrib.auth.forms import UserCreationForm

from apps.accounts.models import User
from apps.specialists.models import SpecialistProfile


class RegisterForm(UserCreationForm):
    """Форма регистрации пользователя."""

    email = forms.EmailField(
        label="Email",
        help_text="Укажи почту для входа и уведомлений.",
        error_messages={
            "required": "Email обязателен для регистрации.",
            "invalid": "Введите корректный email.",
        },
        widget=forms.EmailInput(
            attrs={
                "placeholder": "you@example.com",
                "class": "form-control",
            }
        ),
    )

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "password1",
            "password2",
        )
        labels = {
            "username": "Логин",
            "first_name": "Имя",
            "last_name": "Фамилия",
            "role": "Роль на сервисе",
        }
        help_texts = {
            "username": "Будет отображаться в профиле и карточках.",
            "role": "Выбери основной сценарий работы на сайте.",
        }
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "placeholder": "frontend_dev",
                    "class": "form-control",
                }
            ),
            "first_name": forms.TextInput(
                attrs={
                    "placeholder": "Иван",
                    "class": "form-control",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "placeholder": "Петров",
                    "class": "form-control",
                }
            ),
            "role": forms.Select(
                attrs={
                    "class": "form-control",
                }
            ),
        }

    class Media:
        css = {
            "all": ("css/site.css",),
        }

    def clean_email(self):
        """Проверяет уникальность email."""
        email = self.cleaned_data["email"].strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Пользователь с таким email уже зарегистрирован."
            )

        return email

    def save(self, commit=True):
        """Сохраняет пользователя и при необходимости создаёт профиль специалиста."""
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"].strip().lower()
        user.role = self.cleaned_data["role"]

        if commit:
            user.save()

            if user.role == User.UserRole.SPECIALIST:
                SpecialistProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        "created_by": user,
                        "updated_by": user,
                    },
                )

        return user
