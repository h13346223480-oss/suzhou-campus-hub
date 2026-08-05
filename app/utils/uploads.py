from pathlib import Path
from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


def save_image(upload):
    safe_name = secure_filename(upload.filename or "")
    if "." not in safe_name:
        raise ValueError("图片缺少扩展名")
    extension = safe_name.rsplit(".", 1)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("仅支持 jpg、jpeg、png 或 webp 图片")
    random_name = f"{uuid4().hex}.{extension}"
    target = Path(current_app.config["UPLOAD_FOLDER"]) / random_name
    upload.save(target)
    return f"uploads/{random_name}"

