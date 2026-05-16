import json
from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODEL_NAME
from agents.prompts import COACH_SYSTEM_PROMPT
from database.db import get_recent_logs

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


def recovery_agent_node(state: dict) -> dict:
    user_id = state.get("user_id", "")
    profile = state.get("user_profile", {})

    # 读取今日填写数据（支持顶层 state 和 today_readiness 两种来源）
    today_readiness = state.get("today_readiness", {})
    sleep = (
        state.get("sleep")
        or state.get("sleep_score")
        or today_readiness.get("sleep")
        or today_readiness.get("sleep_score", 7)
    )
    stress = (
        state.get("stress")
        or state.get("stress_score")
        or today_readiness.get("stress")
        or today_readiness.get("stress_score", 5)
    )
    fatigue = (
        state.get("fatigue")
        or state.get("fatigue_score")
        or today_readiness.get("fatigue")
        or today_readiness.get("fatigue_score", 5)
    )
    pain_areas = state.get("pain_areas") or today_readiness.get("pain_areas", [])

    # 读取历史数据
    recent_logs = get_recent_logs(user_id, days=28)

    avg_sleep = (
        sum(l.get("sleep_score", 7) for l in recent_logs)
        / len(recent_logs)
        if recent_logs else 7
    )
    avg_stress = (
        sum(l.get("stress_score", 5) for l in recent_logs)
        / len(recent_logs)
        if recent_logs else 5
    )
    avg_completion = (
        sum(l.get("completion_rate", 0) for l in recent_logs)
        / len(recent_logs)
        if recent_logs else 0
    )

    system_prompt = COACH_SYSTEM_PROMPT + f"""

══ 本次恢复评估任务 ══
今日用户填写：
  睡眠评分：{sleep}/10
  压力评分：{stress}/10
  疲劳评分：{fatigue}/10
  疼痛部位：{pain_areas}
近28天历史数据：
  平均完练率：{avg_completion:.0%}
  平均睡眠评分：{avg_sleep:.1f}
  平均压力评分：{avg_stress:.1f}
  训练次数：{len(recent_logs)}次

请按照 SECTION 5 的公式计算 readiness，
按照 SECTION 9 的 Recovery Agent 输出格式返回 JSON。
"""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",
                 "content": "请评估今日恢复状态，按照 SECTION 9 的 Recovery Agent 输出格式返回 JSON。不要返回其他文字。"},
            ],
            max_tokens=600,
            temperature=0.7,
        )
        result = json.loads(response.choices[0].message.content)
    except Exception as e:
        result = {
            "readiness_score": 5.0,
            "intensity_pct": 75,
            "level": "reduced",
            "deload_needed": False,
            "deload_type": "null",
            "pain_areas": pain_areas,
            "pain_severity": None,
            "recommendation": f"评估生成失败，使用保守默认值: {e}",
            "flags": {
                "substitute_exercises": len(pain_areas) > 0,
                "cancel_last_set": False,
                "no_top_sets": False,
            },
        }

    return {
        "today_readiness": result,
        "agent_response": result.get("recommendation", ""),
    }
