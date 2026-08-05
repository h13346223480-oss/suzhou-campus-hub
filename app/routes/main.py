from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_

from app.extensions import db
from app.forms import MajorForm, PasswordForm
from app.majors import PENDING_CONFIRMATION_CHOICES
from app.models import Bookmark, EnglishResource, Guide, Post, Survey, SurveyResponse, TutorProfile
from app.services.surveys import availability

bp = Blueprint("main", __name__)


@bp.route("/")
def home():
    post_query = Post.query.filter_by(status="approved")
    if not current_app.config["FEATURE_TUTORING_PUBLIC"]:
        post_query = post_query.filter(Post.category != "家教相关")
    latest_posts = post_query.order_by(Post.created_at.desc()).limit(4).all()
    latest_guides = Guide.query.filter_by(status="published").order_by(Guide.updated_at.desc()).limit(3).all()
    active_survey = None
    if current_app.config["FEATURE_SURVEYS_PUBLIC"]:
        active_survey = next((item for item in Survey.query.filter_by(status="published").order_by(Survey.created_at.desc()).all()
                              if availability(item) == "open"), None)
    return render_template("main/home.html", latest_posts=latest_posts, latest_guides=latest_guides,
                           active_survey=active_survey)


@bp.route("/search")
def search():
    keyword = request.args.get("q", "").strip()
    posts, guides, resources = [], [], []
    if keyword:
        post_query = Post.query.filter_by(status="approved")
        if not current_app.config["FEATURE_TUTORING_PUBLIC"]:
            post_query = post_query.filter(Post.category != "家教相关")
        posts = (post_query
                 .filter(or_(Post.title.contains(keyword), Post.content.contains(keyword)))
                 .order_by(Post.created_at.desc()).limit(8).all())
        guides = (Guide.query.filter_by(status="published")
                  .filter(or_(Guide.title.contains(keyword), Guide.summary.contains(keyword),
                              Guide.content.contains(keyword)))
                  .order_by(Guide.updated_at.desc()).limit(6).all())
        resources = (EnglishResource.query.filter_by(status="published")
                     .filter(or_(EnglishResource.title.contains(keyword),
                                 EnglishResource.content.contains(keyword)))
                     .order_by(EnglishResource.created_at.desc()).limit(6).all())
    return render_template("main/search.html", keyword=keyword, posts=posts, guides=guides, resources=resources)


@bp.route("/about")
def about():
    return render_template("main/about.html")


@bp.route("/terms")
def terms():
    return render_template("main/terms.html")


@bp.route("/privacy")
def privacy():
    return render_template("main/privacy.html")


@bp.route("/community-rules")
def community_rules():
    return render_template("main/community_rules.html")


@bp.route("/profile")
@login_required
def profile():
    posts = Post.query.filter_by(author_id=current_user.id).order_by(Post.created_at.desc()).all()
    bookmarks = Bookmark.query.filter_by(user_id=current_user.id).order_by(Bookmark.created_at.desc()).all()
    tutor_profile = TutorProfile.query.filter_by(user_id=current_user.id).first()
    survey_responses = SurveyResponse.query.filter_by(user_id=current_user.id, is_valid=True).order_by(
        SurveyResponse.submitted_at.desc()).limit(5).all()
    return render_template("main/profile.html", posts=posts, bookmarks=bookmarks, tutor_profile=tutor_profile,
                           survey_responses=survey_responses)


@bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = PasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            form.current_password.errors.append("当前密码不正确。")
        else:
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash("密码已修改。", "success")
            return redirect(url_for("main.profile"))
    return render_template("main/change_password.html", form=form)


@bp.route("/profile/major", methods=["GET", "POST"])
@login_required
def edit_major():
    if current_user.is_admin:
        flash("管理员账号不需要设置学生专业。", "info")
        return redirect(url_for("main.profile"))
    form = MajorForm()
    if current_user.requires_major_confirmation:
        form.major.choices = PENDING_CONFIRMATION_CHOICES
    if form.validate_on_submit():
        current_user.set_major(form.major.data)
        db.session.commit()
        flash("专业信息已更新。", "success")
        return redirect(url_for("main.profile"))
    if not form.is_submitted():
        form.major.data = None if current_user.requires_major_confirmation else current_user.major_code
    return render_template("main/edit_major.html", form=form,
                           requires_confirmation=current_user.requires_major_confirmation)
