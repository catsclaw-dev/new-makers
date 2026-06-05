from __future__ import annotations

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
            "password1",
            "password2",
        )
        labels = {
            "username": "Логин",
            "first_name": "Имя",
            "last_name": "Фамилия",
        }
        help_texts = {
            "username": "Будет отображаться в профиле и карточках.",
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
        }

    class Media:
        css = {
            "all": ("css/site.css",),
        }

    def clean_email(self) -> str:
        """
        Проверяет уникальность email.
        """
        email = self.cleaned_data["email"].strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Пользователь с таким email уже зарегистрирован. "
                "Войдите через обычную форму или через тот OAuth-провайдер, "
                "к которому привязана эта почта."
            )

        return email

    def save(self, commit: bool = True) -> object:
        """
        Сохраняет пользователя как специалиста по умолчанию.
        Args:
            commit: Признак необходимости сохранить объект в базе данных
        """
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"].strip().lower()
        user.role = User.UserRole.SPECIALIST

        if commit:
            user.save()

            SpecialistProfile.objects.get_or_create(
                user=user,
                defaults={
                    "created_by": user,
                    "updated_by": user,
                },
            )

        return user


class AccountEmailForm(forms.ModelForm):
    """Форма обновления email пользователя."""

    email = forms.EmailField(
        label="Email",
        help_text="На эту почту будут приходить уведомления по откликам и приглашениям.",
        error_messages={
            "required": "Email обязателен для уведомлений.",
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
        fields = ("email",)

    def __init__(self, *args: object, **kwargs: object) -> None:
        """
        Инициализирует форму обновления email.
        Args:
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы
        """
        super().__init__(*args, **kwargs)

    def clean_email(self) -> str:
        """
        Проверяет уникальность email среди пользователей.
        """
        email = self.cleaned_data["email"].strip().lower()
        queryset = User.objects.filter(email__iexact=email)

        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise forms.ValidationError(
                "Пользователь с таким email уже зарегистрирован. "
                "Используйте другую почту или войдите в аккаунт, "
                "к которому она уже привязана."
            )

        return email

    def save(self, commit: bool = True) -> object:
        """
        Сохраняет нормализованный email пользователя.
        Args:
            commit: Признак необходимости сохранить объект в базе данных
        """
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"].strip().lower()

        if commit:
            user.save(update_fields=["email"])

        return user
