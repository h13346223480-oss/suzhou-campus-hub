from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import or_

from app.extensions import db
from app.forms import GUIDE_CATEGORIES, LOCATION_CATEGORIES, GuideForm
from app.models import CampusLocation, Guide
from app.utils.sanitize import sanitize_html
from app.utils.security import admin_required

bp = Blueprint("guides", __name__, url_prefix="/guides")


@bp.route("")
def index():
    category = request.args.get("category", "").strip()
    keyword = request.args.get("q", "").strip()
    query = Guide.query.filter_by(status="published")
    if category in GUIDE_CATEGORIES:
        query = query.filter_by(category=category)
    if keyword:
        query = query.filter(or_(Guide.title.contains(keyword), Guide.summary.contains(keyword), Guide.content.contains(keyword)))
    guides = query.order_by(Guide.updated_at.desc()).all()
    return render_template("guides/index.html", guides=guides, categories=GUIDE_CATEGORIES, selected=category, keyword=keyword)


@bp.route("/create", methods=["GET", "POST"])
@admin_required
def create():
    form = GuideForm()
    if form.validate_on_submit():
        clean_content = sanitize_html(form.content.data.strip())
        if len(clean_content) < 10:
            form.content.errors.append("正文内容不足，请补充有效文字。")
        else:
            slug = unique_guide_slug()
            guide = Guide(title=form.title.data.strip(), slug=slug,
                          summary=form.summary.data.strip()[:240] or form.title.data.strip(),
                          content=clean_content, category=form.category.data, status="published")
            db.session.add(guide)
            db.session.commit()
            flash("指南已发布。", "success")
            return redirect(url_for("guides.detail", slug=slug))
    return render_template("guides/create.html", form=form)


@bp.route("/<slug>/edit", methods=["GET", "POST"])
@admin_required
def edit(slug):
    guide = Guide.query.filter_by(slug=slug).first_or_404()
    form = GuideForm(obj=guide)
    if request.method == "GET":
        form.summary.data = guide.summary
    if form.validate_on_submit():
        clean_content = sanitize_html(form.content.data.strip())
        if len(clean_content) < 10:
            form.content.errors.append("正文内容不足，请补充有效文字。")
        else:
            guide.title = form.title.data.strip()
            guide.summary = form.summary.data.strip()[:240] or guide.title
            guide.content = clean_content
            guide.category = form.category.data
            db.session.commit()
            flash("指南已更新。", "success")
            return redirect(url_for("guides.detail", slug=guide.slug))
    form.submit.label.text = "保存修改"
    return render_template("guides/create.html", form=form, editing=True)


@bp.route("/<slug>/delete", methods=["POST"])
@admin_required
def delete(slug):
    guide = Guide.query.filter_by(slug=slug).first_or_404()
    guide.status = "hidden"
    db.session.commit()
    flash("指南已删除，前台不再展示，可在后台存档查看。", "success")
    return redirect(url_for("guides.index"))


def unique_guide_slug():
    index = Guide.query.count() + 1
    while Guide.query.filter_by(slug=f"guide-{index}").first():
        index += 1
    return f"guide-{index}"


@bp.route("/<slug>")
def detail(slug):
    guide = Guide.query.filter_by(slug=slug, status="published").first_or_404()
    return render_template("guides/detail.html", guide=guide)


@bp.route("/faq")
def faq():
    items = Guide.query.filter_by(category="常见问题", status="published").all()
    return render_template("guides/faq.html", items=items)


@bp.route("/campus-map")
def campus_map():
    category = request.args.get("category", "").strip()
    query = CampusLocation.query.filter_by(status="published")
    if category in LOCATION_CATEGORIES:
        query = query.filter_by(category=category)
    locations = query.order_by(CampusLocation.category, CampusLocation.name).all()
    return render_template("guides/map.html", locations=locations, categories=LOCATION_CATEGORIES, selected=category)
