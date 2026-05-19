import io
import textwrap
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from django.http import HttpResponse
from django.utils import timezone
from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from import_export.admin import ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    Project,
    ProjectFile,
    ProjectMembership,
    ProjectTechnology,
    ProjectVacancy,
)
from .resources import ProjectResource

PDF_FONT_NAME = "Helvetica"


def register_pdf_font() -> str:
    """Регистрирует шрифт с поддержкой кириллицы для PDF."""
    font_candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    ]

    for font_path in font_candidates:
        if font_path.exists():
            pdfmetrics.registerFont(TTFont("ProjectPDFUnicode", str(font_path)))
            return "ProjectPDFUnicode"

    return PDF_FONT_NAME


def draw_wrapped_text(
    pdf: canvas.Canvas,
    text: str,
    x: int,
    y: int,
    *,
    width: int = 95,
    line_height: int = 14,
) -> int:
    """Рисует длинный текст несколькими строками и возвращает новую координату Y."""
    text = str(text or "-")
    for line in textwrap.wrap(text, width=width):
        pdf.drawString(x, y, line)
        y -= line_height
    return y


class ProjectTechnologyInline(admin.TabularInline):
    """Inline для технологий проекта."""

    model = ProjectTechnology
    extra = 1
    raw_id_fields = ("technology",)
    fields = (
        "technology",
        "is_required",
        "created_at",
    )
    readonly_fields = ("created_at",)


class ProjectVacancyInline(admin.TabularInline):
    """Inline для открытых ролей проекта."""

    model = ProjectVacancy
    extra = 1
    raw_id_fields = ("role",)
    fields = (
        "role",
        "title",
        "required_level",
        "required_count",
        "current_count",
        "status",
        "created_at",
        "updated_at",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )


class ProjectMembershipInline(admin.TabularInline):
    """Inline для участников команды проекта."""

    model = ProjectMembership
    extra = 0
    raw_id_fields = (
        "specialist",
        "role",
        "added_by",
    )
    fields = (
        "specialist",
        "role",
        "status",
        "joined_at",
        "left_at",
        "added_by",
    )
    readonly_fields = ("joined_at",)


class ProjectFileInline(admin.TabularInline):
    """Inline для файлов проекта."""

    model = ProjectFile
    extra = 0
    raw_id_fields = ("uploaded_by",)
    fields = (
        "title",
        "file",
        "file_type",
        "uploaded_by",
        "uploaded_at",
    )
    readonly_fields = ("uploaded_at",)


