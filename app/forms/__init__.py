from datetime import datetime

from flask_wtf import FlaskForm
from wtforms import BooleanField, DateTimeLocalField, IntegerField, PasswordField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Optional, ValidationError

from app.models import User
from app.majors import RESOURCE_MAJOR_CHOICES, STUDENT_MAJOR_CHOICES
from app.utils.security import contains_html

POST_CATEGORIES = ["校园求助", "二手交易", "失物招领", "拼车", "学习搭子", "校园趣事", "兼职信息", "家教相关"]
GUIDE_CATEGORIES = ["报到指南", "宿舍生活", "食堂交通", "周边生活", "设备建议", "常见问题"]
ENGLISH_CATEGORIES = ["专业词汇", "Lecture听课方法", "英文实验报告", "Presentation", "学术写作", "课程经验"]
LOCATION_CATEGORIES = ["宿舍", "教学", "食堂", "交通", "生活服务"]


def no_html(_form, field):
    if contains_html(field.data):
        raise ValidationError("请勿输入 HTML 标签或脚本。")


class RegisterForm(FlaskForm):
    email = StringField("邮箱", validators=[DataRequired(), Email(), Length(max=255)])
    nickname = StringField("昵称", validators=[DataRequired(), Length(min=2, max=40), no_html])
    major = SelectField("专业", choices=STUDENT_MAJOR_CHOICES)
    enrollment_year = IntegerField("入学年份", validators=[DataRequired(), NumberRange(min=2020, max=2100)])
    invite_code = StringField("邀请码", validators=[DataRequired(), Length(max=64)])
    password = PasswordField("密码", validators=[DataRequired(), Length(min=8, max=128)])
    confirm_password = PasswordField("确认密码", validators=[DataRequired(), EqualTo("password", message="两次密码输入不一致")])
    accept_terms = BooleanField("我已阅读并同意用户协议与社区规范", validators=[DataRequired()])
    submit = SubmitField("注册")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower().strip()).first():
            raise ValidationError("该邮箱已注册。")

    def validate_enrollment_year(self, field):
        if field.data > datetime.now().year + 1:
            raise ValidationError("入学年份不正确。")


class LoginForm(FlaskForm):
    email = StringField("邮箱", validators=[DataRequired(), Email()])
    password = PasswordField("密码", validators=[DataRequired()])
    remember = BooleanField("记住我")
    submit = SubmitField("登录")


class PostForm(FlaskForm):
    title = StringField("标题", validators=[DataRequired(), Length(min=4, max=120), no_html])
    category = SelectField("分类", choices=[(item, item) for item in POST_CATEGORIES])
    content = TextAreaField("正文（支持富文本）", validators=[DataRequired(), Length(min=10, max=30000)])
    is_anonymous = BooleanField("在前台匿名发布")
    submit = SubmitField("提交审核")


class GuideForm(FlaskForm):
    title = StringField("标题", validators=[DataRequired(), Length(min=4, max=120), no_html])
    category = SelectField("分类", choices=[(item, item) for item in GUIDE_CATEGORIES])
    summary = StringField("摘要", validators=[Optional(), Length(max=240)])
    content = TextAreaField("正文（支持富文本）", validators=[DataRequired(), Length(min=10, max=30000)])
    submit = SubmitField("发布指南")


class CommentForm(FlaskForm):
    content = TextAreaField("评论", validators=[DataRequired(), Length(min=2, max=1000), no_html])
    submit = SubmitField("发表评论")


class ReportForm(FlaskForm):
    reason = TextAreaField("举报原因", validators=[DataRequired(), Length(min=5, max=1000), no_html])
    submit = SubmitField("提交举报")


class PasswordForm(FlaskForm):
    current_password = PasswordField("当前密码", validators=[DataRequired()])
    new_password = PasswordField("新密码", validators=[DataRequired(), Length(min=8, max=128)])
    confirm_password = PasswordField("确认新密码", validators=[DataRequired(), EqualTo("new_password", message="两次密码输入不一致")])
    submit = SubmitField("修改密码")


class MajorForm(FlaskForm):
    major = SelectField("专业", choices=STUDENT_MAJOR_CHOICES, validators=[DataRequired()])
    submit = SubmitField("保存专业")


class EnglishResourceForm(FlaskForm):
    title = StringField("标题", validators=[DataRequired(), Length(min=4, max=120), no_html])
    category = SelectField("分类", choices=[(item, item) for item in ENGLISH_CATEGORIES])
    content = TextAreaField("经验内容", validators=[DataRequired(), Length(min=20, max=5000), no_html])
    major = SelectField("适用专业", choices=RESOURCE_MAJOR_CHOICES)
    difficulty = SelectField("难度", choices=[("入门", "入门"), ("进阶", "进阶"), ("综合", "综合")])
    submit = SubmitField("提交审核")


