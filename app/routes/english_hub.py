from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy import or_

from app.extensions import db
from app.forms import ENGLISH_CATEGORIES, EnglishResourceForm
from app.majors import RESOURCE_MAJOR_CODES
from app.models import EnglishResource
from flask_login import current_user

from app.utils.security import verified_required

bp = Blueprint("english_hub", __name__, url_prefix="/english-hub")


@bp.route("")
def index():
    category = request.args.get("category", "").strip()
    major = request.args.get("major", "").strip()
    keyword = request.args.get("q", "").strip()
    query = EnglishResource.query.filter_by(status="published")
    if category in ENGLISH_CATEGORIES:
        query = query.filter_by(category=category)
    if major in RESOURCE_MAJOR_CODES:
        query = query.filter_by(major_code=major)
    if keyword:
        query = query.filter(or_(EnglishResource.title.contains(keyword), EnglishResource.content.contains(keyword)))
    resources = query.order_by(EnglishResource.created_at.desc()).all()
    return render_template("english_hub/index.html", resources=resources, categories=ENGLISH_CATEGORIES,
                           selected=category, selected_major=major, keyword=keyword)


@bp.route("/submit", methods=["GET", "POST"])
@verified_required
def submit():
    form = EnglishResourceForm()
    if form.validate_on_submit():
        resource = EnglishResource(title=form.title.data.strip(), category=form.category.data,
                                   content=form.content.data.strip(), difficulty=form.difficulty.data,
                                   status="published" if current_user.is_admin else "pending",
                                   author_id=current_user.id)
        resource.set_major(form.major.data)
        db.session.add(resource)
        db.session.commit()
        flash("学习经验已发布。" if current_user.is_admin else "学习经验已提交审核。", "success")
        return redirect(url_for("english_hub.index"))
    return render_template("english_hub/submit.html", form=form)


@bp.route("/<int:resource_id>/edit", methods=["GET", "POST"])
@verified_required
def edit(resource_id):
    resource = db.get_or_404(EnglishResource, resource_id)
    if not (current_user.is_admin or current_user.id == resource.author_id):
        abort(403)
    form = EnglishResourceForm(obj=resource)
    if request.method == "GET":
        form.major.data = resource.major_code
    if form.validate_on_submit():
        resource.title = form.title.data.strip()
        resource.category = form.category.data
        resource.content = form.content.data.strip()
        resource.difficulty = form.difficulty.data
        resource.set_major(form.major.data)
        resource.status = "published" if current_user.is_admin else "pending"
        db.session.commit()
        flash("学习经验已更新，将直接公开。" if current_user.is_admin else "学习经验已更新，正在等待管理员重新审核。", "success")
        return redirect(url_for("english_hub.index"))
    form.submit.label.text = "保存并直接公开" if current_user.is_admin else "提交修改"
    return render_template("english_hub/submit.html", form=form, editing=True)


@bp.route("/<int:resource_id>/delete", methods=["POST"])
@verified_required
def delete(resource_id):
    resource = db.get_or_404(EnglishResource, resource_id)
    if not (current_user.is_admin or current_user.id == resource.author_id):
        abort(403)
    resource.status = "hidden"
    db.session.commit()
    flash("学习经验已删除，前台不再展示，管理员可在后台存档查看。", "success")
    return redirect(url_for("english_hub.index"))
