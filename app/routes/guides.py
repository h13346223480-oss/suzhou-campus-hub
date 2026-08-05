from flask import Blueprint, render_template, request
from sqlalchemy import or_

from app.forms import GUIDE_CATEGORIES, LOCATION_CATEGORIES
from app.models import CampusLocation, Guide

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
