from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user, logout_user

from app.extensions import db
from app.forms import LoginForm, RegisterForm
from app.models import InviteCode, InviteRedemption, User, utcnow
from app.utils.uploads import save_id_photo

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))
    form = RegisterForm()
    if form.validate_on_submit():
        register_type = (form.register_type.data or "campus").strip()
        invite = None
        code = (form.invite_code.data or "").strip()
        if code:
            invite = InviteCode.query.filter_by(code=code).with_for_update().first()
        photo_path = None
        if form.student_id_photo.data:
            try:
                photo_path = save_id_photo(form.student_id_photo.data)
            except ValueError as exc:
                form.student_id_photo.errors.append(str(exc))
        if register_type == "invite":
            if not code:
                form.invite_code.errors.append("邀请码注册需要填写有效邀请码。")
            elif not invite:
                form.invite_code.errors.append("邀请码无效、已用完或已过期，请核对后重试。")
        elif not form.student_id_photo.data:
            form.student_id_photo.errors.append("请上传校园卡人像面照片。")
        if not form.student_id_photo.errors and not form.invite_code.errors:
            verified = invite is not None
            user = User(
                email=form.email.data.lower().strip(),
                nickname=form.nickname.data.strip(),
                enrollment_year=form.enrollment_year.data,
                verification_status="verified" if verified else "pending",
                joined_via_invite=verified,
                student_id_photo=photo_path,
            )
            user.set_major(form.major.data)
            user.set_password(form.password.data)
            db.session.add(user)
            if invite:
                invite.used_count += 1
                db.session.flush()
                db.session.add(InviteRedemption(invite_code_id=invite.id, user_id=user.id))
            db.session.commit()
            flash("注册成功，你现在可以使用校园社区功能。" if verified else "注册成功，请等待管理员审核，审核通过后即可使用完整功能。", "success")
            session["avatar_guide_pending"] = True
            return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and user.is_active and user.check_password(form.password.data):
            user.last_login_at = utcnow()
            db.session.commit()
            login_user(user, remember=form.remember.data)
            flash("欢迎回来。", "success")
            next_url = request.args.get("next")
            if user.requires_major_confirmation and not next_url:
                flash("原专业记录无法区分机器人工程与智能制造工程，请先重新确认专业。", "warning")
                return redirect(url_for("main.profile"))
            return redirect(next_url if next_url and next_url.startswith("/") else url_for("main.home"))
        flash("邮箱或密码不正确。", "danger")
    return render_template("auth/login.html", form=form)


@bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    flash("你已安全退出。", "success")
    return redirect(url_for("main.home"))


@bp.route("/forgot-password")
def forgot_password():
    return render_template("auth/forgot_password.html")
