from datetime import datetime, timezone

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Poll, PollOption, Vote, utcnow
from app.utils.security import admin_required, contains_html
from app.utils.uploads import save_image

bp = Blueprint("polls", __name__)

MAX_OPTIONS = 10


def _parse_end_time(raw):
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _collect_options(prefix=""):
    """从表单收集新增选项行（标题/描述/图片），返回 [(title, desc, image)]。"""
    options = []
    seen = set()
    for index in range(MAX_OPTIONS):
        title = request.form.get(f"option_title_{prefix}{index}", "").strip()
        description = request.form.get(f"option_desc_{prefix}{index}", "").strip()
        image = None
        upload = request.files.get(f"option_image_{prefix}{index}")
        if upload and upload.filename:
            try:
                image = save_image(upload)
            except ValueError as error:
                flash(str(error), "danger")
                raise
        if not title and not description and not image:
            continue
        if not title:
            flash("每个选项都需要填写标题。", "danger")
            raise ValueError()
        if len(title) > 80 or contains_html(title):
            flash("选项标题不能超过 80 字或包含 HTML 标签。", "danger")
            raise ValueError()
        if len(description) > 200 or contains_html(description):
            flash("选项描述不能超过 200 字或包含 HTML 标签。", "danger")
            raise ValueError()
        if title in seen:
            flash("选项标题不能重复。", "danger")
            raise ValueError()
        seen.add(title)
        options.append((title, description, image))
    return options


@bp.route("/polls")
@login_required
def index():
    polls = Poll.query.order_by(Poll.created_at.desc()).all()
    data = []
    for poll in polls:
        total = (db.session.query(db.func.count(Vote.id))
                 .filter(Vote.poll_id == poll.id).scalar() or 0)
        data.append((poll, total))
    return render_template("polls/list.html", polls=data)


@bp.route("/polls/<int:poll_id>")
@login_required
def detail(poll_id):
    poll = db.get_or_404(Poll, poll_id)
    my_vote = Vote.query.filter_by(poll_id=poll.id, user_id=current_user.id).first()
    counts = {}
    total = 0
    for option in poll.options:
        count = Vote.query.filter_by(option_id=option.id).count()
        counts[option.id] = count
        total += count
    return render_template("polls/detail.html", poll=poll, counts=counts, total=total, my_vote=my_vote)


@bp.route("/polls/<int:poll_id>/results")
@login_required
def results(poll_id):
    poll = db.get_or_404(Poll, poll_id)
    total = (db.session.query(db.func.count(Vote.id))
             .filter(Vote.poll_id == poll.id).scalar() or 0)
    options = []
    for option in poll.options:
        count = Vote.query.filter_by(option_id=option.id).count()
        options.append({
            "id": option.id,
            "title": option.title,
            "count": count,
            "percent": round(count / total * 100, 1) if total else 0,
        })
    return {"total": total, "options": options}


@bp.route("/polls/<int:poll_id>/vote", methods=["POST"])
@login_required
def vote(poll_id):
    poll = db.get_or_404(Poll, poll_id)
    if not poll.is_accepting_votes:
        flash("该投票已结束或未开放。", "warning")
        return redirect(url_for("polls.detail", poll_id=poll.id))
    if Vote.query.filter_by(poll_id=poll.id, user_id=current_user.id).first():
        flash("你已参与过这个投票，不能重复投票。", "warning")
        return redirect(url_for("polls.detail", poll_id=poll.id))
    option_id = request.form.get("option_id", type=int)
    option = db.session.get(PollOption, option_id) if option_id else None
    if not option or option.poll_id != poll.id:
        flash("请选择一个有效的选项。", "danger")
        return redirect(url_for("polls.detail", poll_id=poll.id))
    db.session.add(Vote(poll_id=poll.id, option_id=option.id, user_id=current_user.id))
    db.session.commit()
    flash("投票成功，感谢参与！", "success")
    return redirect(url_for("polls.detail", poll_id=poll.id))


# ---------- 管理 ----------

@bp.route("/admin/polls")
@admin_required
def admin_polls():
    polls = Poll.query.order_by(Poll.created_at.desc()).all()
    data = []
    for poll in polls:
        total = (db.session.query(db.func.count(Vote.id))
                 .filter(Vote.poll_id == poll.id).scalar() or 0)
        data.append((poll, total))
    return render_template("admin/polls.html", polls=data)


