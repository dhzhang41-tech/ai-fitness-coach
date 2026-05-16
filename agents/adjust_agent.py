import json
from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODEL_NAME
from knowledge.rag import search_recovery_knowledge

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


def assess_readiness(sleep: int, stress: int, fatigue: int) -> dict:
    score = sleep * 0.4 + (10 - stress) * 0.3 + (10 - fatigue) * 0.3
    if score >= 7:
        level = "normal"
        intensity_pct = 100
        recommendation = "状态良好，按计划正常训练"
    elif score >= 5:
        level = "reduced"
        intensity_pct = 80
        recommendation = "状态一般，建议降低重量20%，减少一组"
    else:
        level = "rest"
        intensity_pct = 60
        recommendation = "状态较差，建议今日做恢复性训练或休息"
    return {
        "score": round(score, 1),
        "level": level,
        "intensity_pct": intensity_pct,
        "recommendation": recommendation,
    }


def adjust_plan_for_readiness(macro_plan: dict, readiness: dict) -> dict:
    level = readiness["level"]
    intensity_pct = readiness["intensity_pct"]

    if level == "rest":
        return {
            "is_rest_day": True,
            "recommendation": readiness["recommendation"],
            "exercises": [
                {
                    "name": "拉伸放松",
                    "sets": 1,
                    "reps": "15-30秒",
                    "weight_kg": 0,
                    "note": "全身拉伸，重点放松酸痛部位",
                },
                {
                    "name": "低强度有氧",
                    "sets": 1,
                    "reps": "20-30分钟",
                    "weight_kg": 0,
                    "note": "心率控制在120-130，快走或慢跑",
                },
            ],
        }

    current_week_idx = macro_plan.get("current_week", 1) - 1
    current_day_idx = macro_plan.get("current_day_index", 0)
    weeks = macro_plan.get("weeks", [])
    if current_week_idx < len(weeks):
        days = weeks[current_week_idx].get("days", [])
        if current_day_idx < len(days):
            day_plan = days[current_day_idx]
            adjusted_exercises = []
            for ex in day_plan.get("exercises", []):
                adjusted = dict(ex)
                adjusted["weight_kg"] = round(ex["weight_kg"] * intensity_pct / 100 / 2.5) * 2.5
                if level == "reduced":
                    adjusted["sets"] = max(1, ex["sets"] - 1)
                adjusted_exercises.append(adjusted)
            return {
                "is_rest_day": False,
                "recommendation": readiness["recommendation"],
                "exercises": adjusted_exercises,
            }

    return {
        "is_rest_day": False,
        "recommendation": readiness["recommendation"],
        "exercises": [],
    }


def adjust_agent_node(state: dict) -> dict:
    readiness = state.get("today_readiness", {})
    macro_plan = state.get("macro_plan", {})
    score = readiness.get("score", 10)
    level = readiness.get("level", "normal")

    adjusted = adjust_plan_for_readiness(macro_plan, readiness)
    recovery_info = search_recovery_knowledge("状态差恢复训练")

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": "你是一个专业的增肌教练，根据用户今日状态评估调整训练计划。回复专业、体贴，控制在150字以内。",
                },
                {
                    "role": "user",
                    "content": (
                        f"今日状态评分：{score}（水平：{level}），"
                        f"睡眠{readiness.get('sleep', 7)}/10，"
                        f"压力{readiness.get('stress', 5)}/10，"
                        f"疲劳{readiness.get('fatigue', 5)}/10。\n"
                        f"恢复知识参考：{' '.join(recovery_info)}\n"
                        f"建议调整：{readiness.get('recommendation', '')}"
                    ),
                },
            ],
            temperature=0.7,
        )
        coach_message = response.choices[0].message.content
    except Exception:
        coach_message = readiness.get("recommendation", "")

    return {
        "current_plan": adjusted,
        "is_override": level != "normal",
        "agent_response": coach_message,
    }
