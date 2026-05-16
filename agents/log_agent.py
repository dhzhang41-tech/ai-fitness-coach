import uuid
import json
from datetime import date
from database.db import save_workout_log, save_pr, get_user_profile, update_macro_plan


def _check_and_save_pr(user_id: str, exercise_name: str, actual_weight: float, sets_done: int) -> bool:
    profile = get_user_profile(user_id)
    if not profile:
        return False

    rm_field_map = {
        "卧推": "bench_1rm", "深蹲": "squat_1rm", "硬拉": "deadlift_1rm",
    }
    rm_field = rm_field_map.get(exercise_name)
    if not rm_field:
        return False

    current_rm = profile.get(rm_field) or 0
    estimated_1rm = actual_weight * (1 + sets_done / 30)
    if estimated_1rm > current_rm * 1.02:
        save_pr(user_id, exercise_name, round(estimated_1rm, 1), sets_done)
        return True
    return False


def _advance_macro_week(user_id: str) -> None:
    profile = get_user_profile(user_id)
    if not profile:
        return
    current_week = profile.get("macro_week", 1)
    current_phase = profile.get("macro_phase", "accumulation")
    plan_json = profile.get("macro_plan_json", "{}")
    if not plan_json:
        return

    next_week = current_week + 1
    if next_week > 4:
        next_week = 1
        next_phase = "accumulation"
    else:
        next_phase = "deload" if next_week == 4 else "accumulation"

    update_macro_plan(
        user_id=user_id,
        phase=next_phase,
        week=next_week,
        plan_json=plan_json,
        start_date=str(profile.get("macro_start_date") or date.today()),
    )


def _estimate_from_exercises(completed: list) -> dict:
    total_weight = 0
    count = 0
    for ex in completed:
        w = ex.get("actual_weight") or ex.get("weight_kg") or 0
        s = ex.get("sets_done") or ex.get("sets") or 1
        total_weight += w * s
        count += 1
    return {"total_volume": total_weight, "exercise_count": count}


def log_agent_node(state: dict) -> dict:
    user_id = state["user_id"]
    completed_exercises = state.get("completed_exercises", [])
    current_plan = state.get("current_plan", {})
    planned_exercises = current_plan.get("exercises", [])
    readiness = state.get("today_readiness", {})

    total_planned = len(planned_exercises)
    total_completed = len(completed_exercises)

    # 防止除零和超出范围
    if total_planned > 0:
        completion_rate = round(total_completed / total_planned, 2)
        completion_rate = max(0.0, min(1.0, completion_rate))
    else:
        completion_rate = 1.0

    print(f"[log_agent] planned={total_planned}, completed={total_completed}, rate={completion_rate}")

    log_id = str(uuid.uuid4())
    save_workout_log({
        "id": log_id,
        "user_id": user_id,
        "log_date": str(date.today()),
        "sleep_score": readiness.get("sleep", 7),
        "stress_score": readiness.get("stress", 5),
        "fatigue_score": readiness.get("fatigue", 5),
        "pain_areas": ",".join(readiness.get("pain_areas", [])),
        "planned_json": json.dumps(planned_exercises, ensure_ascii=False),
        "actual_json": json.dumps(completed_exercises, ensure_ascii=False),
        "completion_rate": completion_rate,
        "is_override": state.get("is_override", False),
        "replan_count": state.get("replan_count", 0),
    })

    new_prs = []
    for ex in completed_exercises:
        if ex.get("actual_weight") and ex.get("sets_done"):
            is_new = _check_and_save_pr(
                user_id,
                ex["name"],
                ex["actual_weight"],
                ex["sets_done"],
            )
            if is_new:
                new_prs.append(ex["name"])

    _advance_macro_week(user_id)

    volume_info = _estimate_from_exercises(completed_exercises)
    summary_parts = []
    if completion_rate >= 0.9:
        summary_parts.append(f"完练率 {int(completion_rate * 100)}%，非常棒，训练质量很高！")
    elif completion_rate >= 0.7:
        summary_parts.append(f"完练率 {int(completion_rate * 100)}%，不错，基本完成了今日目标。")
    else:
        summary_parts.append(f"完练率 {int(completion_rate * 100)}%，今天状态一般，下次继续加油！")

    if new_prs:
        summary_parts.append(f"🎉 新PR突破：{'、'.join(new_prs)}，你又变强了！")
    if volume_info["exercise_count"] > 0:
        summary_parts.append(f"今日训练总组数：{volume_info['exercise_count']}，估算总容量：{int(volume_info['total_volume'])}kg")

    return {
        "agent_response": "\n".join(summary_parts),
    }
