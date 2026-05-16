from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODEL_NAME
from knowledge.rag import search_recovery_knowledge, search_exercises

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

REPLAN_STRATEGIES = {
    "太重": "降低剩余动作重量15-20%，组数不变",
    "太累": "减少剩余动作组数1-2组，重量不变",
    "部位不舒服": "移除涉及该部位的动作，用其他动作替代",
    "没时间": "只保留剩余动作中最重要的2-3个，其余跳过",
}


def _find_exercise_by_name(name: str, exercises: list) -> dict | None:
    for ex in exercises:
        if ex.get("name") == name:
            return ex
    return None


def _get_remaining_exercises(all_exercises: list, completed: list) -> list:
    completed_names = {e.get("name") for e in completed}
    return [e for e in all_exercises if e.get("name") not in completed_names]


def replan_agent_node(state: dict) -> dict:
    replan_count = state.get("replan_count", 0)

    if replan_count >= 2:
        return {
            "agent_response": "今日训练到此结束，你已经做得很好了！休息一下，明天继续努力 💪",
            "replan_count": replan_count + 1,
        }

    reason = state.get("replan_reason", "太累")
    completed = state.get("completed_exercises", [])
    all_exercises = state.get("current_plan", {}).get("exercises", [])
    remaining = _get_remaining_exercises(all_exercises, completed)
    strategy = REPLAN_STRATEGIES.get(reason, "适当降低强度")

    rag_results = search_recovery_knowledge(f"训练中{reason}如何调整")

    adjusted_remaining = []
    if reason == "太重":
        for ex in remaining:
            ex = dict(ex)
            ex["weight_kg"] = round(ex.get("weight_kg", 0) * 0.8 / 2.5) * 2.5
            adjusted_remaining.append(ex)
    elif reason == "太累":
        for ex in remaining:
            ex = dict(ex)
            ex["sets"] = max(1, ex.get("sets", 3) - 1)
            adjusted_remaining.append(ex)
    elif reason == "没时间":
        adjusted_remaining = [dict(ex) for ex in remaining[:3]]
    else:
        adjusted_remaining = [dict(ex) for ex in remaining]

    try:
        prompt = (
            f"训练原因：{reason}，调整策略：{strategy}\n"
            f"剩余动作：{[e['name'] for e in adjusted_remaining]}\n"
            f"恢复建议：{' '.join(rag_results)}\n"
            "请给用户一段鼓励性+建设性的调整说明，控制在100字以内。"
        )
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "你是专业体贴的健身教练。调整训练计划时要鼓励用户，不要批评。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )
        coach_msg = response.choices[0].message.content
    except Exception:
        coach_msg = f"已根据「{reason}」调整剩余训练计划，加油！"

    adjusted_plan = dict(state.get("current_plan", {}))
    adjusted_plan["exercises"] = adjusted_remaining

    return {
        "current_plan": adjusted_plan,
        "replan_count": replan_count + 1,
        "agent_response": coach_msg,
    }
