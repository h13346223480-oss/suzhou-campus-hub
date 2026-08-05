from datetime import datetime, timedelta, timezone
from secrets import token_hex
from zoneinfo import ZoneInfo

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import or_

from app.extensions import db
from app.forms import ENGLISH_CATEGORIES, GUIDE_CATEGORIES, LOCATION_CATEGORIES
from app.majors import RESOURCE_MAJOR_CODES, USER_MAJOR_CODES, normalize_resource_major
from app.models import CampusLocation, Comment, EnglishResource, Guide, InviteCode, InviteRedemption, Post, Report, TutorProfile, TutorRequest, User, utcnow
from app.utils.security import admin_required, contains_html
from app.utils.uploads import save_image

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("")
@admin_required
def dashboard():
    stats = {
        "restricted_users": User.query.filter(
            User.role != "admin",
            or_(User.verification_status != "verified", User.is_active.is_(False)),
        ).count(),
        "pending_posts": Post.query.filter_by(status="pending").count(),
        "open_reports": Report.query.filter_by(status="pending").count(),
        "tutor_requests": TutorRequest.query.filter_by(status="pending").count(),
    }
    return render_template("admin/dashboard.html", stats=stats)


@bp.route("/users")
@admin_required
def users():
    major_code = request.args.get("major", "").strip()
    query = User.query
    if major_code in USER_MAJOR_CODES:
        query = query.filter_by(major_code=major_code)
    return render_template("admin/users.html", users=query.order_by(User.created_at.desc()).all(),
                           selected_major=major_code)


@bp.route("/invites", methods=["GET", "POST"])
@admin_required
def invites():
    if request.method == "POST":
        max_uses = request.form.get("max_uses", type=int)
        expires_value = request.form.get("expires_at", "").strip()
        try:
            local_expiry = datetime.fromisoformat(expires_value)
            expires_at = local_expiry.replace(tzinfo=ZoneInfo("Asia/Shanghai")).astimezone(timezone.utc)
        except ValueError:
            expires_at = None
        if not max_uses or not 1 <= max_uses <= 1000:
            flash("最大使用次数必须在 1 到 1000 之间。", "danger")
        elif not expires_at or expires_at <= utcnow():
            flash("失效时间必须是未来的北京时间。", "danger")
        else:
            code = generate_invite_code()
            db.session.add(InviteCode(code=code, max_uses=max_uses, expires_at=expires_at, is_active=True))
            db.session.commit()
            flash("邀请码已创建。", "success")
            return redirect(url_for("admin.invites"))
    default_expiry = (datetime.now(ZoneInfo("Asia/Shanghai")) + timedelta(days=30)).replace(second=0, microsecond=0)
    return render_template(
        "admin/invites.html",
        invites=InviteCode.query.order_by(InviteCode.id.desc()).all(),
        default_expiry=default_expiry,
        display_expiry=display_expiry,
        invite_redemption_model=InviteRedemption,
    )


@bp.route("/invites/<int:invite_id>/toggle", methods=["POST"])
@admin_required
def toggle_invite(invite_id):
    invite = db.get_or_404(InviteCode, invite_id)
    invite.is_active = not invite.is_active
    db.session.commit()
    flash("邀请码状态已更新。", "success")
    return redirect(url_for("admin.invites"))


def generate_invite_code():
    while True:
        code = f"SZ-{token_hex(5).upper()}"
        if not InviteCode.query.filter_by(code=code).first():
            return code


def display_expiry(value):
    if value is None:
        return "未设置"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M")


