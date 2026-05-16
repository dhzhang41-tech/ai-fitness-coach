import json
from database.db import (
    get_user,
    get_user_profile,
    get_avg_completion_rate,
    get_pr_stagnation_weeks,
    mark_plan_stale,
)

INTENTS = {
    "start_workout": "开始今日训练",
    "ask_exercise": "问某个动作怎么做",
    "log_nutrition": "记录饮食",
    "review_macro_plan": "主动要求调整长期计划",
    "general_chat": "一般闲聊",
}

PLAN_REVIEW_SIGNALS = [
    "进步停滞", "没有进步", "瓶颈", "换计划",
    "计划有问题", "练不动", "要不要调整", "停滞",
    "没效果", "plateau", "不进步",
]


def detect_plan_review_intent(message: str) -> bool:
    for signal in PLAN_REVIEW_SIGNALS:
        if signal in message:
            return True
    return False


def check_auto_stagnation(user_id: str) -> bool:
    avg_rate = get_avg_completion_rate(user_id, weeks=4)
    bench_stagnant = get_pr_stagnation_weeks(user_id, "卧推") >= 6
    squat_stagnant = get_pr_stagnation_weeks(user_id, "深蹲") >= 6
    return avg_rate < 0.75 or bench_stagnant or squat_stagnant


def classify_intent(user_input: str) -> str:
    ui = user_input.strip()
    if detect_plan_review_intent(ui):
        return "review_macro_plan"
    if ui in ("开始训练", "开始今日训练", "去训练", "训练", "健身", "start"):
        return "start_workout"
    if "怎么练" in ui or "怎么做" in ui or "动作" in ui or "怎么做" in ui or "标准" in ui:
        return "ask_exercise"
    if "蛋白" in ui or "蛋白质" in ui or "饮食" in ui or "吃了" in ui or "营养" in ui:
        return "log_nutrition"
    return "general_chat"


def orchestrator_node(state: dict) -> dict:
    user_id = state.get("user_id", "test_user_001")
    user = get_user(user_id)
    profile = get_user_profile(user_id)
    user_name = user["name"] if user else "用户"

    user_input = state.get("user_input", "")
    # 如果外部已传入确定的 intent（如 run_session 直接指定），优先使用
    intent = state.get("intent") or classify_intent(user_input)

    macro_plan = {}
    if profile and profile.get("macro_plan_json"):
        try:
            macro_plan = json.loads(profile["macro_plan_json"])
        except (json.JSONDecodeError, TypeError):
            macro_plan = {}

    plan_needs_review = detect_plan_review_intent(user_input)
    if not plan_needs_review:
        plan_needs_review = check_auto_stagnation(user_id)

    return {
        "user_id": user_id,
        "user_name": user_name,
        "user_profile": profile or {},
        "macro_plan": macro_plan,
        "plan_needs_review": plan_needs_review,
        "intent": intent,
        "agent_response": "",
        "error": "",
    }
