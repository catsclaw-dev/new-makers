from django.shortcuts import render


from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render

from apps.accounts.forms import RegisterForm


def register(request):
    """Регистрация нового пользователя."""
    if request.user.is_authenticated:
        return redirect("accounts:profile")

    if request.method == "POST":
        form = RegisterForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Регистрация завершена. Профиль создан.")
            return redirect("accounts:profile")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})


class AccountLoginView(LoginView):
    """Страница входа пользователя."""

    template_name = "accounts/login.html"
    redirect_authenticated_user = True


class AccountLogoutView(LogoutView):
    """Выход пользователя."""

    next_page = "projects:home"


@login_required
def profile(request):
    """Простая страница личного кабинета пользователя."""
    specialist_profile = getattr(request.user, "specialist_profile", None)

    context = {
        "specialist_profile": specialist_profile,
    }
    return render(request, "accounts/profile.html", context)
