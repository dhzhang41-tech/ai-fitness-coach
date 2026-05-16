import streamlit as st
import json
from database.db import get_user_profile


def _render_days_format(macro: dict, phase: str, week: int, start_date: str):
    """渲染 plan_edit 手动输入格式：{"days": [...], "split_type": "PPL_3"}"""
    split_names = {
        "PPL_3": "三分化（Push/Pull/Legs）",
        "UL_4": "四分化（Upper/Lower）",
        "PPL_5": "五分化高频版",
    }
    split_type = macro.get("split_type", "")
    if split_type:
        st.markdown(f"**分化方案：** {split_names.get(split_type, split_type)}")

    days = macro.get("days", [])
    if not days:
        st.info("计划内容为空，请重新输入。")
        return

    for day in days:
        day_name = day.get("day_name", "训练日")
        exercises = day.get("exercises", [])

        with st.expander(f"📅 {day_name}", expanded=True):
            if not exercises:
                st.caption("暂无动作")
                continue

            for ex in exercises:
                name = ex.get("name", "未知动作")
                sets = ex.get("sets") or "-"
                reps = ex.get("reps_range") or ex.get("reps") or "-"
                weight = ex.get("weight_kg")

                weight_str = f"{weight}kg" if weight else "重量待定"
                st.write(f"**{name}**　{sets}组 × {reps}次　{weight_str}")


def _render_weeks_format(macro: dict):
    """渲染 plan_agent 自动生成格式：{"split": "PPL_3", "weeks": [...]}"""
    split_names = {
        "PPL_3": "三分化（Push/Pull/Legs）",
        "UL_4": "四分化（Upper/Lower）",
        "PPL_5": "五分化高频版",
    }
    split_key = macro.get("split", "")
    if split_key:
        st.markdown(f"**分化方案：** {split_names.get(split_key, split_key)}")

    weeks = macro.get("weeks", [])
    current_week = macro.get("current_week", 1)

    for w in weeks:
        week_num = w.get("week", 1)
        phase_label = "积累期" if w.get("phase") == "accumulation" else "减载期"
        is_current = week_num == current_week

        with st.container():
            col1, col2 = st.columns([3, 1])
            with col1:
                marker = "▶ " if is_current else ""
                st.markdown(f"**{marker}第{week_num}周 - {phase_label}**")
                for day in w.get("days", []):
                    day_key = day.get("day_key", "")
                    exercises = ", ".join(e["name"] for e in day.get("exercises", []))
                    st.text(f"  {day_key}: {exercises}")
            with col2:
                if is_current:
                    st.markdown("**`当前周`**")
            st.divider()


def render_plan_overview(user_id: str):
    st.title("📋 我的计划")

    if st.button("← 返回首页"):
        st.session_state.page = "home"
        st.rerun()

    profile = get_user_profile(user_id)
    if not profile:
        st.warning("未找到用户档案")
        return

    macro_json = profile.get("macro_plan_json")
    if not macro_json:
        st.info("还没有训练计划，请先在「训练计划调整」里输入计划。")
        if st.button("去创建计划"):
            st.session_state.page = "plan_edit"
            st.rerun()
        return

    try:
        macro = json.loads(macro_json)
    except (json.JSONDecodeError, TypeError):
        st.error("计划数据格式异常，请重新生成计划。")
        return

    # 展示周期状态
    phase = profile.get("macro_phase", "accumulation")
    week = profile.get("macro_week", 1)
    start_date = profile.get("macro_start_date", "")

    phase_cn = {
        "accumulation": "积累期",
        "deload": "减载期",
        "strength_test": "力量测试期",
    }.get(phase, phase)

    st.markdown(f"#### 当前周期：{phase_cn} 第 {week} 周")
    if start_date:
        st.caption(f"本周期开始于 {start_date}")

    st.divider()

    # 判断格式并渲染
    if "weeks" in macro:
        _render_weeks_format(macro)
    elif "days" in macro:
        _render_days_format(macro, phase, week, start_date)
    else:
        st.info("计划内容格式无法识别，请重新输入。")

    st.divider()

    if st.button("✏️ 调整训练计划", use_container_width=True):
        st.session_state.page = "plan_edit"
        st.rerun()
