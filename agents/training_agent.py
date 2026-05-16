import json
from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODEL_NAME
from agents.prompts import COACH_SYSTEM_PROMPT

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


def training_agent_node(state: dict) -> dict:
    profile = state.get("user_profile", {})
    split_type = state.get("split_type", "")
    phase = state.get("phase", "")
    training_stage = state.get("training_stage", "intermediate")
    intensity_pct = state.get("intensity_pct", 100)

    today_readiness = state.get("today_readiness", {})
    pain_areas = today_readiness.get("pain_areas", [])
    flags = state.get("flags", {})

    system_prompt = COACH_SYSTEM_PROMPT + f"""

══ 本次计划生成任务 ══
今日分化：{split_type}
当前周期：{phase}
训练阶段：{training_stage}
今日 intensity_pct：{intensity_pct}
疼痛部位：{json.dumps(pain_areas, ensure_ascii=False)}
Recovery Agent flags：{json.dumps(flags, ensure_ascii=False)}
用户三大项1RM：
  深蹲：{profile.get('squat_1rm', 0)}kg
  卧推：{profile.get('bench_1rm', 0)}kg
  硬拉：{profile.get('deadlift_1rm', 0)}kg
体重：{profile.get('weight_kg', 70)}kg
"""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",
                 "content": "请根据以上信息生成今日训练计划，按照 SECTION 9 的 Training Agent 输出格式返回 JSON。不要返回其他文字。"},
            ],
            max_tokens=600,
            temperature=0.7,
        )
        result = json.loads(response.choices[0].message.content)
    except Exception as e:
        result = {
            "split_type": split_type,
            "phase": phase,
            "training_stage": training_stage,
            "intensity_pct": intensity_pct,
            "deload_type": "null",
            "exercises": [],
            "coach_note": f"计划生成失败: {e}",
        }

    return {
        "current_plan": result,
        "agent_response": result.get("coach_note", "训练计划已生成"),
    }
