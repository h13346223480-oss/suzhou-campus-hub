import json
from collections import Counter
from datetime import datetime, timezone

from app.utils.security import contains_html

CHOICE_TYPES = {"single_choice", "multiple_choice", "matrix_single_choice"}
TEXT_TYPES = {"short_text", "long_text"}


def rules_for(question):
    try:
        data = json.loads(question.validation_rules_json or "{}")
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}


def build_rules(form):
    rules = {}
    for name in ["min_choices", "max_choices", "min_length", "max_length", "min_value", "max_value"]:
        value = getattr(form, name).data
        if value is not None:
            rules[name] = value
    rows = [line.strip() for line in (form.matrix_rows_text.data or "").splitlines() if line.strip()]
    if rows:
        rules["rows"] = rows
    if form.add_other.data:
        rules["allow_other"] = True
    return rules


def validate_question_definition(form):
    errors = []
    qtype = form.question_type.data
    options = [line.strip() for line in (form.options_text.data or "").splitlines() if line.strip()]
    if qtype in CHOICE_TYPES and len(options) < 2:
        errors.append("选择题和矩阵题至少需要两个选项。")
    if qtype == "matrix_single_choice":
        rows = [line.strip() for line in (form.matrix_rows_text.data or "").splitlines() if line.strip()]
        if not rows:
            errors.append("矩阵单选题至少需要一行。")
    if form.min_choices.data is not None and form.max_choices.data is not None:
        if form.min_choices.data > form.max_choices.data:
            errors.append("最少选择数不能大于最多选择数。")
    if form.min_value.data is not None and form.max_value.data is not None:
        if form.min_value.data >= form.max_value.data:
            errors.append("最小值必须小于最大值。")
    if qtype == "rating" and (form.min_value.data is None or form.max_value.data is None):
        errors.append("评分题必须设置最小和最大评分。")
    return errors, options


def validate_submission(survey, form_data):
    answers = []
    errors = {}
    for question in survey.questions:
        answer, error = validate_answer(question, form_data)
        if error:
            errors[question.id] = error
        elif answer is not None:
            answers.append((question, answer[0], answer[1]))
    return answers, errors


def validate_answer(question, form_data):
    key = f"q_{question.id}"
    rules = rules_for(question)
    allowed = {option.value for option in question.options}
    qtype = question.question_type

    if qtype == "multiple_choice":
        values = [value for value in form_data.getlist(key) if value]
        if question.is_required and not values:
            return None, "此题为必填题。"
        if any(value not in allowed for value in values):
            return None, "包含无效选项。"
        minimum, maximum = rules.get("min_choices"), rules.get("max_choices")
        if minimum is not None and len(values) < minimum:
            return None, f"请至少选择 {minimum} 项。"
        if maximum is not None and len(values) > maximum:
            return None, f"最多选择 {maximum} 项。"
        other = clean_other(form_data.get(f"{key}_other")) if "other" in values else ""
        if "other" in values and not other:
            return None, "选择“其他”后请填写具体内容。"
        if other is None:
            return None, "其他内容不能包含 HTML。"
        if not values:
            return None, None
        return (None, json.dumps({"values": values, "other": other}, ensure_ascii=False)), None

    if qtype == "matrix_single_choice":
        rows = rules.get("rows", [])
        matrix = {}
        for index, row in enumerate(rows):
            value = (form_data.get(f"{key}_{index}") or "").strip()
            if question.is_required and not value:
                return None, f"请完成“{row}”这一行。"
            if value and value not in allowed:
                return None, "矩阵中包含无效选项。"
            if value:
                matrix[row] = value
        if not matrix:
            return None, None
        return (None, json.dumps(matrix, ensure_ascii=False)), None

    raw = (form_data.get(key) or "").strip()
    if question.is_required and not raw:
        return None, "此题为必填题。"
    if not raw:
        return None, None

    if qtype == "single_choice":
        if raw not in allowed:
            return None, "请选择有效选项。"
        other = clean_other(form_data.get(f"{key}_other")) if raw == "other" else ""
        if raw == "other" and not other:
            return None, "选择“其他”后请填写具体内容。"
        if other is None:
            return None, "其他内容不能包含 HTML。"
        return (None, json.dumps({"value": raw, "other": other}, ensure_ascii=False)), None

    if qtype in TEXT_TYPES:
        if contains_html(raw):
            return None, "请勿输入 HTML 标签或脚本。"
        if rules.get("min_length") is not None and len(raw) < rules["min_length"]:
            return None, f"请至少填写 {rules['min_length']} 个字符。"
        if rules.get("max_length") is not None and len(raw) > rules["max_length"]:
            return None, f"最多填写 {rules['max_length']} 个字符。"
        return (raw, None), None

    if qtype in {"number", "rating"}:
        try:
            number = float(raw)
        except ValueError:
            return None, "请输入有效数字。"
        if rules.get("min_value") is not None and number < rules["min_value"]:
            return None, f"数值不能小于 {rules['min_value']}。"
        if rules.get("max_value") is not None and number > rules["max_value"]:
            return None, f"数值不能大于 {rules['max_value']}。"
        return (raw, None), None

    if qtype == "consent":
        if raw != "yes":
            return None, "需要同意后才能继续。"
        return ("yes", None), None

    return None, "暂不支持该题型。"


def clean_other(value):
    value = (value or "").strip()
    if contains_html(value):
        return None
    return value[:500]


def answer_display(answer):
    if answer.answer_text is not None:
        return answer.answer_text
    try:
        data = json.loads(answer.answer_json or "null")
    except ValueError:
        return ""
    if isinstance(data, dict) and "values" in data:
        values = list(data.get("values", []))
        if data.get("other"):
            values = [data.get("other") if value == "other" else value for value in values]
        return "；".join(values)
    if isinstance(data, dict) and "value" in data:
        return data.get("other") or data.get("value", "")
    if isinstance(data, dict):
        return "；".join(f"{key}：{value}" for key, value in data.items())
    return str(data or "")


def normalize_datetime(value):
    if value and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def availability(survey, now=None):
    now = now or datetime.now(timezone.utc)
    start_at, end_at = normalize_datetime(survey.start_at), normalize_datetime(survey.end_at)
    if survey.status == "closed":
        return "closed"
    if survey.status == "paused":
        return "paused"
    if survey.status != "published":
        return "draft"
    if start_at and now < start_at:
        return "upcoming"
    if end_at and now > end_at:
        return "closed"
    return "open"


def device_type(user_agent):
    value = (user_agent or "").lower()
    if "ipad" in value or "tablet" in value:
        return "tablet"
    if any(name in value for name in ["mobile", "iphone", "android"]):
        return "mobile"
    return "desktop"


def safe_source(value):
    value = (value or "direct").strip().lower()
    cleaned = "".join(char for char in value if char.isalnum() or char in {"_", "-"})
    return (cleaned or "direct")[:80]


def response_audit_details(record, question_ids=None):
    """Return a non-sensitive audit summary without copying answer content."""
    return json.dumps(
        {
            "source": record.source,
            "logged_in": bool(record.user_id),
            "completion_seconds": record.completion_seconds,
            "question_ids": sorted(question_ids if question_ids is not None else
                                   (answer.question_id for answer in record.answers)),
        },
        ensure_ascii=False,
    )
