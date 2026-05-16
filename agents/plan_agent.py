import json
from datetime import date
from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODEL_NAME
from database.db import update_macro_plan, calculate_training_years
from knowledge.rag import search_training_principles

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

SPLIT_PLANS = {
    "PPL_3": {
        "push": {
            "exercises": ["卧推", "颈前推举", "哑铃飞鸟", "三头绳索下压", "哑铃侧平举"],
            "sets_per_exercise": 4,
            "reps_range": "8-12",
        },
        "pull": {
            "exercises": ["俯身划船", "坐姿划船", "高位下拉", "哑铃弯举", "绳索面拉"],
            "sets_per_exercise": 4,
            "reps_range": "8-12",
        },
        "legs": {
            "exercises": ["深蹲", "腿举", "罗马尼亚硬拉", "腿弯举", "臀推"],
            "sets_per_exercise": 4,
            "reps_range": "8-12",
        },
    },
    "UL_4": {
        "upper_a": {
            "exercises": ["卧推", "俯身划船", "颈前推举", "高位下拉", "哑铃侧平举"],
            "sets_per_exercise": 4,
            "reps_range": "8-12",
        },
        "lower_a": {
            "exercises": ["深蹲", "腿举", "腿弯举", "臀推", "平板支撑"],
            "sets_per_exercise": 4,
            "reps_range": "8-12",
        },
        "upper_b": {
            "exercises": ["哑铃飞鸟", "坐姿划船", "哑铃弯举", "三头绳索下压", "绳索面拉"],
            "sets_per_exercise": 3,
            "reps_range": "10-15",
        },
        "lower_b": {
            "exercises": ["罗马尼亚硬拉", "腿举", "腿夹器", "臀推", "平板支撑"],
            "sets_per_exercise": 3,
            "reps_range": "10-15",
        },
    },
    "PPL_5": {
        "push": {
            "exercises": ["卧推", "颈前推举", "哑铃飞鸟", "三头绳索下压", "哑铃侧平举", "哑铃前平举"],
            "sets_per_exercise": 4,
            "reps_range": "8-12",
        },
        "pull": {
            "exercises": ["俯身划船", "坐姿划船", "高位下拉", "哑铃弯举", "绳索面拉", "引体向上"],
            "sets_per_exercise": 4,
            "reps_range": "8-12",
        },
        "legs": {
            "exercises": ["深蹲", "腿举", "罗马尼亚硬拉", "腿弯举", "臀推", "腿夹器"],
            "sets_per_exercise": 4,
            "reps_range": "8-12",
        },
        "push_2": {
            "exercises": ["哑铃飞鸟", "颈前推举", "三头绳索下压", "哑铃侧平举"],
            "sets_per_exercise": 3,
            "reps_range": "10-15",
        },
        "legs_2": {
            "exercises": ["硬拉", "腿举", "腿弯举", "臀推"],
            "sets_per_exercise": 3,
            "reps_range": "10-15",
        },
    },
}

EXERCISE_INTENSITY_PCT = {
    "卧推": 0.75, "深蹲": 0.75, "硬拉": 0.80,
    "颈前推举": 0.70, "俯身划船": 0.72, "坐姿划船": 0.72,
    "高位下拉": 0.72, "哑铃弯举": 0.65, "罗马尼亚硬拉": 0.72,
    "腿举": 0.80, "腿弯举": 0.72, "臀推": 0.75,
    "哑铃飞鸟": 0.60, "三头绳索下压": 0.60, "哑铃侧平举": 0.55,
    "绳索面拉": 0.55, "腿夹器": 0.65, "哑铃前平举": 0.55,
    "引体向上": 0.75, "平板支撑": 0.50,
}

EXERCISE_1RM_BASE = {
    "卧推": "bench_1rm", "颈前推举": "bench_1rm",
    "哑铃飞鸟": "bench_1rm", "三头绳索下压": "bench_1rm",
    "哑铃侧平举": "bench_1rm", "哑铃前平举": "bench_1rm",
    "深蹲": "squat_1rm", "腿举": "squat_1rm",
    "腿弯举": "squat_1rm", "臀推": "squat_1rm",
    "腿夹器": "squat_1rm",
    "硬拉": "deadlift_1rm", "俯身划船": "deadlift_1rm",
    "坐姿划船": "deadlift_1rm", "高位下拉": "deadlift_1rm",
    "哑铃弯举": "deadlift_1rm", "绳索面拉": "deadlift_1rm",
    "罗马尼亚硬拉": "deadlift_1rm",
    "引体向上": "deadlift_1rm",
}


