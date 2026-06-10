"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve as static_serve
from django.views.i18n import set_language
from django.utils.translation import gettext_lazy as _

from config import views
from apps.projects.views import project_file_serve

admin.site.site_header = "New-Makers Admin"
admin.site.site_title = "New-Makers Admin"
admin.site.index_title = _("Админка сервиса по поиску IT-команды")

urlpatterns = [
    re_path(
        r"^media/projects/files/(?P<path>.+)$",
        project_file_serve,
        name="project_file_serve",
    ),
    path("admin/", admin.site.urls),
    path("api/", include("apps.api.urls")),
    path("oauth/", include("allauth.urls")),
    path("search/", views.global_search, name="global_search"),
    path("", include("apps.projects.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("specialists/", include("apps.specialists.urls")),
    path("", include("apps.interactions.urls")),
    path(
        "i18n/setlang/",
        set_language,
        name="set_language",
    ),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [
        path("__debug__/", include(debug_toolbar.urls)),
    ]

    if getattr(settings, "SILK_ENABLED", False):
        urlpatterns += [
            path("silk/", include("silk.urls", namespace="silk")),
        ]

if settings.SERVE_MEDIA:
    urlpatterns += [
        re_path(
            r"^media/(?!projects/files/)(?P<path>.*)$",
            static_serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]