class TutorProfileForm(FlaskForm):
    subjects = StringField("可辅导科目", validators=[DataRequired(), Length(max=160), no_html])
    high_school_province = StringField("高中所在省份", validators=[DataRequired(), Length(max=40), no_html])
    exam_score_description = StringField("成绩概述", validators=[DataRequired(), Length(max=200), no_html])
    strengths = TextAreaField("擅长方向", validators=[DataRequired(), Length(max=1000), no_html])
    teaching_style = TextAreaField("教学方式", validators=[DataRequired(), Length(max=1000), no_html])
    available_times = StringField("可用时间", validators=[DataRequired(), Length(max=160), no_html])
    expected_hourly_rate = IntegerField("期望时薪（元）", validators=[DataRequired(), NumberRange(min=0, max=2000)])
    submit = SubmitField("提交审核")


class TutorRequestForm(FlaskForm):
    contact_name = StringField("联系人称呼", validators=[DataRequired(), Length(max=60), no_html])
    contact_method = StringField("联系方式（仅管理员可见）", validators=[DataRequired(), Length(max=160), no_html])
    student_grade = StringField("学生年级", validators=[DataRequired(), Length(max=40), no_html])
    subjects = StringField("辅导科目", validators=[DataRequired(), Length(max=120), no_html])
    current_level = StringField("目前水平", validators=[DataRequired(), Length(max=200), no_html])
    target = StringField("学习目标", validators=[DataRequired(), Length(max=200), no_html])
    location = StringField("大致区域", validators=[DataRequired(), Length(max=120), no_html])
    budget = StringField("预算", validators=[DataRequired(), Length(max=80), no_html])
    notes = TextAreaField("补充说明", validators=[Optional(), Length(max=1000), no_html])
    submit = SubmitField("提交需求")


SURVEY_QUESTION_TYPES = [
    ("single_choice", "单选"), ("multiple_choice", "多选"), ("short_text", "短文本"),
    ("long_text", "长文本"), ("number", "数字"), ("rating", "评分"),
    ("matrix_single_choice", "矩阵单选"), ("consent", "知情同意"),
]


class SurveyForm(FlaskForm):
    title = StringField("调查标题", validators=[DataRequired(), Length(min=4, max=160), no_html])
    slug = StringField("公开链接别名", validators=[DataRequired(), Length(min=3, max=180)])
    description = TextAreaField("调查简介", validators=[DataRequired(), Length(min=10, max=3000), no_html])
    allow_anonymous = BooleanField("允许匿名参与")
    require_login = BooleanField("必须登录后填写")
    allow_edit = BooleanField("允许修改已提交答卷")
    allow_repeat = BooleanField("允许重复提交")
    use_account_profile_data = BooleanField("经说明后，统计中使用登录用户已有的专业和入学年份")
    start_at = DateTimeLocalField("开始时间", validators=[Optional()], format="%Y-%m-%dT%H:%M")
    end_at = DateTimeLocalField("截止时间", validators=[Optional()], format="%Y-%m-%dT%H:%M")
    estimated_minutes = IntegerField("预计用时（分钟）", validators=[DataRequired(), NumberRange(min=1, max=60)])
    success_message = TextAreaField("提交成功提示", validators=[DataRequired(), Length(max=500), no_html])
    submit = SubmitField("保存调查")


class SurveyQuestionForm(FlaskForm):
    title = StringField("问题标题", validators=[DataRequired(), Length(min=2, max=300), no_html])
    description = StringField("补充说明", validators=[Optional(), Length(max=500), no_html])
    question_type = SelectField("题型", choices=SURVEY_QUESTION_TYPES)
    is_required = BooleanField("设为必填")
    is_contact_info = BooleanField("这是联系方式类题目（仅管理员查看，不进入普通图表和匿名汇总）")
    options_text = TextAreaField("选项（每行一个）", validators=[Optional(), Length(max=5000), no_html])
    matrix_rows_text = TextAreaField("矩阵行（每行一个）", validators=[Optional(), Length(max=3000), no_html])
    min_choices = IntegerField("最少选择数", validators=[Optional(), NumberRange(min=0, max=100)])
    max_choices = IntegerField("最多选择数", validators=[Optional(), NumberRange(min=1, max=100)])
    min_length = IntegerField("最少文字数", validators=[Optional(), NumberRange(min=0, max=10000)])
    max_length = IntegerField("最多文字数", validators=[Optional(), NumberRange(min=1, max=10000)])
    min_value = IntegerField("最小数值/评分", validators=[Optional()])
    max_value = IntegerField("最大数值/评分", validators=[Optional()])
    add_other = BooleanField("添加“其他，请填写”选项")
    submit = SubmitField("保存问题")

class AdminCreateUserForm(FlaskForm):
    email = StringField("邮箱", validators=[DataRequired(), Email(), Length(max=255)])
    nickname = StringField("昵称", validators=[DataRequired(), Length(min=2, max=40), no_html])
    role = SelectField("角色", choices=[("student", "普通用户（学生）"), ("admin", "管理员")], default="student")
    password = PasswordField("初始密码", validators=[DataRequired(), Length(min=8, max=128)])
    submit = SubmitField("创建用户")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower().strip()).first():
            raise ValidationError("该邮箱已注册。")

