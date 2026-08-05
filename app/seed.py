import json
import os
import re
from datetime import timedelta

import click
from flask import current_app

from .extensions import db
from .majors import (GENERAL, INTELLIGENT_MANUFACTURING_ENGINEERING,
                     NEW_ENERGY_SCIENCE_ENGINEERING, OTHER, ROBOTICS_ENGINEERING)
from .models import (CampusLocation, EnglishResource, Guide, InviteCode, Post, Survey, SurveyOption,
                     SurveyQuestion, TutorProfile, TutorRequest, User, utcnow)


def register_commands(app):
    @app.cli.command("seed")
    @click.option("--reset", is_flag=True, help="清空现有数据后重建演示数据。")
    def seed_command(reset):
        """导入本地演示账号和中文演示数据。"""
        if reset:
            db.drop_all()
        db.create_all()
        if User.query.first():
            admin = User.query.filter_by(role="admin").first()
            created = ensure_demo_survey(admin) if admin else False
            update_tutoring_demo_visibility()
            db.session.commit()
            click.echo("首份演示调查已创建。" if created else "数据库已有数据和演示调查；如需重建，请使用 flask seed --reset。")
            return

        admin = make_user("管理员", "admin@campus-hub.example.com", OTHER, 2026, "admin", "verified")
        students = [
            make_user("小苏", "student1@campus-hub.example.com", ROBOTICS_ENGINEERING, 2026, "student", "verified"),
            make_user("能量同学", "student2@campus-hub.example.com", NEW_ENERGY_SCIENCE_ENGINEERING, 2026, "student", "verified"),
            make_user("齿轮猫", "student3@campus-hub.example.com", INTELLIGENT_MANUFACTURING_ENGINEERING, 2026, "student", "verified"),
            make_user("湖畔新生", "student4@campus-hub.example.com", NEW_ENERGY_SCIENCE_ENGINEERING, 2026, "student", "verified"),
            make_user("等风来", "student5@campus-hub.example.com", ROBOTICS_ENGINEERING, 2026, "student", "pending"),
        ]
        db.session.add_all([admin, *students, InviteCode(code="SUZHOU2026", max_uses=300)])
        db.session.flush()

        post_rows = [
            ("新生想找一起熟悉校区的同学", "校园求助", "演示信息：周末想结伴熟悉教学、生活服务和交通区域，欢迎在评论区交流。"),
            ("智能制造课程学习搭子", "学习搭子", "演示信息：希望每周安排一次复盘，整理全英文课堂中的专业词汇。"),
            ("闲置台灯转让", "二手交易", "演示信息：可调亮度台灯，使用正常。线下交易请当面确认物品情况。"),
            ("食堂附近捡到水杯", "失物招领", "演示信息：深色保温杯，请失主描述外观细节后认领。"),
            ("周五傍晚拼车到市区", "拼车", "演示信息：仅用于测试分类功能，请自行核实行程并注意出行安全。"),
            ("新能源专业词汇互助整理", "学习搭子", "演示信息：一起补充储能、电化学相关的中英文术语。"),
            ("分享第一次英文 Presentation 的准备方法", "校园趣事", "演示信息：先写清三段结构，再控制每页只讲一个重点，排练时计时。"),
            ("寻找高数答疑伙伴", "校园求助", "演示信息：希望互相讲题，不涉及代写作业或考试答案。"),
            ("周末校园活动志愿者招募", "兼职信息", "演示信息：该信息仅用于展示，请核验真实组织方后再参与。"),
            ("学生家教资料如何登记", "家教相关", "演示信息：已认证学生可在用户中心提交资料，审核后展示，联系方式不会公开。"),
        ]
        for index, row in enumerate(post_rows):
            post_status = "approved"
            if row[0] == "学生家教资料如何登记" and not current_app.config["FEATURE_TUTORING_PUBLIC"]:
                post_status = "hidden"
            db.session.add(Post(author_id=students[index % 4].id, title=row[0], category=row[1], content=row[2],
                                status=post_status, is_anonymous=index in {0, 7}, view_count=12 + index * 7))

        guides = [
            ("新生到校前的轻量准备清单", "arrival-checklist", "报到指南", "整理证件、电子设备和日常用品，不必一次买齐。", "演示信息：先按照官方通知核对材料，再准备常用充电设备、基础衣物和个人药品。具体报到材料与时间必须以学校官方通知为准。"),
            ("宿舍收纳与共同生活建议", "dorm-life", "宿舍生活", "从少量必需品开始，并尽早和室友约定公共空间规则。", "演示信息：行李先轻量化；入住后再按实际空间添置。共同讨论作息、卫生和公共物品，尊重每个人的边界。"),
            ("食堂与通勤的第一周", "food-transport", "食堂交通", "用一周时间建立自己的用餐与出行节奏。", "演示信息：错峰体验不同用餐区域，出行前使用可靠地图核对线路。校内交通安排以现场和官方通知为准。"),
            ("全英文课堂设备怎么选", "study-devices", "设备建议", "优先保证记笔记、查词和展示兼容性。", "演示信息：无需盲目追求高配置，确保续航、常见文档格式和投屏接口可用即可。实验课程设备要求请询问任课教师。"),
            ("邀请码注册后可以使用哪些功能？", "verification-faq", "常见问题", "使用有效邀请码注册后即可使用校园社区功能。", "演示信息：有效邀请码用于控制社区加入范围。注册成功后可以发布信息、评论、收藏、举报并参与调查；管理员仍可处理违规账号和泄露的邀请码。"),
        ]
        db.session.add_all([Guide(title=t, slug=s, category=c, summary=m, content=b) for t, s, c, m, b in guides])

        english_rows = [
            ("机器人运动学常用词汇", "专业词汇", ROBOTICS_ENGINEERING, "入门", "演示信息：整理 joint、link、end-effector、forward kinematics 等常用概念，并结合图示理解。"),
            ("智能制造流程词汇速记", "专业词汇", INTELLIGENT_MANUFACTURING_ENGINEERING, "入门", "演示信息：把 production line、quality control、digital twin 放进实际流程记忆。"),
            ("新能源课堂常见单位表达", "专业词汇", NEW_ENERGY_SCIENCE_ENGINEERING, "入门", "演示信息：听课时同步记录 quantity、unit 和 measurement condition，避免只抄数值。"),
            ("Lecture 听漏了怎么办", "Lecture听课方法", GENERAL, "入门", "演示信息：先标记时间点和关键词，课后用讲义补结构，再向同学或教师确认。"),
            ("英文实验报告的结果段", "英文实验报告", GENERAL, "进阶", "演示信息：Results 先客观描述数据，Discussion 再解释原因，不混写结论与过程。"),
            ("三分钟 Presentation 结构", "Presentation", GENERAL, "入门", "演示信息：用问题、证据、结论三段式，每页只保留一个核心信息。"),
            ("学术写作中的谨慎表达", "学术写作", GENERAL, "进阶", "演示信息：用 may、suggest、indicate 等表达证据强度，避免过度断言。"),
            ("读新能源论文的图表顺序", "课程经验", NEW_ENERGY_SCIENCE_ENGINEERING, "进阶", "演示信息：先读摘要和结论，再看图表标题与变量，最后回到方法核对条件。"),
            ("智能制造小组讨论分工", "课程经验", INTELLIGENT_MANUFACTURING_ENGINEERING, "综合", "演示信息：提前约定术语、交付格式和汇报接口，减少最后合并时的冲突。"),
            ("问答环节的英文缓冲句", "Presentation", GENERAL, "入门", "演示信息：先复述问题确认理解，再给结论和一条理由；不确定时明确说明范围。"),
        ]
        for title, category, major_code, difficulty, content in english_rows:
            resource = EnglishResource(title=title, category=category, difficulty=difficulty, content=content)
            resource.set_major(major_code)
            db.session.add(resource)

        location_rows = [
            ("学生生活区", "宿舍", "演示地点：入住与生活服务集中区域，具体楼栋以现场指引为准。"),
            ("本科教学区域", "教学", "演示地点：日常课堂可能集中的区域，课程地点请查看正式课表。"),
            ("公共自习空间", "教学", "演示地点：可用于个人复习与小组讨论，开放时间以现场为准。"),
            ("学生用餐区域", "食堂", "演示地点：提供日常餐饮服务，窗口和时间可能调整。"),
            ("校园出入口", "交通", "演示地点：进出校区与接驳参考点，不表示精确位置。"),
            ("快递服务点", "生活服务", "演示地点：收取快递的参考区域，实际运营信息以通知为准。"),
            ("基础医疗服务点", "生活服务", "演示地点：出现紧急情况请优先联系正规急救服务。"),
            ("校园活动空间", "生活服务", "演示地点：学生交流与活动的参考区域。"),
        ]
        db.session.add_all([CampusLocation(name=n, category=c, description=d) for n, c, d in location_rows])

        for index, student in enumerate(students[:5]):
            db.session.add(TutorProfile(user_id=student.id, subjects=["数学、物理", "英语、数学", "物理、编程", "化学、数学", "英语"][index],
                high_school_province=["江苏", "浙江", "山东", "安徽", "湖北"][index], exam_score_description="演示信息：相关科目基础扎实，可提供学习方法介绍",
                strengths="演示信息：重视概念理解和错题复盘，不提供作业代写。", teaching_style="先诊断薄弱点，再通过例题和练习反馈调整。",
                available_times="周末或工作日晚间，具体由管理员协调", expected_hourly_rate=80 + index * 10, status="approved"))
        db.session.add_all([
            TutorRequest(contact_name="王家长", contact_method="演示联系方式：仅管理员可见-001", student_grade="初二", subjects="数学", current_level="基础题较稳定", target="建立几何解题思路", location="苏州校区周边", budget="80-120元/小时", notes="演示信息"),
            TutorRequest(contact_name="李家长", contact_method="演示联系方式：仅管理员可见-002", student_grade="高一", subjects="物理", current_level="概念理解不牢", target="跟上课程进度", location="线上", budget="100元/小时左右", notes="演示信息"),
            TutorRequest(contact_name="陈家长", contact_method="演示联系方式：仅管理员可见-003", student_grade="小学六年级", subjects="英语", current_level="阅读词汇量不足", target="培养阅读习惯", location="苏州校区周边", budget="可商议", notes="演示信息"),
        ])
        ensure_demo_survey(admin)
        db.session.commit()
        click.echo("本地演示数据已创建。演示账号说明见 README。")

    @app.cli.command("create-admin")
    @click.option("--email", prompt="管理员邮箱")
    @click.option("--nickname", prompt="管理员昵称")
    @click.password_option(prompt="管理员密码", confirmation_prompt=True)
    def create_admin_command(email, nickname, password):
        """为新部署创建首个管理员，不在日志中输出密码。"""
        email = email.lower().strip()
        nickname = nickname.strip()
        if "@" not in email or len(nickname) < 2 or len(password) < 12:
            raise click.ClickException("请输入有效邮箱、至少2字符昵称和至少12字符密码。")
        if User.query.filter_by(email=email).first():
            raise click.ClickException("该邮箱已存在。")
        user = User(nickname=nickname, email=email, enrollment_year=2026,
                    role="admin", verification_status="verified")
        user.set_major(OTHER)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo("管理员账号已创建。")

    @app.cli.command("bootstrap-admin")
    def bootstrap_admin_command():
        """从环境变量幂等创建生产环境的首个管理员。"""
        existing_admin = User.query.filter_by(role="admin").first()
        if existing_admin:
            click.echo("管理员已存在，无需重复创建。")
            return

        email = os.getenv("ADMIN_EMAIL", "").lower().strip()
        nickname = os.getenv("ADMIN_NICKNAME", "").strip()
        password = os.getenv("ADMIN_PASSWORD", "")
        missing = [name for name, value in (
            ("ADMIN_EMAIL", email),
            ("ADMIN_NICKNAME", nickname),
            ("ADMIN_PASSWORD", password),
        ) if not value]
        if missing:
            raise click.ClickException("缺少生产管理员环境变量：" + "、".join(missing))
        if "@" not in email or len(nickname) < 2 or len(password) < 12:
            raise click.ClickException("ADMIN_EMAIL 必须有效，昵称至少2字符，密码至少12字符。")
        if User.query.filter_by(email=email).first():
            raise click.ClickException("ADMIN_EMAIL 已被非管理员账号占用，请更换。")

        user = User(
            nickname=nickname,
            email=email,
            enrollment_year=2026,
            role="admin",
            verification_status="verified",
        )
        user.set_major(OTHER)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo("生产管理员已创建。")

    @app.cli.command("reset-admin-password")
    def reset_admin_password_command():
        """使用一次性环境变量安全重置指定生产管理员密码。"""
        email = os.getenv("ADMIN_EMAIL", "").lower().strip()
        password = os.getenv("ADMIN_RESET_PASSWORD", "")
        if not email:
            raise click.ClickException("缺少 ADMIN_EMAIL。")
        if not password:
            raise click.ClickException("缺少一次性环境变量 ADMIN_RESET_PASSWORD。")
        if len(password) < 12:
            raise click.ClickException("ADMIN_RESET_PASSWORD 至少需要 12 个字符。")

        user = User.query.filter_by(email=email, role="admin").first()
        if not user:
            raise click.ClickException("未找到与 ADMIN_EMAIL 匹配的管理员账号。")

        user.set_password(password)
        db.session.commit()
        click.echo("生产管理员密码已安全重置。")

    @app.cli.command("bootstrap-invite")
    def bootstrap_invite_command():
        """从环境变量幂等创建一次性配置的限量邀请码。"""
        valid_count = sum(1 for invite in InviteCode.query.all() if invite.usable)
        click.echo(f"当前有效邀请码数量：{valid_count}。")
        code = os.getenv("INVITE_BOOTSTRAP_CODE", "").strip()
        if not code:
            click.echo("未配置一次性邀请码，无需创建。")
            return
        try:
            max_uses = int(os.getenv("INVITE_BOOTSTRAP_MAX_USES", "20"))
            valid_days = int(os.getenv("INVITE_BOOTSTRAP_DAYS", "30"))
        except ValueError as error:
            raise click.ClickException("邀请码使用次数和有效天数必须是整数。") from error
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", code):
            raise click.ClickException("邀请码只能包含字母、数字、下划线或短横线，长度为 8 到 64。")
        if not 1 <= max_uses <= 1000 or not 1 <= valid_days <= 365:
            raise click.ClickException("邀请码使用次数必须为 1 到 1000，有效天数必须为 1 到 365。")
        if InviteCode.query.filter_by(code=code).first():
            click.echo("一次性邀请码已存在，无需重复创建。")
            return
        db.session.add(InviteCode(
            code=code,
            max_uses=max_uses,
            expires_at=utcnow() + timedelta(days=valid_days),
            is_active=True,
        ))
        db.session.commit()
        click.echo("一次性邀请码已创建，请移除对应环境变量。")


