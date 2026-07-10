import streamlit as st
import json
from database.db import (
    get_user, get_user_profile, get_today_nutrition,
    get_recent_logs, save_nutrition_log,
    has_trained_today, is_rest_day, get_today_cycle_index,
    reset_today_logs,
)
from agents.nutrition_agent import estimate_protein_from_text
from agents.home_coach import home_coach_agent


def render_recent_workout_card(user_id: str):
    """显示最近一次训练的动作记录卡片"""
    logs = get_recent_logs(user_id, days=7)
    if not logs:
        st.info("暂无训练记录，开始你的第一次训练吧")
        return

    latest = logs[0]
    try:
        actual = json.loads(latest.get("actual_json") or "[]")
    except (json.JSONDecodeError, TypeError):
        actual = []

    if not actual or not isinstance(actual, list):
        # actual 为空，尝试从计划内容显示
        try:
            planned = json.loads(latest.get("planned_json") or "[]")
            if isinstance(planned, dict):
                planned = planned.get("exercises", [])
        except Exception:
            planned = []
        if planned:
            actual = planned
        else:
            st.info("暂无训练记录，开始你的第一次训练吧")
            return

    st.markdown("#### 最近训练")
    with st.container(border=True):
        cols = st.columns([2, 1, 1])
        cols[0].markdown("**动作**")
        cols[1].markdown("**重量**")
        cols[2].markdown("**组数×次数**")

        for ex in actual:
            if not isinstance(ex, dict):
                continue
            name = ex.get("name", "")
            weight = ex.get("actual_weight") or ex.get("weight_kg") or 0
            sets = ex.get("sets_done") or ex.get("sets") or 0
            reps = ex.get("last_reps") or ex.get("reps") or "-"
            c1, c2, c3 = st.columns([2, 1, 1])
            c1.write(name)
            c2.write(f"{weight}kg" if weight else "-")
            c3.write(f"{sets}×{reps}")


