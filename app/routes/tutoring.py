from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.extensions import db
from app.forms import TutorProfileForm, TutorRequestForm
from app.models import TutorProfile, TutorRequest
from app.utils.security import verified_required

bp = Blueprint("tutoring", __name__, url_prefix="/tutoring")


def require_public_or_admin():
    if current_app.config["FEATURE_TUTORING_PUBLIC"]:
        return
    if current_user.is_authenticated and current_user.is_admin:
        return
    abort(404)


@bp.route("")
def index():
    require_public_or_admin()
    subject = request.args.get("subject", "").strip()
    max_rate = request.args.get("max_rate", type=int)
    query = TutorProfile.query.filter_by(status="approved")
    if subject:
        query = query.filter(TutorProfile.subjects.contains(subject))
    if max_rate:
        query = query.filter(TutorProfile.expected_hourly_rate <= max_rate)
    profiles = query.order_by(TutorProfile.created_at.desc()).all()
    return render_template("tutoring/index.html", profiles=profiles, subject=subject, max_rate=max_rate)


@bp.route("/request", methods=["GET", "POST"])
def request_tutor():
    require_public_or_admin()
    form = TutorRequestForm()
    if form.validate_on_submit():
        record = TutorRequest(**{name: getattr(form, name).data.strip() if isinstance(getattr(form, name).data, str) else getattr(form, name).data
            for name in ["contact_name", "contact_method", "student_grade", "subjects", "current_level", "target", "location", "budget", "notes"]})
        db.session.add(record)
        db.session.commit()
        flash("需求已安全提交，联系方式仅管理员可见。", "success")
        return redirect(url_for("tutoring.index"))
    return render_template("tutoring/request.html", form=form)


@bp.route("/profile", methods=["GET", "POST"])
@verified_required
def tutor_profile():
    profile = TutorProfile.query.filter_by(user_id=current_user.id).first()
    form = TutorProfileForm(obj=profile)
    if form.validate_on_submit():
        if not profile:
            profile = TutorProfile(user_id=current_user.id)
            db.session.add(profile)
        for name in ["subjects", "high_school_province", "exam_score_description", "strengths", "teaching_style", "available_times", "expected_hourly_rate"]:
            setattr(profile, name, getattr(form, name).data)
        profile.status = "pending"
        db.session.commit()
        flash("家教资料已提交审核。", "success")
        return redirect(url_for("main.profile"))
    return render_template("tutoring/profile_form.html", form=form, profile=profile)