@bp.route("/users/<int:user_id>/verify", methods=["POST"])
@admin_required
def verify_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.is_admin:
        abort(400)
    user.verification_status = "verified"
    db.session.commit()
    flash("学生认证已通过。", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:user_id>/revoke", methods=["POST"])
@admin_required
def revoke_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.is_admin:
        abort(400)
    user.verification_status = "revoked"
    db.session.commit()
    flash("该用户的校园社区权限已撤销。", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@admin_required
def toggle_user_active(user_id):
    user = db.get_or_404(User, user_id)
    if user.is_admin:
        abort(400)
    user.is_active = not user.is_active
    db.session.commit()
    flash("用户账号状态已更新。", "success")
    return redirect(url_for("admin.users"))


@bp.route("/invites/<int:invite_id>/delete", methods=["POST"])
@admin_required
def delete_invite(invite_id):
    invite = db.get_or_404(InviteCode, invite_id)
    if invite.used_count or invite.redemptions.count():
        flash("已有使用记录的邀请码不能删除，请将其停用。", "danger")
    else:
        db.session.delete(invite)
        db.session.commit()
        flash("未使用的邀请码已删除。", "success")
    return redirect(url_for("admin.invites"))


@bp.route("/posts")
@admin_required
def posts():
    return render_template("admin/posts.html", posts=Post.query.order_by(Post.created_at.desc()).all())


@bp.route("/posts/<int:post_id>/<action>", methods=["POST"])
@admin_required
def moderate_post(post_id, action):
    post = db.get_or_404(Post, post_id)
    if action not in {"approve", "hide", "delete"}:
        abort(404)
    if action == "delete":
        db.session.delete(post)
    else:
        post.status = "approved" if action == "approve" else "hidden"
    db.session.commit()
    flash("帖子状态已更新。", "success")
    return redirect(url_for("admin.posts"))


@bp.route("/comments")
@admin_required
def comments():
    return render_template("admin/comments.html", comments=Comment.query.order_by(Comment.created_at.desc()).all())


@bp.route("/comments/<int:comment_id>/hide", methods=["POST"])
@admin_required
def hide_comment(comment_id):
    comment = db.get_or_404(Comment, comment_id)
    comment.status = "hidden"
    db.session.commit()
    flash("评论已隐藏。", "success")
    return redirect(url_for("admin.comments"))


@bp.route("/reports")
@admin_required
def reports():
    return render_template("admin/reports.html", reports=Report.query.order_by(Report.created_at.desc()).all())


@bp.route("/reports/<int:report_id>/resolve", methods=["POST"])
@admin_required
def resolve_report(report_id):
    report = db.get_or_404(Report, report_id)
    report.status = "resolved"
    db.session.commit()
    flash("举报已标记为已处理。", "success")
    return redirect(url_for("admin.reports"))


@bp.route("/tutors")
@admin_required
def tutors():
    return render_template("admin/tutors.html", profiles=TutorProfile.query.order_by(TutorProfile.created_at.desc()).all())


@bp.route("/tutors/<int:profile_id>/<action>", methods=["POST"])
@admin_required
def moderate_tutor(profile_id, action):
    profile = db.get_or_404(TutorProfile, profile_id)
    if action not in {"approve", "reject"}:
        abort(404)
    profile.status = "approved" if action == "approve" else "rejected"
    db.session.commit()
    flash("家教资料状态已更新。", "success")
    return redirect(url_for("admin.tutors"))


@bp.route("/tutor-requests")
@admin_required
def tutor_requests():
    records = TutorRequest.query.order_by(TutorRequest.created_at.desc()).all()
    return render_template("admin/tutor_requests.html", requests=records)


@bp.route("/tutor-requests/<int:request_id>")
@admin_required
def tutor_request_detail(request_id):
    record = db.get_or_404(TutorRequest, request_id)
    return render_template("admin/tutor_request_detail.html", item=record)


@bp.route("/tutor-requests/<int:request_id>/match", methods=["POST"])
@admin_required
def match_tutor_request(request_id):
    record = db.get_or_404(TutorRequest, request_id)
    record.status = "matched"
    db.session.commit()
    flash("需求已标记为已匹配。", "success")
    return redirect(url_for("admin.tutor_requests"))


@bp.route("/content", methods=["GET", "POST"])
@admin_required
def content():
    if request.method == "POST":
        kind = request.form.get("kind")
        title = request.form.get("title", "").strip()
        body = request.form.get("content", "").strip()
        category = request.form.get("category", "").strip()
        if not title or not body or contains_html(title) or contains_html(body):
            flash("标题和内容不能为空，也不能包含 HTML。", "danger")
        elif kind == "guide" and category in GUIDE_CATEGORIES:
            base_slug = request.form.get("slug", "").strip() or f"guide-{Guide.query.count() + 1}"
            if Guide.query.filter_by(slug=base_slug).first():
                flash("文章别名已存在。", "danger")
                return redirect(url_for("admin.content"))
            db.session.add(Guide(title=title, slug=base_slug, summary=request.form.get("summary", title)[:240], content=body, category=category))
            db.session.commit()
            flash("攻略已创建。", "success")
        elif kind == "english" and category in ENGLISH_CATEGORIES:
            major_code = request.form.get("major", "general")
            if major_code not in RESOURCE_MAJOR_CODES:
                flash("请选择有效的适用专业。", "danger")
            else:
                resource = EnglishResource(title=title, content=body, category=category,
                                           difficulty=request.form.get("difficulty", "入门"))
                resource.set_major(major_code)
                db.session.add(resource)
                db.session.commit()
                flash("英语资料已创建。", "success")
        else:
            flash("内容类型或分类无效。", "danger")
        return redirect(url_for("admin.content"))
    return render_template("admin/content.html", guides=Guide.query.all(), resources=EnglishResource.query.all(),
                           guide_categories=GUIDE_CATEGORIES, english_categories=ENGLISH_CATEGORIES)


@bp.route("/content/<kind>/<int:item_id>/delete", methods=["POST"])
@admin_required
def delete_content(kind, item_id):
    model = Guide if kind == "guide" else EnglishResource if kind == "english" else None
    if model is None:
        abort(404)
    db.session.delete(db.get_or_404(model, item_id))
    db.session.commit()
    flash("内容已删除。", "success")
    return redirect(url_for("admin.content"))


@bp.route("/content/<kind>/<int:item_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_content(kind, item_id):
    model = Guide if kind == "guide" else EnglishResource if kind == "english" else None
    if model is None:
        abort(404)
    item = db.get_or_404(model, item_id)
    categories = GUIDE_CATEGORIES if kind == "guide" else ENGLISH_CATEGORIES
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("content", "").strip()
        category = request.form.get("category", "").strip()
        if not title or not body or category not in categories or contains_html(title) or contains_html(body):
            flash("请完整填写有效内容，且不要包含 HTML。", "danger")
        else:
            item.title = title
            item.content = body
            item.category = category
            if kind == "guide":
                item.summary = request.form.get("summary", "").strip()[:240] or title
            else:
                major_code = request.form.get("major", "general")
                if major_code not in RESOURCE_MAJOR_CODES:
                    flash("请选择有效的适用专业。", "danger")
                    return render_template("admin/edit_content.html", item=item, kind=kind,
                                           categories=categories), 400
                item.set_major(normalize_resource_major(major_code))
                item.difficulty = request.form.get("difficulty", "入门")
            db.session.commit()
            flash("内容已更新。", "success")
            return redirect(url_for("admin.content"))
    return render_template("admin/edit_content.html", item=item, kind=kind, categories=categories)


@bp.route("/content/<kind>/<int:item_id>/publish", methods=["POST"])
@admin_required
def publish_content(kind, item_id):
    model = Guide if kind == "guide" else EnglishResource if kind == "english" else None
    if model is None:
        abort(404)
    item = db.get_or_404(model, item_id)
    item.status = "published"
    db.session.commit()
    flash("内容已审核发布。", "success")
    return redirect(url_for("admin.content"))


@bp.route("/locations", methods=["GET", "POST"])
@admin_required
def locations():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        if not name or not description or category not in LOCATION_CATEGORIES or contains_html(name) or contains_html(description):
            flash("请完整填写有效的地点信息。", "danger")
        else:
            image_path = None
            upload = request.files.get("image")
            if upload and upload.filename:
                try:
                    image_path = save_image(upload)
                except ValueError as error:
                    flash(str(error), "danger")
                    return redirect(url_for("admin.locations"))
            db.session.add(CampusLocation(name=name, description=description, category=category, image_path=image_path))
            db.session.commit()
            flash("地图地点已添加。", "success")
        return redirect(url_for("admin.locations"))
    return render_template("admin/locations.html", locations=CampusLocation.query.all(), categories=LOCATION_CATEGORIES)


@bp.route("/locations/<int:location_id>/delete", methods=["POST"])
@admin_required
def delete_location(location_id):
    db.session.delete(db.get_or_404(CampusLocation, location_id))
    db.session.commit()
    flash("地图地点已删除。", "success")
    return redirect(url_for("admin.locations"))


@bp.route("/locations/<int:location_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_location(location_id):
    item = db.get_or_404(CampusLocation, location_id)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        if not name or not description or category not in LOCATION_CATEGORIES or contains_html(name) or contains_html(description):
            flash("请完整填写有效的地点信息。", "danger")
        else:
            item.name, item.description, item.category = name, description, category
            upload = request.files.get("image")
            if upload and upload.filename:
                try:
                    item.image_path = save_image(upload)
                except ValueError as error:
                    flash(str(error), "danger")
                    return redirect(url_for("admin.edit_location", location_id=item.id))
            db.session.commit()
            flash("地图地点已更新。", "success")
            return redirect(url_for("admin.locations"))
    return render_template("admin/edit_location.html", item=item, categories=LOCATION_CATEGORIES)