def select_split(days_per_week: int, training_years: float) -> str:
    if days_per_week <= 3:
        return "PPL_3"
    elif days_per_week == 4:
        return "UL_4"
    else:
        return "PPL_5"


def calc_weight(exercise_name: str, profile: dict) -> float:
    rm_field = EXERCISE_1RM_BASE.get(exercise_name)
    intensity = EXERCISE_INTENSITY_PCT.get(exercise_name, 0.70)
    if rm_field and profile.get(rm_field):
        return round(profile[rm_field] * intensity / 2.5) * 2.5
    return 20.0


def build_macro_plan(profile: dict) -> dict:
    training_years = profile.get("training_years")
    if training_years is None and profile.get("training_start_date"):
        training_years = calculate_training_years(profile["training_start_date"])
    split_key = select_split(profile.get("days_per_week", 4), training_years or 1)
    split_plan = SPLIT_PLANS[split_key]

    weeks = []
    for week_num in range(1, 5):
        phase = "accumulation" if week_num <= 3 else "deload"
        days = []
        for day_key, day_plan in split_plan.items():
            exercises = []
            for ex_name in day_plan["exercises"]:
                weight = calc_weight(ex_name, profile)
                sets = day_plan["sets_per_exercise"]
                if phase == "deload":
                    weight = round(weight * 0.6 / 2.5) * 2.5
                exercises.append({
                    "name": ex_name,
                    "sets": sets,
                    "reps": day_plan["reps_range"],
                    "weight_kg": weight,
                    "day": day_key,
                })
            days.append({
                "day_key": day_key,
                "exercises": exercises,
            })
        weeks.append({
            "week": week_num,
            "phase": phase,
            "days": days,
        })

    return {
        "split": split_key,
        "weeks": weeks,
        "current_week": 1,
        "current_day_index": 0,
    }


def plan_agent_node(state: dict) -> dict:
    profile = state.get("user_profile", {})
    principles = search_training_principles("周期化训练计划 增肌 分化")

    plan = build_macro_plan(profile)

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": "你是一个专业增肌教练。请根据用户档案生成训练周期说明。回复控制在200字以内，中文。",
                },
                {
                    "role": "user",
                    "content": (
                        f"用户档案：{json.dumps(profile, ensure_ascii=False)}\n"
                        f"训练原则参考：{' '.join(principles)}\n"
                        f"生成的计划摘要：{json.dumps(plan, ensure_ascii=False)}\n"
                        "请简要说明这个训练周期的安排逻辑和注意事项。"
                    ),
                },
            ],
            temperature=0.7,
        )
        coach_comment = response.choices[0].message.content
    except Exception as e:
        # DeepSeek API 失败不阻塞计划生成，但把异常信息传递出去
        coach_comment = f"（AI 点评生成失败: {e}）"

    plan_json = json.dumps(plan, ensure_ascii=False)
    print(f"[plan_agent] 准备写入 plan_json, 长度={len(plan_json)}, 前100字符={plan_json[:100]}")
    print(f"[plan_agent] user_id={state['user_id']}, phase={plan['weeks'][0]['phase']}, week=1")
    try:
        update_macro_plan(
            user_id=state["user_id"],
            phase=plan["weeks"][0]["phase"],
            week=1,
            plan_json=plan_json,
            start_date=str(date.today()),
        )
        print(f"[plan_agent] update_macro_plan 执行完毕")
    except Exception as e:
        print(f"[plan_agent] update_macro_plan 抛出异常: {e}")
        raise RuntimeError(f"写入训练计划到数据库失败: {e}") from e

    return {
        "macro_plan": plan,
        "agent_response": f"长期训练计划已生成！{coach_comment}",
    }