def render_home(user_id: str):
    user = get_user(user_id)
    profile = get_user_profile(user_id)
    if not user:
        st.error("用户不存在")
        return

    user_name = user.get("name", "用户")
    st.title(f"👋 欢迎回来，{user_name}")

    # ─── 计划状态检查 ────────────────────────────────
    has_plan = profile and profile.get("macro_plan_json") and len(profile["macro_plan_json"]) > 10

    if not has_plan:
        st.warning(
            "你还没有有效的训练计划，请先完成个人设置或重新生成计划。",
            icon="⚠️",
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📝 完善个人档案", key="home_btn_onboarding", type="primary", use_container_width=True):
                st.session_state.page = "onboarding"
                st.rerun()
        with col2:
            if st.button("🔄 尝试重新生成计划", key="home_btn_regenerate", use_container_width=True):
                st.session_state.page = "adjust_macro"
                st.rerun()
        return

    if profile.get("plan_stale"):
        st.warning("系统检测到你的训练可能需要调整。", icon="⚠️")

    # ─── 今日训练预览 ────────────────────────────────
    trained_today = has_trained_today(user_id)
    rest_day = is_rest_day(user_id)

    if trained_today:
        st.success("✅ 今日训练已完成，好好休息！")
        st.button(
            "🏋️ 今日训练已完成",
            key="home_btn_start_today_disabled",
            use_container_width=True,
            disabled=True,
        )
        # 测试用重置按钮（开发阶段使用）
        if st.button("🔧 重置今日训练状态（测试用）",
                     key="home_btn_reset_today"):
            reset_today_logs(user_id)
            st.success("已重置，可以重新训练")
            st.rerun()

    elif rest_day:
        st.info("🛌 今日休息日，专注恢复")
        if st.button(
            "🏋️ 选择训练日开始训练",
            key="home_btn_start_today",
            use_container_width=True,
            type="primary",
        ):
            st.session_state.page = "workout"
            st.session_state.workout_step = "readiness_form"
            st.session_state.current_exercise_index = 0
            st.rerun()

    else:
        macro_json = profile.get("macro_plan_json") if profile else None
        macro_phase = profile.get("macro_phase", "accumulation")
        macro_week = profile.get("macro_week", 1)

        phase_cn = {
            "accumulation": "积累期",
            "deload": "减载期",
            "strength_test": "力量测试期",
        }.get(macro_phase, macro_phase)

        if macro_json:
            try:
                macro = json.loads(macro_json)
                days = macro.get("days", [])
                idx = get_today_cycle_index(user_id)
                if idx < len(days):
                    today_day = days[idx]
                    exercises = today_day.get("exercises", [])
                    day_name = today_day.get("day_name", "")

                    st.markdown(
                        f"#### 📋 今日训练 — "
                        f"第{macro_week}周 ({phase_cn})"
                        f" — {day_name}"
                    )
                    for ex in exercises:
                        name = ex.get("name", "")
                        sets = ex.get("sets", "-")
                        weight = ex.get("weight_kg")
                        weight_str = (
                            f"{weight}kg" if weight
                            else "重量待定"
                        )
                        st.write(
                            f"**{name}**　{sets}组　{weight_str}"
                        )
            except Exception:
                st.info("计划读取异常，请重新生成计划。")
        else:
            st.info("还没有训练计划，请先创建计划。")

        if st.button(
            "🏋️ 开始训练",
            key="home_btn_start_today",
            use_container_width=True,
            type="primary",
        ):
            st.session_state.page = "workout"
            st.session_state.workout_step = "readiness_form"
            st.session_state.current_exercise_index = 0
            st.session_state.completed_exercises = []
            st.session_state.replan_count = 0
            st.rerun()

    st.divider()

    # ─── 1.1 四个主按钮 ────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📊 训练记录", key="home_btn_history",
                     use_container_width=True):
            st.session_state.page = "workout_history"
            st.rerun()
        if st.button("📋 我的计划", key="home_btn_plan",
                     use_container_width=True):
            st.session_state.page = "plan_overview"
            st.rerun()
    with col2:
        if st.button("👤 个人档案", key="home_btn_profile",
                     use_container_width=True):
            st.session_state.page = "profile"
            st.rerun()
        if st.button("✏️ 训练计划调整", key="home_btn_edit",
                     use_container_width=True):
            st.session_state.page = "plan_edit"
            st.rerun()

    st.divider()

    # ─── 1.2 最近训练内容卡片 ─────────────────────────
    render_recent_workout_card(user_id)

    st.divider()

    # ─── 1.3 蛋白质摄入模块 ────────────────────────────
    st.subheader("🥩 今日蛋白质摄入")
    nutrition = get_today_nutrition(user_id)
    protein_target = (profile.get("weight_kg", 75) * 1.8) if profile else 135
    protein_current = nutrition.get("protein_g", 0) if nutrition else 0
    protein_pct = min(100, int(protein_current / protein_target * 100)) if protein_target > 0 else 0
    st.progress(protein_pct / 100, text=f"{protein_current:.0f}g / {protein_target:.0f}g ({protein_pct}%)")

    with st.expander("记录蛋白质摄入"):
        tab1, tab2 = st.tabs(["描述食物", "直接输入克数"])

        with tab1:
            food_desc = st.text_input(
                label="描述食物",
                placeholder="例：两个鸡蛋、一杯牛奶、200g鸡胸肉",
                label_visibility="collapsed",
                key="food_desc_input"
            )
            if st.button("AI估算并记录", key="ai_estimate_btn"):
                protein_g = estimate_protein_from_text(food_desc)
                save_nutrition_log(user_id, protein_g, food_desc)
                st.success(f"估算蛋白质 {protein_g:.0f}g，已记录")
                st.rerun()

        with tab2:
            protein_g = st.number_input("蛋白质克数", 0.0, 300.0, step=5.0, key="protein_direct")
            note = st.text_input("备注", placeholder="鸡胸肉+蛋白粉", key="protein_note")
            if st.button("记录", key="protein_record_btn"):
                save_nutrition_log(user_id, protein_g, note)
                st.success(f"已记录 {protein_g:.0f}g")
                st.rerun()

    st.divider()

    # ─── 1.5 AI 教练对话窗口 ─────────────────────────
    st.markdown("#### 💬 问教练")

    if "home_chat_history" not in st.session_state:
        st.session_state.home_chat_history = []

    for msg in st.session_state.home_chat_history[-8:]:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    user_input = st.chat_input(
        "问我任何健身问题，或者告诉我你遇到了什么困难..."
    )

    if user_input:
        st.session_state.home_chat_history.append({
            "role": "user", "content": user_input
        })
        with st.spinner("教练思考中..."):
            # 合并 user 中的 name 到 profile
            profile_with_name = dict(profile or {})
            profile_with_name["name"] = user.get("name", "用户")
            response = home_coach_agent(user_input, user_id, profile_with_name)
        st.session_state.home_chat_history.append({
            "role": "assistant", "content": response
        })
        st.rerun()
