from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func, or_

from app.extensions import db
from app.forms import CommentForm, POST_CATEGORIES, PostForm, ReportForm
from app.majors import PENDING_CONFIRMATION, USER_MAJOR_CODES
from app.models import Bookmark, Comment, Post, Report, User
from app.utils.sanitize import sanitize_html
from app.utils.security import verified_required
from app.utils.uploads import save_image

bp = Blueprint("posts", __name__, url_prefix="/posts")


def visible_categories():
    if current_app.config["FEATURE_TUTORING_PUBLIC"]:
        return POST_CATEGORIES
    return [item for item in POST_CATEGORIES if item != "家教相关"]


def ensure_post_visible(post):
    if post.status != "approved":
        abort(404)
    if post.category == "家教相关" and not current_app.config["FEATURE_TUTORING_PUBLIC"]:
        abort(404)


@bp.route("")
def index():
    categories = visible_categories()
    category = request.args.get("category", "").strip()
    keyword = request.args.get("q", "").strip()
    major_code = request.args.get("major", "").strip()
    sort = request.args.get("sort", "latest")
    query = Post.query.filter_by(status="approved")
    if not current_app.config["FEATURE_TUTORING_PUBLIC"]:
        query = query.filter(Post.category != "家教相关")
    if category in categories:
        query = query.filter_by(category=category)
    if keyword:
        query = query.filter(or_(Post.title.contains(keyword), Post.content.contains(keyword)))
    if major_code in USER_MAJOR_CODES and major_code != PENDING_CONFIRMATION:
        query = query.join(User, Post.author_id == User.id).filter(
            User.major_code == major_code,
            Post.is_anonymous.is_(False),
        )
    if sort == "popular":
        query = query.outerjoin(Comment).group_by(Post.id).order_by((Post.view_count + func.count(Comment.id) * 3).desc())
    else:
        query = query.order_by(Post.created_at.desc())
    pagination = query.paginate(page=request.args.get("page", 1, type=int), per_page=8, error_out=False)
    return render_template("posts/index.html", pagination=pagination, categories=categories,
                           selected=category, selected_major=major_code, keyword=keyword, sort=sort)


@bp.route("/<int:post_id>")
def detail(post_id):
    post = db.get_or_404(Post, post_id)
    if post.category == "家教相关" and not current_app.config["FEATURE_TUTORING_PUBLIC"] and not current_user.is_admin:
        abort(404)
    can_preview = current_user.is_authenticated and (current_user.is_admin or current_user.id == post.author_id)
    if post.status != "approved" and not can_preview:
        abort(404)
    post.view_count += 1
    db.session.commit()
    bookmarked = current_user.is_authenticated and Bookmark.query.filter_by(user_id=current_user.id, post_id=post.id).first()
    return render_template("posts/detail.html", post=post, comment_form=CommentForm(), report_form=ReportForm(), bookmarked=bool(bookmarked))


@bp.route("/create", methods=["GET", "POST"])
@verified_required
def create():
    form = PostForm()
    form.category.choices = [(item, item) for item in visible_categories()]
    if form.validate_on_submit():
        clean_content = sanitize_html(form.content.data.strip())
        if len(clean_content) < 10:
            form.content.errors.append("正文内容不足，请补充有效文字。")
        else:
            is_admin = current_user.is_admin
            post = Post(author_id=current_user.id, title=form.title.data.strip(), category=form.category.data,
                        content=clean_content, is_anonymous=form.is_anonymous.data,
                        status="approved" if is_admin else "pending")
            db.session.add(post)
            db.session.commit()
            flash("信息已发布，将直接公开。" if is_admin else "信息已提交，将在管理员审核后公开。", "success")
            return redirect(url_for("main.profile"))
    if current_user.is_admin:
        form.submit.label.text = "直接发布"
    return render_template("posts/create.html", form=form)


@bp.route("/upload-image", methods=["POST"])
@verified_required
def upload_image():
    upload = request.files.get("image")
    if not upload or not upload.filename:
        return {"error": "未选择图片"}, 400
    try:
        image_path = save_image(upload)
    except ValueError as exc:
        return {"error": str(exc)}, 400
    return {"location": url_for("static", filename=image_path)}


