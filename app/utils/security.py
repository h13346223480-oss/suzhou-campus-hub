import re
from functools import wraps

from flask import abort, flash, redirect, request, url_for
from flask_login import current_user

HTML_PATTERN = re.compile(r"<[^>]*>|javascript:", re.IGNORECASE)


def contains_html(value):
    return bool(value and HTML_PATTERN.search(value))


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def verified_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        if not current_user.is_verified:
            flash("当前账号的校园社区权限不可用，请联系平台管理员。", "warning")
            return redirect(url_for("main.profile"))
        return view(*args, **kwargs)

    return wrapped
