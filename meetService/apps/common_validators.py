from pathlib import Path

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
PROJECT_FILE_EXTENSIONS = {
    "pdf",
    "doc",
    "docx",
    "txt",
    "png",
    "jpg",
    "jpeg",
    "webp",
    "zip",
}


def validate_file_size(file, *, max_size_mb: int) -> None:
    """Проверяет максимальный размер загружаемого файла."""
    max_size_bytes = max_size_mb * 1024 * 1024

    if file.size > max_size_bytes:
        raise ValidationError(
            _("Размер файла не должен превышать %(max_size_mb)s МБ."),
            params={
                "max_size_mb": max_size_mb,
            },
        )


def validate_file_extension(file, *, allowed_extensions: set[str]) -> None:
    """Проверяет расширение загружаемого файла."""
    extension = Path(file.name).suffix.lower().lstrip(".")

    if extension not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise ValidationError(
            _("Недопустимый формат файла. Разрешены: %(allowed)s."),
            params={
                "allowed": allowed,
            },
        )


def validate_avatar_image(file) -> None:
    """Проверяет аватар специалиста."""
    validate_file_size(file, max_size_mb=2)
    validate_file_extension(file, allowed_extensions=IMAGE_EXTENSIONS)


def validate_project_cover_image(file) -> None:
    """Проверяет обложку проекта."""
    validate_file_size(file, max_size_mb=5)
    validate_file_extension(file, allowed_extensions=IMAGE_EXTENSIONS)


def validate_project_file(file) -> None:
    """Проверяет файл, прикрепляемый к проекту."""
    validate_file_size(file, max_size_mb=10)
    validate_file_extension(file, allowed_extensions=PROJECT_FILE_EXTENSIONS)
