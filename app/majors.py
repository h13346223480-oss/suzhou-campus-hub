ROBOTICS_ENGINEERING = "robotics_engineering"
INTELLIGENT_MANUFACTURING_ENGINEERING = "intelligent_manufacturing_engineering"
NEW_ENERGY_SCIENCE_ENGINEERING = "new_energy_science_engineering"
OTHER = "other"
PENDING_CONFIRMATION = "pending_confirmation"
GENERAL = "general"

STUDENT_MAJOR_LABELS = {
    ROBOTICS_ENGINEERING: "机器人工程",
    INTELLIGENT_MANUFACTURING_ENGINEERING: "智能制造工程",
    NEW_ENERGY_SCIENCE_ENGINEERING: "新能源科学与工程",
    OTHER: "其他",
    PENDING_CONFIRMATION: "待确认",
}

STUDENT_MAJOR_CHOICES = [
    (ROBOTICS_ENGINEERING, STUDENT_MAJOR_LABELS[ROBOTICS_ENGINEERING]),
    (INTELLIGENT_MANUFACTURING_ENGINEERING, STUDENT_MAJOR_LABELS[INTELLIGENT_MANUFACTURING_ENGINEERING]),
    (NEW_ENERGY_SCIENCE_ENGINEERING, STUDENT_MAJOR_LABELS[NEW_ENERGY_SCIENCE_ENGINEERING]),
    (OTHER, STUDENT_MAJOR_LABELS[OTHER]),
]

PENDING_CONFIRMATION_CHOICES = STUDENT_MAJOR_CHOICES[:2]
RESOURCE_MAJOR_CHOICES = [(GENERAL, "通用"), *STUDENT_MAJOR_CHOICES]
USER_MAJOR_CODES = {*STUDENT_MAJOR_LABELS}
RESOURCE_MAJOR_CODES = {GENERAL, *(code for code, _label in STUDENT_MAJOR_CHOICES)}


def major_label(code):
    if code == GENERAL:
        return "通用"
    return STUDENT_MAJOR_LABELS.get(code, "待确认")


def normalize_user_major(value):
    """Return a controlled user major code; ambiguous legacy values stay pending."""
    if value in USER_MAJOR_CODES:
        return value
    label_to_code = {label: code for code, label in STUDENT_MAJOR_LABELS.items()}
    aliases = {
        "新能源": NEW_ENERGY_SCIENCE_ENGINEERING,
        "平台维护": OTHER,
        "专业待确认": PENDING_CONFIRMATION,
        "机器人" + "/" + "智能制造": PENDING_CONFIRMATION,
    }
    return label_to_code.get(value, aliases.get(value, PENDING_CONFIRMATION))


def normalize_resource_major(value):
    if value in RESOURCE_MAJOR_CODES:
        return value
    if value == "通用":
        return GENERAL
    code = normalize_user_major(value)
    return GENERAL if code == PENDING_CONFIRMATION else code
