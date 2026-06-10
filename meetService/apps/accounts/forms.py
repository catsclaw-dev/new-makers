from __future__ import annotations

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.utils.translation import gettext_lazy as _

from allauth.account.models import EmailAddress

from apps.accounts.models import User
from apps.specialists.models import SpecialistProfile


class VerifiedEmailAuthenticationForm(AuthenticationForm):
    """Форма входа с проверкой подтверждения email."""

    error_messages = {
        **AuthenticationForm.error_messages,
        "email_not_verified": _(
            "Подтверди email перед входом. Проверь письмо со ссылкой подтверждения."
        ),
        "email_required": _(
            "У аккаунта не указан email. Обратись к администратору или обнови профиль."
        ),
    }

    def confirm_login_allowed(self, user: User) -> None:
        """
        Проверяет, может ли пользователь войти.
        Args:
            user: Пользователь, который пытается войти
        """
        super().confirm_login_allowed(user)

        if user.is_staff or user.is_superuser:
            return

        if not user.email:
            raise forms.ValidationError(
                self.error_messages["email_required"],
                code="email_required",
            )

        email_is_verified = EmailAddress.objects.filter(
            user=user,
            email__iexact=user.email,
            verified=True,
        ).exists()

        if not email_is_verified:
            raise forms.ValidationError(
                self.error_messages["email_not_verified"],
                code="email_not_verified",
            )


class RegisterForm(UserCreationForm):
    """Форма регистрации пользователя."""

    email = forms.EmailField(
        label="Email",
        help_text=_("Укажи почту для входа и уведомлений."),
        error_messages={
            "required": _("Email обязателен для регистрации."),
            "invalid": _("Введите корректный email."),
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
            "username": _("Логин"),
            "first_name": _("Имя"),
            "last_name": _("Фамилия"),
        }
        help_texts = {
            "username": _("Будет отображаться в профиле и карточках."),
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
                    "placeholder": _("Иван"),
                    "class": "form-control",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "placeholder": _("Петров"),
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
                _(
                    "Пользователь с таким email уже зарегистрирован. "
                    "Войдите через обычную форму или через тот OAuth-провайдер, "
                    "к которому привязана эта почта."
                )
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
        help_text=_(
            "На эту почту будут приходить уведомления по откликам и приглашениям."
        ),
        error_messages={
            "required": _("Email обязателен для уведомлений."),
            "invalid": _("Введите корректный email."),
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
                _(
                    "Пользователь с таким email уже зарегистрирован. "
                    "Используйте другую почту или войдите в аккаунт, "
                    "к которому она уже привязана."
                )
            )

        email_address_queryset = EmailAddress.objects.filter(email__iexact=email)

        if self.instance.pk:
            email_address_queryset = email_address_queryset.exclude(user=self.instance)

        if email_address_queryset.exists():
            raise forms.ValidationError(
                _(
                    "Этот email уже привязан к другому аккаунту. "
                    "Используйте другую почту."
                )
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
