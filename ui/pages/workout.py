import streamlit as st
import json
from database.db import get_user_profile
from agents.graph import run_session
from agents.adjust_agent import assess_readiness
from ui.forms import render_readiness_form, render_workout_log_form
from ui.display import render_exercise_card, render_training_summary


def get_today_plan(user_id: str) -> dict | None:
    """
    根据循环周期索引读取今日训练计划。
    返回 None 表示今日是休息日或无计划。
    """
    from database.db import (
        get_user_profile,
        get_today_cycle_index,
    )

    profile = get_user_profile(user_id)
    if not profile:
        return None

    macro_json = profile.get("macro_plan_json")
    if not macro_json:
        return None

    try:
        macro = json.loads(macro_json)
    except (json.JSONDecodeError, TypeError):
        return None

    days = macro.get("days", [])
    if not days:
        return None

    idx = get_today_cycle_index(user_id)
    if idx >= len(days):
        idx = 0

    today_day = days[idx]
    day_name = today_day.get("day_name", "")
    exercises = today_day.get("exercises", [])

    # 休息日返回 None
    if day_name == "休息" or not exercises:
        return None

    return today_day


def render_workout(user_id: str):
    import json
    from database.db import get_user_profile

    # workout_step 初始化
    if "workout_step" not in st.session_state:
        st.session_state.workout_step = "readiness_form"

    step = st.session_state.workout_step

    # Step 1：状态评估表单
    if step == "readiness_form":
        from ui.forms import render_readiness_form
        st.title("🏋️ 开始训练")
        form_data = render_readiness_form()
        if form_data:
            st.session_state.today_readiness = form_data
            st.session_state.workout_step = "plan_display"
            st.rerun()

    # Step 2：展示今日计划
    elif step == "plan_display":
        st.title("📋 今日训练计划")

        # 读取今日计划
        today_plan = get_today_plan(user_id)

        if not today_plan:
            # 判断是休息日还是没有计划
            from database.db import (
                is_rest_day, get_user_profile
            )
            profile = get_user_profile(user_id)
            has_plan = bool(
                profile and profile.get("macro_plan_json")
            )

            if has_plan and is_rest_day(user_id):
                st.success("🛌 今日是休息日，好好恢复！")
                st.info(
                    "明天继续训练，今天专注睡眠和营养补充。"
                )
            else:
                st.warning("未找到今日训练计划。")
                st.info(
                    "请先在「训练计划调整」里输入训练计划。"
                )
                if st.button("去创建计划"):
                    st.session_state.page = "plan_edit"
                    st.rerun()

            if st.button("返回首页"):
                st.session_state.page = "home"
                st.rerun()
            return

        # 根据今日状态调整计划
        readiness = st.session_state.get("today_readiness", {})
        exercises = today_plan.get("exercises", [])

        # 应用 intensity_pct 调整重量
        if readiness:
            readiness_result = assess_readiness(
                readiness.get("sleep", 7),
                readiness.get("stress", 3),
                readiness.get("fatigue", 3),
            )
            intensity_pct = readiness_result.get("intensity_pct", 100)
            st.session_state.today_readiness["intensity_pct"] = intensity_pct

            if intensity_pct < 100:
                st.warning(f"根据今日状态，建议强度调整为 {intensity_pct}%")
        else:
            intensity_pct = 100

        # 标准化 exercises 格式
        # 兼容 plan_edit（reps 字段）和 training_agent（reps_range 字段）
        standardized = []
        for ex in exercises:
            reps_range = ex.get("reps_range") or str(ex.get("reps", "8-12"))
            weight = ex.get("weight_kg") or 0
            adjusted_weight = round(weight * intensity_pct / 100 / 2.5) * 2.5

            standardized.append({
                "name": ex.get("name", "未知动作"),
                "sets": ex.get("sets") or 4,
                "reps_range": reps_range,
                "weight_kg": adjusted_weight,
                "rest_seconds": ex.get("rest_seconds", 120),
                "notes": ex.get("notes", ""),
            })

        # 存入 session_state
        st.session_state.current_plan = {
            "day_name": today_plan.get("day_name", "训练"),
            "exercises": standardized,
        }
        st.session_state.current_exercise_index = 0
        st.session_state.completed_exercises = []

        # 展示计划摘要
        st.markdown(f"#### {today_plan.get('day_name', '今日')} 训练")
        for ex in standardized:
            st.write(f"**{ex['name']}**　{ex['sets']}组 × {ex['reps_range']}次　{ex['weight_kg']}kg")

        st.divider()
        if st.button("开始训练 →", type="primary", use_container_width=True):
            st.session_state.workout_step = "exercise_loop"
            st.rerun()

        if st.button("返回首页"):
            st.session_state.page = "home"
            st.rerun()

    elif step == "exercise_loop":
        plan = st.session_state.get("current_plan", {})
        exercises = plan.get("exercises", [])
        idx = st.session_state.get("current_exercise_index", 0)
        replan_count = st.session_state.get("replan_count", 0)

        if idx >= len(exercises):
            st.session_state.workout_step = "log_form"
            st.rerun()
            return

        exercise = exercises[idx]
        action = render_exercise_card(exercise, idx, len(exercises), replan_count)

        if action == "next":
            st.session_state.current_exercise_index = idx + 1
            # 记录当前动作为已完成
            completed = st.session_state.get("completed_exercises", [])
            completed.append({
                "name": exercise["name"],
                "sets": exercise.get("sets", 3),
                "sets_done": exercise.get("sets", 3),
                "weight_kg": exercise.get("weight_kg", 0),
                "actual_weight": exercise.get("weight_kg", 0),
            })
            st.session_state.completed_exercises = completed
            st.rerun()

        elif action == "prev":
            if idx > 0:
                st.session_state.current_exercise_index = idx - 1
                st.rerun()

        elif action and action.startswith("replan:"):
            reason = action.split(":", 1)[1]
            completed = st.session_state.get("completed_exercises", [])
            completed.append({
                "name": exercise["name"],
                "sets": exercise.get("sets", 3),
                "sets_done": 0,
                "weight_kg": exercise.get("weight_kg", 0),
                "actual_weight": 0,
                "incomplete": True,
                "reason": reason,
            })
            st.session_state.completed_exercises = completed

            result = run_session(
                user_id=user_id,
                intent="start_workout",
                replan_reason=reason,
                completed_exercises=completed,
                current_plan=plan,
                replan_count=replan_count,
            )
            st.session_state.current_plan = result.get("current_plan", plan)
            st.session_state.replan_count = result.get("replan_count", replan_count + 1)
            msg = result.get("agent_response", "")
            if msg:
                st.warning(msg)

            # 重规划后跳到下一个动作
            st.session_state.current_exercise_index = idx + 1
            st.rerun()

        elif action == "done":
            completed = st.session_state.get("completed_exercises", [])
            completed.append({
                "name": exercise["name"],
                "sets": exercise.get("sets", 3),
                "sets_done": exercise.get("sets", 3),
                "weight_kg": exercise.get("weight_kg", 0),
                "actual_weight": exercise.get("weight_kg", 0),
            })
            st.session_state.completed_exercises = completed
            st.session_state.workout_step = "log_form"
            st.rerun()

    elif step == "log_form":
        plan = st.session_state.get("current_plan", {})
        log_data = render_workout_log_form(plan)
        if log_data:
            st.session_state.completed_log = log_data["exercises"]
            st.session_state.workout_step = "summary"
            st.rerun()

    elif step == "summary":
        completed = st.session_state.get("completed_exercises", [])
        plan = st.session_state.get("current_plan", {})
        log = st.session_state.get("completed_log", [])

        # 合并日志数据中的实际重量
        log_map = {e["name"]: e for e in log}
        for ex in completed:
            if ex["name"] in log_map:
                ex["actual_weight"] = log_map[ex["name"]]["actual_weight"]
                ex["sets_done"] = log_map[ex["name"]]["sets_done"]
                ex["last_reps"] = log_map[ex["name"]].get("last_reps", ex.get("reps", 8))
                ex["feel"] = log_map[ex["name"]].get("feeling", "")

        result = run_session(
            user_id=user_id,
            intent="start_workout",
            completed_exercises=completed,
            current_plan=plan,
            replan_count=st.session_state.get("replan_count", 0),
            form_data={
                "sleep": st.session_state.today_readiness.get("sleep", 7),
                "stress": st.session_state.today_readiness.get("stress", 5),
                "fatigue": st.session_state.today_readiness.get("fatigue", 5),
            },
        )

        # 检测 PR
        new_prs = []
        for ex in completed:
            if ex.get("actual_weight") and ex.get("sets_done"):
                profile = get_user_profile(user_id)
                rm_field_map = {"卧推": "bench_1rm", "深蹲": "squat_1rm", "硬拉": "deadlift_1rm"}
                rm_field = rm_field_map.get(ex["name"])
                if rm_field and profile:
                    current_rm = profile.get(rm_field) or 0
                    estimated = ex["actual_weight"] * (1 + ex["sets_done"] / 30)
                    if estimated > current_rm * 1.02:
                        new_prs.append(ex["name"])

        summary_data = {
            "completion_rate": len(completed) / max(len(plan.get("exercises", [])), 1),
            "completed_exercises": completed,
            "agent_response": result.get("agent_response", "今天辛苦了！"),
        }
        render_training_summary(summary_data, new_prs)

        if st.button("返回首页", use_container_width=True):
            # 重置 workout state
            for k in ["workout_step", "current_exercise_index", "completed_exercises",
                      "replan_count", "current_plan", "today_readiness",
                      "is_override_setting", "completed_log"]:
                if k in st.session_state:
                    del st.session_state[k]
            st.session_state.page = "home"
            st.rerun()
