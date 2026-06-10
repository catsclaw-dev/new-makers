from __future__ import annotations

from pathlib import Path
import stat
from zipfile import BadZipFile, ZipFile
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.utils.translation import gettext_lazy as _
from PIL import Image, UnidentifiedImageError


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
IMAGE_FORMATS = {
    "jpg": {"JPEG"},
    "jpeg": {"JPEG"},
    "png": {"PNG"},
    "webp": {"WEBP"},
}
MAX_ARCHIVE_FILES = 1000
MAX_ARCHIVE_UNCOMPRESSED_SIZE = 100 * 1024 * 1024


def validate_file_size(file: UploadedFile, *, max_size_mb: int) -> None:
    """
    Проверяет максимальный размер загружаемого файла.
    Args:
        file: Значение параметра `file`
        max_size_mb: Значение параметра `max_size_mb`
    """
    max_size_bytes = max_size_mb * 1024 * 1024

    if file.size > max_size_bytes:
        raise ValidationError(
            _("Размер файла не должен превышать %(max_size_mb)s МБ."),
            params={
                "max_size_mb": max_size_mb,
            },
        )


def validate_file_extension(file: UploadedFile, *, allowed_extensions: set[str]) -> None:
    """
    Проверяет расширение загружаемого файла.
    Args:
        file: Значение параметра `file`
        allowed_extensions: Значение параметра `allowed_extensions`
    """
    extension = Path(file.name).suffix.lower().lstrip(".")

    if extension not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise ValidationError(
            _("Недопустимый формат файла. Разрешены: %(allowed)s."),
            params={
                "allowed": allowed,
            },
        )


def _extension(file: UploadedFile) -> str:
    return Path(file.name).suffix.lower().lstrip(".")


def _rewind(file: UploadedFile) -> None:
    try:
        file.seek(0)
    except (AttributeError, OSError):
        pass


def validate_image_content(file: UploadedFile) -> None:
    """Проверяет декодирование изображения и соответствие расширению."""
    extension = _extension(file)
    try:
        _rewind(file)
        with Image.open(file) as image:
            image.verify()
            image_format = image.format
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as error:
        raise ValidationError(_("Файл не является корректным изображением.")) from error
    finally:
        _rewind(file)

    if image_format not in IMAGE_FORMATS.get(extension, set()):
        raise ValidationError(_("Содержимое изображения не соответствует расширению файла."))


def validate_zip_content(file: UploadedFile, *, require_docx: bool = False) -> None:
    """Проверяет структуру ZIP/DOCX и защищает от path traversal и zip bomb."""
    try:
        _rewind(file)
        with ZipFile(file) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ARCHIVE_FILES:
                raise ValidationError(_("Архив содержит слишком много файлов."))

            total_size = 0
            names = set()
            for entry in entries:
                path = Path(entry.filename)
                if path.is_absolute() or ".." in path.parts:
                    raise ValidationError(_("Архив содержит небезопасный путь."))
                if entry.flag_bits & 0x1:
                    raise ValidationError(_("Зашифрованные архивы не поддерживаются."))
                mode = entry.external_attr >> 16
                if mode and stat.S_ISLNK(mode):
                    raise ValidationError(_("Архив не должен содержать символические ссылки."))

                total_size += entry.file_size
                if total_size > MAX_ARCHIVE_UNCOMPRESSED_SIZE:
                    raise ValidationError(_("Распакованный архив слишком большой."))
                names.add(entry.filename)

            if require_docx and (
                "[Content_Types].xml" not in names
                or not any(name.startswith("word/") for name in names)
            ):
                raise ValidationError(_("Файл не является корректным документом DOCX."))
    except (BadZipFile, OSError, ValueError) as error:
        raise ValidationError(_("Файл не является корректным ZIP-архивом.")) from error
    finally:
        _rewind(file)


def validate_project_file_content(file: UploadedFile) -> None:
    """Проверяет сигнатуру и структуру прикрепляемого файла."""
    extension = _extension(file)

    if extension in IMAGE_EXTENSIONS:
        validate_image_content(file)
        return
    if extension == "zip":
        validate_zip_content(file)
        return
    if extension == "docx":
        validate_zip_content(file, require_docx=True)
        return

    _rewind(file)
    header = file.read(8)
    content = header + file.read() if extension == "txt" else header
    _rewind(file)

    if extension == "pdf" and not header.startswith(b"%PDF-"):
        raise ValidationError(_("Файл не является корректным PDF-документом."))
    if extension == "doc" and not header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        raise ValidationError(_("Файл не является корректным DOC-документом."))
    if extension == "txt":
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValidationError(_("Текстовый файл должен быть в кодировке UTF-8.")) from error
        if b"\x00" in content:
            raise ValidationError(_("Текстовый файл содержит бинарные данные."))


def validate_iana_timezone(value: str) -> None:
    """Проверяет, что строка является существующим IANA timezone identifier."""
    if not value:
        return
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValidationError(_("Укажи корректный часовой пояс IANA.")) from error


def validate_avatar_image(file: UploadedFile) -> None:
    """
    Проверяет аватар специалиста.
    Args:
        file: Значение параметра `file`
    """
    validate_file_size(file, max_size_mb=2)
    validate_file_extension(file, allowed_extensions=IMAGE_EXTENSIONS)
    validate_image_content(file)


def validate_project_cover_image(file: UploadedFile) -> None:
    """
    Проверяет обложку проекта.
    Args:
        file: Значение параметра `file`
    """
    validate_file_size(file, max_size_mb=5)
    validate_file_extension(file, allowed_extensions=IMAGE_EXTENSIONS)
    validate_image_content(file)


def validate_project_file(file: UploadedFile) -> None:
    """
    Проверяет файл, прикрепляемый к проекту.
    Args:
        file: Значение параметра `file`
    """
    validate_file_size(file, max_size_mb=10)
    validate_file_extension(file, allowed_extensions=PROJECT_FILE_EXTENSIONS)
    validate_project_file_content(file)