@bp.route("/<int:post_id>/comment", methods=["POST"])
@verified_required
def comment(post_id):
    post = db.get_or_404(Post, post_id)
    ensure_post_visible(post)
    form = CommentForm()
    if form.validate_on_submit():
        db.session.add(Comment(post_id=post.id, author_id=current_user.id, content=form.content.data.strip()))
        db.session.commit()
        flash("评论已发布。", "success")
    else:
        flash("评论内容需为 2—1000 个字符，且不能含 HTML。", "danger")
    return redirect(url_for("posts.detail", post_id=post.id))


@bp.route("/<int:post_id>/bookmark", methods=["POST"])
@verified_required
def bookmark(post_id):
    post = db.get_or_404(Post, post_id)
    ensure_post_visible(post)
    existing = Bookmark.query.filter_by(user_id=current_user.id, post_id=post.id).first()
    if existing:
        db.session.delete(existing)
        message = "已取消收藏。"
    else:
        db.session.add(Bookmark(user_id=current_user.id, post_id=post.id))
        message = "已收藏。"
    db.session.commit()
    flash(message, "success")
    return redirect(url_for("posts.detail", post_id=post.id))


@bp.route("/<int:post_id>/report", methods=["POST"])
@verified_required
def report(post_id):
    post = db.get_or_404(Post, post_id)
    ensure_post_visible(post)
    form = ReportForm()
    if form.validate_on_submit():
        db.session.add(Report(reporter_id=current_user.id, target_type="post", target_id=post.id, reason=form.reason.data.strip()))
        db.session.commit()
        flash("举报已提交，管理员会尽快处理。", "success")
    else:
        flash("请填写至少 5 个字符的举报原因。", "danger")
    return redirect(url_for("posts.detail", post_id=post.id))


@bp.route("/<int:post_id>/edit", methods=["GET", "POST"])
@verified_required
def edit(post_id):
    post = db.get_or_404(Post, post_id)
    if not (current_user.is_admin or current_user.id == post.author_id):
        abort(403)
    form = PostForm(obj=post)
    form.category.choices = [(item, item) for item in visible_categories()]
    if form.validate_on_submit():
        clean_content = sanitize_html(form.content.data.strip())
        if len(clean_content) < 10:
            form.content.errors.append("正文内容不足，请补充有效文字。")
        else:
            post.title = form.title.data.strip()
            post.category = form.category.data
            post.content = clean_content
            post.is_anonymous = form.is_anonymous.data
            post.status = "approved" if current_user.is_admin else "pending"
            db.session.commit()
            flash("帖子已更新，将直接公开。" if current_user.is_admin else "帖子已更新，正在等待管理员重新审核。", "success")
            return redirect(url_for("posts.detail", post_id=post.id))
    form.submit.label.text = "保存并直接公开" if current_user.is_admin else "提交修改"
    return render_template("posts/create.html", form=form, editing=True)


@bp.route("/<int:post_id>/delete", methods=["POST"])
@verified_required
def delete(post_id):
    post = db.get_or_404(Post, post_id)
    if not (current_user.is_admin or current_user.id == post.author_id):
        abort(403)
    post.status = "hidden"
    db.session.commit()
    flash("帖子已删除，前台不再展示，管理员可在后台存档查看。", "success")
    return redirect(url_for("posts.index"))


@bp.route("/comments/<int:comment_id>/edit", methods=["GET", "POST"])
@verified_required
def edit_comment(comment_id):
    comment = db.get_or_404(Comment, comment_id)
    if not (current_user.is_admin or current_user.id == comment.author_id):
        abort(403)
    form = CommentForm(obj=comment)
    if form.validate_on_submit():
        comment.content = form.content.data.strip()
        db.session.commit()
        flash("评论已更新。", "success")
        return redirect(url_for("posts.detail", post_id=comment.post_id))
    form.submit.label.text = "保存修改"
    return render_template("posts/comment_edit.html", form=form, comment=comment)


@bp.route("/comments/<int:comment_id>/delete", methods=["POST"])
@verified_required
def delete_comment(comment_id):
    comment = db.get_or_404(Comment, comment_id)
    if not (current_user.is_admin or current_user.id == comment.author_id):
        abort(403)
    comment.status = "hidden"
    db.session.commit()
    flash("评论已删除，前台不再展示。", "success")
    return redirect(url_for("posts.detail", post_id=comment.post_id))
