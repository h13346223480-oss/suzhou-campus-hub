from pathlib import Path
from uuid import uuid4

from flask import current_app
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


def _save_image_to(upload, folder):
    safe_name = secure_filename(upload.filename or "")
    if "." not in safe_name:
        raise ValueError("图片缺少扩展名")
    extension = safe_name.rsplit(".", 1)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("仅支持 jpg、jpeg、png 或 webp 图片")
    random_name = f"{uuid4().hex}.{extension}"
    target = folder / random_name
    upload.save(target)
    try:
        with Image.open(target) as image:
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        target.unlink(missing_ok=True)
        raise ValueError("图片内容无效，请重新选择")
    return random_name


def save_image(upload):
    random_name = _save_image_to(upload, Path(current_app.config["UPLOAD_FOLDER"]))
    return f"uploads/{random_name}"


def save_id_photo(upload):
    return _save_image_to(upload, Path(current_app.config["ID_PHOTO_FOLDER"]))