@admin.register(Project)
class ProjectAdmin(ImportExportModelAdmin, SimpleHistoryAdmin):
    """Админ-панель проектов."""

    actions = ("export_projects_to_pdf",)

    resource_classes = [ProjectResource]

    list_display = (
        "title",
        "owner",
        "stage",
        "participation_format",
        "status",
        "display_open_vacancies_count",
        "display_members_count",
        "display_technologies_count",
        "created_at",
        "updated_at",
    )
    list_display_links = (
        "title",
        "owner",
    )
    list_filter = (
        "stage",
        "participation_format",
        "status",
        "technologies",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "title",
        "slug",
        "short_description",
        "description",
        "goal",
        "owner__username",
        "owner__email",
    )
    raw_id_fields = (
        "owner",
        "created_by",
        "updated_by",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "display_cover_preview",
        "display_open_vacancies_count",
        "display_members_count",
        "display_technologies_count",
    )
    date_hierarchy = "created_at"
    prepopulated_fields = {
        "slug": ("title",),
    }
    inlines = (
        ProjectTechnologyInline,
        ProjectVacancyInline,
        ProjectMembershipInline,
        ProjectFileInline,
    )

    fieldsets = (
        (
            _("Владелец и статус"),
            {
                "fields": (
                    "owner",
                    "status",
                    "stage",
                    "participation_format",
                ),
            },
        ),
        (
            _("Описание проекта"),
            {
                "fields": (
                    "title",
                    "slug",
                    "short_description",
                    "description",
                    "goal",
                ),
            },
        ),
        (
            _("Медиа и ссылки"),
            {
                "fields": (
                    "cover_image",
                    "display_cover_preview",
                    "repository_url",
                    "demo_url",
                ),
            },
        ),
        (
            _("Статистика"),
            {
                "fields": (
                    "display_open_vacancies_count",
                    "display_members_count",
                    "display_technologies_count",
                ),
            },
        ),
        (
            _("Служебная информация"),
            {
                "fields": (
                    "created_at",
                    "updated_at",
                    "created_by",
                    "updated_by",
                ),
            },
        ),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return (
            queryset.select_related(
                "owner",
                "created_by",
                "updated_by",
            )
            .prefetch_related(
                "technologies",
                "members",
            )
            .annotate(
                vacancies_count=Count("vacancies", distinct=True),
                members_count=Count("memberships", distinct=True),
                technologies_count=Count("technologies", distinct=True),
            )
        )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="Открытых ролей")
    def display_open_vacancies_count(self, obj: Project) -> int:
        return obj.vacancies.filter(status=ProjectVacancy.Status.OPEN).count()

    @admin.display(description="Участников")
    def display_members_count(self, obj: Project) -> int:
        return getattr(obj, "members_count", obj.memberships.count())

    @admin.display(description="Технологий")
    def display_technologies_count(self, obj: Project) -> int:
        return getattr(obj, "technologies_count", obj.technologies.count())

    @admin.display(description="Предпросмотр обложки")
    def display_cover_preview(self, obj: Project) -> str:
        if obj and obj.cover_image:
            return format_html(
                '<img src="{}" style="max-height: 140px; border-radius: 8px;" />',
                obj.cover_image.url,
            )
        return "Обложка не загружена"

    @admin.action(description="Сформировать PDF по выбранным проектам")
    def export_projects_to_pdf(self, request, queryset):
        """Генерирует PDF-отчёт по выбранным проектам из админки."""
        font_name = register_pdf_font()

        queryset = (
            queryset.select_related("owner")
            .prefetch_related(
                "technologies",
                "vacancies__role",
                "files",
            )
            .order_by("title")
        )

        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        page_width, page_height = A4

        x = 40
        y = int(page_height) - 50
        line_height = 16

        def new_page() -> None:
            nonlocal y
            pdf.showPage()
            pdf.setFont(font_name, 11)
            y = int(page_height) - 50

        def ensure_space(required_height: int = 80) -> None:
            if y < required_height:
                new_page()

        pdf.setTitle("Отчёт по проектам")
        pdf.setFont(font_name, 16)
        pdf.drawString(x, y, "Отчёт по выбранным проектам")
        y -= 24

        pdf.setFont(font_name, 10)
        pdf.drawString(
            x,
            y,
            f"Дата формирования: {timezone.localtime().strftime('%d.%m.%Y %H:%M')}",
        )
        y -= 28

        for number, project in enumerate(queryset, start=1):
            ensure_space(120)

            pdf.setFont(font_name, 13)
            y = draw_wrapped_text(
                pdf,
                f"{number}. {project.title}",
                x,
                y,
                width=85,
                line_height=18,
            )

            pdf.setFont(font_name, 10)

            fields = [
                ("Владелец", project.owner),
                ("Статус", project.get_status_display()),
                ("Стадия", project.get_stage_display()),
                ("Формат участия", project.get_participation_format_display()),
                ("Краткое описание", project.short_description),
                ("Цель", project.goal),
                ("Репозиторий", project.repository_url or "-"),
                ("Демо", project.demo_url or "-"),
            ]

            for label, value in fields:
                ensure_space(70)
                y = draw_wrapped_text(
                    pdf,
                    f"{label}: {value}",
                    x + 12,
                    y,
                    width=100,
                    line_height=line_height,
                )

            technologies = ", ".join(
                technology.name for technology in project.technologies.all()
            )
            ensure_space(70)
            y = draw_wrapped_text(
                pdf,
                f"Технологии: {technologies or '-'}",
                x + 12,
                y,
                width=100,
                line_height=line_height,
            )

            vacancies = project.vacancies.all()
            ensure_space(70)
            pdf.drawString(x + 12, y, "Открытые роли:")
            y -= line_height

            if vacancies:
                for vacancy in vacancies:
                    ensure_space(70)
                    vacancy_text = (
                        f"- {vacancy.title}; роль: {vacancy.role}; "
                        f"уровень: {vacancy.get_required_level_display()}; "
                        f"статус: {vacancy.get_status_display()}; "
                        f"набрано: {vacancy.current_count}/{vacancy.required_count}"
                    )
                    y = draw_wrapped_text(
                        pdf,
                        vacancy_text,
                        x + 24,
                        y,
                        width=95,
                        line_height=line_height,
                    )
            else:
                pdf.drawString(x + 24, y, "- Нет открытых ролей")
                y -= line_height

            files = project.files.all()
            ensure_space(70)
            pdf.drawString(x + 12, y, "Файлы проекта:")
            y -= line_height

            if files:
                for project_file in files:
                    ensure_space(70)
                    file_text = (
                        f"- {project_file.title}; "
                        f"тип: {project_file.get_file_type_display()}; "
                        f"путь: {project_file.file.name}"
                    )
                    y = draw_wrapped_text(
                        pdf,
                        file_text,
                        x + 24,
                        y,
                        width=95,
                        line_height=line_height,
                    )
            else:
                pdf.drawString(x + 24, y, "- Нет прикреплённых файлов")
                y -= line_height

            y -= 12
            ensure_space(70)

        pdf.save()
        buffer.seek(0)

        response = HttpResponse(buffer, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="projects_report.pdf"'
        return response


@admin.register(ProjectTechnology)
class ProjectTechnologyAdmin(ImportExportModelAdmin):
    """Админ-панель технологий проектов."""

    list_display = (
        "project",
        "technology",
        "is_required",
        "created_at",
    )
    list_display_links = (
        "project",
        "technology",
    )
    list_filter = (
        "is_required",
        "technology__category",
        "created_at",
    )
    search_fields = (
        "project__title",
        "technology__name",
    )
    raw_id_fields = (
        "project",
        "technology",
    )
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"


@admin.register(ProjectVacancy)
class ProjectVacancyAdmin(ImportExportModelAdmin, SimpleHistoryAdmin):
    """Админ-панель открытых ролей проектов."""

    list_display = (
        "title",
        "project",
        "role",
        "required_level",
        "required_count",
        "current_count",
        "display_remaining_slots",
        "status",
        "created_at",
    )
    list_display_links = (
        "title",
        "project",
    )
    list_filter = (
        "role",
        "required_level",
        "status",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "title",
        "description",
        "project__title",
        "role__name",
    )
    raw_id_fields = (
        "project",
        "role",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "display_remaining_slots",
    )
    date_hierarchy = "created_at"

    fieldsets = (
        (
            _("Проект и роль"),
            {
                "fields": (
                    "project",
                    "role",
                    "title",
                    "description",
                ),
            },
        ),
        (
            _("Требования и набор"),
            {
                "fields": (
                    "required_level",
                    "required_count",
                    "current_count",
                    "display_remaining_slots",
                    "status",
                ),
            },
        ),
        (
            _("Служебная информация"),
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    @admin.display(description="Свободных мест")
    def display_remaining_slots(self, obj: ProjectVacancy) -> int:
        return obj.remaining_slots()


@admin.register(ProjectMembership)
class ProjectMembershipAdmin(ImportExportModelAdmin, SimpleHistoryAdmin):
    """Админ-панель участников команд."""

    list_display = (
        "project",
        "specialist",
        "role",
        "status",
        "joined_at",
        "left_at",
        "added_by",
        "display_is_active",
    )
    list_display_links = (
        "project",
        "specialist",
    )
    list_filter = (
        "role",
        "status",
        "joined_at",
        "left_at",
    )
    search_fields = (
        "project__title",
        "specialist__user__username",
        "specialist__user__email",
        "specialist__user__first_name",
        "specialist__user__last_name",
        "role__name",
    )
    raw_id_fields = (
        "project",
        "specialist",
        "role",
        "added_by",
    )
    readonly_fields = ("joined_at",)
    date_hierarchy = "joined_at"

    @admin.display(boolean=True, description="Активен")
    def display_is_active(self, obj: ProjectMembership) -> bool:
        return obj.is_active()


@admin.register(ProjectFile)
class ProjectFileAdmin(ImportExportModelAdmin):
    """Админ-панель файлов проектов."""

    list_display = (
        "title",
        "project",
        "file_type",
        "uploaded_by",
        "uploaded_at",
    )
    list_display_links = (
        "title",
        "project",
    )
    list_filter = (
        "file_type",
        "uploaded_at",
    )
    search_fields = (
        "title",
        "project__title",
        "uploaded_by__username",
        "uploaded_by__email",
    )
    raw_id_fields = (
        "project",
        "uploaded_by",
    )
    readonly_fields = ("uploaded_at",)
    date_hierarchy = "uploaded_at"
