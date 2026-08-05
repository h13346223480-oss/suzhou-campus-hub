from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import or_

from app.extensions import db
from app.forms import ENGLISH_CATEGORIES, EnglishResourceForm
from app.majors import RESOURCE_MAJOR_CODES
from app.models import EnglishResource
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
                                   status="pending")
        resource.set_major(form.major.data)
        db.session.add(resource)
        db.session.commit()
        flash("学习经验已提交审核。", "success")
        return redirect(url_for("english_hub.index"))
    return render_template("english_hub/submit.html", form=form)
