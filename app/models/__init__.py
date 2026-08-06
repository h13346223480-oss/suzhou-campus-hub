from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.majors import (GENERAL, PENDING_CONFIRMATION, RESOURCE_MAJOR_CODES, USER_MAJOR_CODES,
                        major_label, normalize_resource_major, normalize_user_major)


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __table_args__ = (
        db.CheckConstraint(
            "major_code IN ('robotics_engineering', 'intelligent_manufacturing_engineering', "
            "'new_energy_science_engineering', 'other', 'pending_confirmation')",
            name="ck_user_major_code",
        ),
    )
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(40), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    major = db.Column(db.String(80), nullable=False)
    major_code = db.Column(db.String(50), nullable=False, default=PENDING_CONFIRMATION, index=True)
    enrollment_year = db.Column(db.Integer, nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    verification_status = db.Column(db.String(20), nullable=False, default="pending")
    student_id_photo = db.Column(db.String(255), nullable=True)
    joined_via_invite = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    last_login_at = db.Column(db.DateTime(timezone=True))
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    posts = db.relationship("Post", back_populates="author", lazy="dynamic")
    tutor_profile = db.relationship("TutorProfile", back_populates="user", uselist=False)
    invite_redemption = db.relationship("InviteRedemption", back_populates="user", uselist=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def set_major(self, code):
        normalized = normalize_user_major(code)
        if normalized not in USER_MAJOR_CODES:
            raise ValueError("无效专业代码")
        self.major_code = normalized
        self.major = major_label(normalized)

    @property
    def major_display(self):
        return "平台维护" if self.is_admin else major_label(self.major_code)

    @property
    def requires_major_confirmation(self):
        return not self.is_admin and self.major_code == PENDING_CONFIRMATION

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_verified(self):
        return self.verification_status == "verified" or self.is_admin


class InviteCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False)
    max_uses = db.Column(db.Integer, nullable=False, default=1)
    used_count = db.Column(db.Integer, nullable=False, default=0)
    expires_at = db.Column(db.DateTime(timezone=True))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    redemptions = db.relationship("InviteRedemption", back_populates="invite", lazy="dynamic")

    @property
    def usable(self):
        expires_at = self.expires_at
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        expiry_ok = not expires_at or expires_at > utcnow()
        return self.is_active and self.used_count < self.max_uses and expiry_ok


class InviteRedemption(db.Model):
    __table_args__ = (db.UniqueConstraint("user_id", name="uq_invite_redemption_user_id"),)

    id = db.Column(db.Integer, primary_key=True)
    invite_code_id = db.Column(db.Integer, db.ForeignKey("invite_code.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    redeemed_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    invite = db.relationship("InviteCode", back_populates="redemptions")
    user = db.relationship("User", back_populates="invite_redemption")




class PostCategory(db.Model):
    """信息广场帖子分类：内置分类为代码常量，自定义分类存于此表。"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), unique=True, nullable=False, index=True)
    is_custom = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)



class Poll(db.Model):
    """投票主题：管理员创建，登录学生参与投票。"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=False, default="")
    ends_at = db.Column(db.DateTime(timezone=True), nullable=True)
    is_open = db.Column(db.Boolean, nullable=False, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    options = db.relationship(
        "PollOption", back_populates="poll", cascade="all, delete-orphan",
        order_by="PollOption.sort_order")
    votes = db.relationship("Vote", back_populates="poll", cascade="all, delete-orphan")

    @property
    def is_accepting_votes(self):
        if not self.is_open:
            return False
        if self.ends_at is not None:
            ends_at = self.ends_at
            if ends_at.tzinfo is None:
                ends_at = ends_at.replace(tzinfo=timezone.utc)
            if ends_at <= utcnow():
                return False
        return True


class PollOption(db.Model):
    """投票选项：可附图片或文本描述。"""
    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey("poll.id"), nullable=False, index=True)
    title = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(200), nullable=False, default="")
    image_path = db.Column(db.String(255), nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    poll = db.relationship("Poll", back_populates="options")
    votes = db.relationship("Vote", back_populates="option")


class Vote(db.Model):
    """投票记录：每个投票每个用户限一票。"""
    __table_args__ = (db.UniqueConstraint("poll_id", "user_id", name="uq_vote_poll_user"),)
    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey("poll.id"), nullable=False, index=True)
    option_id = db.Column(db.Integer, db.ForeignKey("poll_option.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    poll = db.relationship("Poll", back_populates="votes")
    option = db.relationship("PollOption", back_populates="votes")

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(30), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    is_anonymous = db.Column(db.Boolean, nullable=False, default=False)
    view_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    author = db.relationship("User", back_populates="posts")
    comments = db.relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    bookmarks = db.relationship("Bookmark", back_populates="post", cascade="all, delete-orphan")


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="approved")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    post = db.relationship("Post", back_populates="comments")
    author = db.relationship("User")


class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    target_type = db.Column(db.String(20), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    reporter = db.relationship("User")


class Guide(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(140), unique=True, nullable=False, index=True)
    summary = db.Column(db.String(240), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(30), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="published")
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class CampusLocation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    category = db.Column(db.String(30), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    image_path = db.Column(db.String(255))
    status = db.Column(db.String(20), nullable=False, default="published")


class EnglishResource(db.Model):
    __table_args__ = (
        db.CheckConstraint(
            "major_code IN ('general', 'robotics_engineering', "
            "'intelligent_manufacturing_engineering', 'new_energy_science_engineering', 'other')",
            name="ck_english_resource_major_code",
        ),
    )
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(40), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    major = db.Column(db.String(80), nullable=False)
    major_code = db.Column(db.String(50), nullable=False, default=GENERAL, index=True)
    difficulty = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="published")
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    def set_major(self, code):
        normalized = normalize_resource_major(code)
        if normalized not in RESOURCE_MAJOR_CODES:
            raise ValueError("无效适用专业代码")
        self.major_code = normalized
        self.major = major_label(normalized)

    @property
    def major_display(self):
        return major_label(self.major_code)


class TutorProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    subjects = db.Column(db.String(160), nullable=False)
    high_school_province = db.Column(db.String(40), nullable=False)
    exam_score_description = db.Column(db.String(200), nullable=False)
    strengths = db.Column(db.Text, nullable=False)
    teaching_style = db.Column(db.Text, nullable=False)
    available_times = db.Column(db.String(160), nullable=False)
    expected_hourly_rate = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    user = db.relationship("User", back_populates="tutor_profile")


class TutorRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contact_name = db.Column(db.String(60), nullable=False)
    contact_method = db.Column(db.String(160), nullable=False)
    student_grade = db.Column(db.String(40), nullable=False)
    subjects = db.Column(db.String(120), nullable=False)
    current_level = db.Column(db.String(200), nullable=False)
    target = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(120), nullable=False)
    budget = db.Column(db.String(80), nullable=False)
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default="pending")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)


class Bookmark(db.Model):
    __table_args__ = (db.UniqueConstraint("user_id", "post_id", name="uq_bookmark_user_post"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    user = db.relationship("User")
    post = db.relationship("Post", back_populates="bookmarks")


class SiteStat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    total_visits = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class AiChatUsage(db.Model):
    """AI 助手调用用量：仅记录 token 用量与费用，不保存对话内容（最小化收集个人信息）。"""
    __table_args__ = (db.Index("ix_ai_chat_usage_created", "created_at"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    model = db.Column(db.String(60), nullable=False)
    prompt_tokens = db.Column(db.Integer, nullable=False, default=0)
    completion_tokens = db.Column(db.Integer, nullable=False, default=0)
    total_tokens = db.Column(db.Integer, nullable=False, default=0)
    cost = db.Column(db.Numeric(12, 6), nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    user = db.relationship("User")


class AiKnowledge(db.Model):
    """AI 助手知识库条目：管理员维护的问答/事实，仅用于给模型提供上下文，不含用户个人信息。"""
    __table_args__ = (db.Index("ix_ai_knowledge_updated", "updated_at"),)
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    content = db.Column(db.Text, nullable=False)
    keywords = db.Column(db.String(255), nullable=False, default="")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class Survey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="draft", index=True)
    allow_anonymous = db.Column(db.Boolean, nullable=False, default=True)
    require_login = db.Column(db.Boolean, nullable=False, default=False)
    allow_edit = db.Column(db.Boolean, nullable=False, default=False)
    allow_repeat = db.Column(db.Boolean, nullable=False, default=False)
    use_account_profile_data = db.Column(db.Boolean, nullable=False, default=False)
    start_at = db.Column(db.DateTime(timezone=True))
    end_at = db.Column(db.DateTime(timezone=True))
    estimated_minutes = db.Column(db.Integer, nullable=False, default=2)
    success_message = db.Column(db.String(500), nullable=False, default="感谢你的参与。")
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    creator = db.relationship("User", foreign_keys=[created_by])
    questions = db.relationship("SurveyQuestion", back_populates="survey", cascade="all, delete-orphan",
                                order_by="SurveyQuestion.sort_order")
    responses = db.relationship("SurveyResponse", back_populates="survey", cascade="all, delete-orphan")
    access_logs = db.relationship("SurveyAccessLog", back_populates="survey", cascade="all, delete-orphan")


class SurveyQuestion(db.Model):
    __table_args__ = (db.Index("idx_survey_question_order", "survey_id", "sort_order"),)
    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey("survey.id"), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.String(500))
    question_type = db.Column(db.String(40), nullable=False)
    is_required = db.Column(db.Boolean, nullable=False, default=False)
    is_contact_info = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    validation_rules_json = db.Column(db.Text, nullable=False, default="{}")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    survey = db.relationship("Survey", back_populates="questions")
    options = db.relationship("SurveyOption", back_populates="question", cascade="all, delete-orphan",
                              order_by="SurveyOption.sort_order")
    answers = db.relationship("SurveyAnswer", back_populates="question", cascade="all, delete-orphan")


class SurveyOption(db.Model):
    __table_args__ = (db.Index("idx_survey_option_order", "question_id", "sort_order"),)
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("survey_question.id"), nullable=False)
    label = db.Column(db.String(200), nullable=False)
    value = db.Column(db.String(200), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    question = db.relationship("SurveyQuestion", back_populates="options")


class SurveyResponse(db.Model):
    __table_args__ = (
        db.Index("idx_survey_response_submitted", "survey_id", "submitted_at"),
        db.Index("idx_survey_response_user", "survey_id", "user_id"),
    )
    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey("survey.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    anonymous_token = db.Column(db.String(64), index=True)
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    source = db.Column(db.String(80), nullable=False, default="direct")
    device_type = db.Column(db.String(20), nullable=False, default="unknown")
    completion_seconds = db.Column(db.Integer)
    is_valid = db.Column(db.Boolean, nullable=False, default=True)
    validity_status = db.Column(db.String(20), nullable=False, default="valid", index=True)

    survey = db.relationship("Survey", back_populates="responses")
    user = db.relationship("User")
    answers = db.relationship("SurveyAnswer", back_populates="response", cascade="all, delete-orphan")
    audit_logs = db.relationship("SurveyResponseAudit", back_populates="response", passive_deletes=True)


class SurveyAnswer(db.Model):
    __table_args__ = (db.UniqueConstraint("response_id", "question_id", name="uq_survey_answer_response_question"),)
    id = db.Column(db.Integer, primary_key=True)
    response_id = db.Column(db.Integer, db.ForeignKey("survey_response.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("survey_question.id"), nullable=False)
    answer_text = db.Column(db.Text)
    answer_json = db.Column(db.Text)

    response = db.relationship("SurveyResponse", back_populates="answers")
    question = db.relationship("SurveyQuestion", back_populates="answers")
    tags = db.relationship("SurveyAnswerTag", back_populates="answer", cascade="all, delete-orphan",
                           order_by="SurveyAnswerTag.tag")


class SurveyAnswerTag(db.Model):
    __table_args__ = (
        db.UniqueConstraint("answer_id", "tag", name="uq_survey_answer_tag"),
        db.Index("idx_survey_answer_tag_value", "tag"),
    )
    id = db.Column(db.Integer, primary_key=True)
    answer_id = db.Column(db.Integer, db.ForeignKey("survey_answer.id"), nullable=False)
    tag = db.Column(db.String(40), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    answer = db.relationship("SurveyAnswer", back_populates="tags")
    creator = db.relationship("User", foreign_keys=[created_by])


class SurveyResponseAudit(db.Model):
    __table_args__ = (db.Index("idx_survey_response_audit_created", "survey_id", "created_at"),)
    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey("survey.id"), nullable=False)
    response_id = db.Column(db.Integer, db.ForeignKey("survey_response.id", ondelete="SET NULL"))
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    action = db.Column(db.String(30), nullable=False)
    previous_status = db.Column(db.String(20))
    new_status = db.Column(db.String(20))
    details_json = db.Column(db.Text, nullable=False, default="{}")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    response = db.relationship("SurveyResponse", back_populates="audit_logs")
    actor = db.relationship("User", foreign_keys=[actor_id])


class SurveyDecisionOverride(db.Model):
    __table_args__ = (
        db.UniqueConstraint("survey_id", "question_id", "option_value", name="uq_survey_decision_override"),
    )
    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey("survey.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("survey_question.id"), nullable=False)
    option_value = db.Column(db.String(200), nullable=False)
    priority = db.Column(db.String(20), nullable=False)
    updated_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    survey = db.relationship("Survey")
    question = db.relationship("SurveyQuestion")
    editor = db.relationship("User", foreign_keys=[updated_by])


class SurveyAccessLog(db.Model):
    __table_args__ = (db.Index("idx_survey_access_visited", "survey_id", "visited_at"),)
    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey("survey.id"), nullable=False)
    anonymous_token = db.Column(db.String(64))
    source = db.Column(db.String(80), nullable=False, default="direct")
    visited_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    survey = db.relationship("Survey", back_populates="access_logs")