def make_user(nickname, email, major_code, year, role, status):
    user = User(nickname=nickname, email=email, enrollment_year=year, role=role, verification_status=status)
    user.set_major(major_code)
    user.set_password("Admin123!" if role == "admin" else "Student123!")
    return user


def ensure_demo_survey(admin):
    if Survey.query.filter_by(slug="freshman-needs").first():
        return False
    survey = Survey(
        title="东南大学苏州校区首届本科生需求调查",
        slug="freshman-needs",
        description="我们是苏州校区首届本科生，目前很多学习和校园生活信息仍在逐步完善。本调查希望了解大家真正关心的问题，后续将整理成新生指南、校园地图和学生互助内容。预计用时2分钟。",
        status="published",
        allow_anonymous=True,
        require_login=False,
        estimated_minutes=2,
        success_message="感谢你的参与。调查结果只用于整理首届本科生的真实需求，后续内容会持续更新。",
        created_by=admin.id,
    )
    db.session.add(survey)
    db.session.flush()
    definitions = [
        ("你的专业方向是什么？", "single_choice", True, "", [
            (ROBOTICS_ENGINEERING, "机器人工程"),
            (INTELLIGENT_MANUFACTURING_ENGINEERING, "智能制造工程"),
            (NEW_ENERGY_SCIENCE_ENGINEERING, "新能源科学与工程"),
            (OTHER, "其他"),
        ], {}),
        ("你目前最想提前了解哪些信息？", "multiple_choice", True, "", ["宿舍条件", "食堂与校园生活", "校区地图和报到路线", "周边交通和生活设施", "全英文教学方式", "专业课程设置", "电脑和平板设备建议", "英语学习准备", "社团、竞赛和科研", "兼职与校园实践", "其他"], {"max_choices": 5}),
        ("你对全英文教学的担心程度是多少？", "rating", True, "1表示完全不担心，5表示非常担心", [], {"min_value": 1, "max_value": 5}),
        ("关于全英课堂，你最希望平台提供哪些帮助？", "multiple_choice", False, "", ["专业英语词汇库", "Lecture听课方法", "英文课堂常用表达", "英文实验报告写作", "Presentation训练", "课程笔记分享", "英语学习搭子", "学长学姐课程经验", "暂时不需要", "其他"], {}),
        ("你最希望校园互助平台提供哪些功能？", "multiple_choice", False, "", ["新生指南", "校园地图", "信息广场", "学习资料", "学习搭子", "二手交易", "失物招领", "拼车和代取快递", "活动与比赛组队", "校园趣事分享", "其他"], {}),
        ("你是否愿意在开学后分享校园经验？", "single_choice", False, "", ["愿意", "看具体内容", "暂时不愿意"], {}),
        ("你愿意参与哪些平台共建工作？", "multiple_choice", False, "", ["拍摄校园照片", "整理新生攻略", "分享学习资料", "分享英语学习经验", "网页开发", "UI设计", "内容审核", "社群运营", "暂时不参与"], {}),
        ("你认为还有什么问题值得提前关注？", "long_text", False, "", [], {"max_length": 500}),
        ("是否愿意参加后续内测？", "single_choice", False, "", ["愿意", "暂时不愿意"], {}),
        ("内测联系方式", "short_text", False, "只有选择愿意参加内测时填写。可填写微信号或邮箱，仅用于邀请内测，不公开展示。", [], {"max_length": 120}),
    ]
    for order, (title, qtype, required, description, options, rules) in enumerate(definitions, 1):
        question = SurveyQuestion(survey_id=survey.id, title=title, question_type=qtype, is_required=required,
                                  description=description, sort_order=order,
                                  is_contact_info=title == "内测联系方式",
                                  validation_rules_json=json.dumps(rules, ensure_ascii=False))
        db.session.add(question)
        db.session.flush()
        for option_order, option in enumerate(options, 1):
            value, label = option if isinstance(option, tuple) else (
                "other" if option == "其他" else option,
                option,
            )
            db.session.add(SurveyOption(question_id=question.id, label=label, value=value, sort_order=option_order))
    return True


def update_tutoring_demo_visibility():
    demo_post = Post.query.filter_by(title="学生家教资料如何登记").first()
    if demo_post:
        demo_post.status = "approved" if current_app.config["FEATURE_TUTORING_PUBLIC"] else "hidden"