@bp.route("/admin/polls/create", methods=["GET", "POST"])
@admin_required
def admin_poll_create():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        ends_at = _parse_end_time(request.form.get("ends_at", ""))
        if not title or len(title) > 100 or contains_html(title):
            flash("请填写有效的投票标题（100 字以内，不含 HTML）。", "danger")
            return redirect(url_for("polls.admin_poll_create"))
        if contains_html(description):
            flash("投票说明不能包含 HTML 标签。", "danger")
            return redirect(url_for("polls.admin_poll_create"))
        try:
            options = _collect_options(prefix="new_")
        except ValueError:
            return redirect(url_for("polls.admin_poll_create"))
        if not options:
            flash("至少需要一个选项。", "danger")
            return redirect(url_for("polls.admin_poll_create"))
        poll = Poll(title=title, description=description, ends_at=ends_at,
                    created_by=current_user.id)
        db.session.add(poll)
        for order, (opt_title, opt_desc, image) in enumerate(options):
            db.session.add(PollOption(poll=poll, title=opt_title, description=opt_desc,
                                      image_path=image, sort_order=order))
        db.session.commit()
        flash("投票已创建。", "success")
        return redirect(url_for("polls.admin_polls"))
    return render_template("admin/poll_form.html", poll=None)


@bp.route("/admin/polls/<int:poll_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_poll_edit(poll_id):
    poll = db.get_or_404(Poll, poll_id)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        ends_at = _parse_end_time(request.form.get("ends_at", ""))
        if not title or len(title) > 100 or contains_html(title):
            flash("请填写有效的投票标题（100 字以内，不含 HTML）。", "danger")
            return redirect(url_for("polls.admin_poll_edit", poll_id=poll.id))
        if contains_html(description):
            flash("投票说明不能包含 HTML 标签。", "danger")
            return redirect(url_for("polls.admin_poll_edit", poll_id=poll.id))
        for option in list(poll.options):
            if request.form.get(f"delete_option_{option.id}"):
                if Vote.query.filter_by(option_id=option.id).first():
                    flash("已有投票的选项不能删除。", "warning")
                    return redirect(url_for("polls.admin_poll_edit", poll_id=poll.id))
                db.session.delete(option)
        try:
            new_options = _collect_options(prefix="new_")
        except ValueError:
            return redirect(url_for("polls.admin_poll_edit", poll_id=poll.id))
        for option in poll.options:
            option.title = request.form.get(f"option_title_{option.id}", "").strip() or option.title
            option.description = request.form.get(f"option_desc_{option.id}", "").strip()
        start = max((o.sort_order for o in poll.options), default=-1) + 1
        for offset, (opt_title, opt_desc, image) in enumerate(new_options):
            db.session.add(PollOption(poll=poll, title=opt_title, description=opt_desc,
                                      image_path=image, sort_order=start + offset))
        poll.title = title
        poll.description = description
        poll.ends_at = ends_at
        db.session.commit()
        flash("投票已更新。", "success")
        return redirect(url_for("polls.admin_polls"))
    return render_template("admin/poll_form.html", poll=poll)


@bp.route("/admin/polls/<int:poll_id>/toggle", methods=["POST"])
@admin_required
def admin_poll_toggle(poll_id):
    poll = db.get_or_404(Poll, poll_id)
    ends_at = poll.ends_at
    if ends_at is not None and ends_at.tzinfo is None:
        ends_at = ends_at.replace(tzinfo=timezone.utc)
    if not poll.is_open and ends_at is not None and ends_at <= utcnow():
        flash("该投票已到截止时间，重新开放前请先修改截止时间。", "warning")
        return redirect(url_for("polls.admin_polls"))
    poll.is_open = not poll.is_open
    db.session.commit()
    flash("投票已{}。".format("开放" if poll.is_open else "关闭"), "success")
    return redirect(url_for("polls.admin_polls"))


@bp.route("/admin/polls/<int:poll_id>/delete", methods=["POST"])
@admin_required
def admin_poll_delete(poll_id):
    poll = db.get_or_404(Poll, poll_id)
    db.session.delete(poll)
    db.session.commit()
    flash("投票已删除。", "success")
    return redirect(url_for("polls.admin_polls"))
