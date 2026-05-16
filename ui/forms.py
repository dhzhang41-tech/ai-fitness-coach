import streamlit as st
from datetime import date


def render_onboarding_form() -> dict | None:
    st.markdown("## 🏋️ 欢迎使用 AI 增肌教练")
    st.markdown(
        "让我先了解一下你的情况，然后为你生成一份**个性化训练周期计划**。"
    )

    with st.form("onboarding_form"):
        st.subheader("基本信息")
        name = st.text_input("你的名字 *", value="", placeholder="输入你的称呼")
        col1, col2 = st.columns(2)
        with col1:
            birth_date = st.date_input(
                "出生日期",
                value=date(1995, 1, 1),
                min_value=date(1950, 1, 1),
                max_value=date(2010, 12, 31),
            )
        with col2:
            height = st.number_input("身高 (cm)", min_value=100.0, max_value=250.0, value=175.0, step=0.5)

        weight = st.number_input("体重 (kg)", min_value=30.0, max_value=200.0, value=75.0, step=0.5)

        st.subheader("训练经验")
        col1, col2 = st.columns(2)
        with col1:
            training_start_date = st.date_input(
                "开始训练时间",
                value=date(2023, 1, 1),
                min_value=date(2000, 1, 1),
                max_value=date.today(),
            )
        with col2:
            days_per_week = st.selectbox(
                "每周可以训练几天",
                options=[3, 4, 5],
                index=1,
            )

        goal = st.selectbox(
            "当前目标",
            options=["hypertrophy", "strength"],
            format_func=lambda x: "增肌（肌肥大）" if x == "hypertrophy" else "增力",
            index=0,
        )

        st.subheader("三大项 1RM 估计（可选）")
        st.caption("如果不知道或没测过可以留默认值，系统会随训练自动调整。")
        col1, col2, col3 = st.columns(3)
        with col1:
            squat_1rm = st.number_input("深蹲 1RM (kg)", min_value=0.0, max_value=300.0, value=100.0, step=2.5,
                                        help="0表示未测量")
        with col2:
            bench_1rm = st.number_input("卧推 1RM (kg)", min_value=0.0, max_value=200.0, value=80.0, step=2.5,
                                        help="0表示未测量")
        with col3:
            deadlift_1rm = st.number_input("硬拉 1RM (kg)", min_value=0.0, max_value=300.0, value=120.0, step=2.5,
                                           help="0表示未测量")

        submitted = st.form_submit_button("✨ 生成我的训练计划", type="primary", use_container_width=True)

    if submitted and name.strip():
        return {
            "name": name.strip(),
            "birth_date": str(birth_date),
            "training_start_date": str(training_start_date),
            "height_cm": height,
            "weight_kg": weight,
            "days_per_week": days_per_week,
            "current_goal": goal,
            "squat_1rm": max(squat_1rm, 20),
            "bench_1rm": max(bench_1rm, 15),
            "deadlift_1rm": max(deadlift_1rm, 30),
        }
    if submitted:
        st.error("请输入你的名字")
    return None


def render_readiness_form() -> dict | None:
    st.subheader("今日状态评估")
    st.markdown("在开始训练之前，请先评估一下今天的身体状态。")

    with st.form("readiness_form"):
        sleep = st.slider("睡眠质量", 1, 10, 7, 1,
                          help="1=极差（<5小时），10=极好（>8小时）")
        stress = st.slider("精神压力", 1, 10, 5, 1,
                           help="1=完全放松，10=压力极大")
        fatigue = st.slider("身体疲劳感", 1, 10, 5, 1,
                            help="1=精力充沛，10=非常疲惫")

        pain_options = ["无", "腰部", "膝盖", "肩膀", "手腕", "其他"]
        pain = st.multiselect("今日有无部位疼痛", pain_options, default=["无"])

        submitted = st.form_submit_button("开始训练", type="primary", use_container_width=True)

    if submitted:
        if "无" in pain and len(pain) > 1:
            pain.remove("无")
        return {
            "sleep": sleep,
            "stress": stress,
            "fatigue": fatigue,
            "pain_areas": [p for p in pain if p != "无"],
        }
    return None


def parse_reps_to_int(reps_value) -> int:
    """把 reps/sets 字段转成整数。'8-12' 取第一个数，默认 8。"""
    try:
        if isinstance(reps_value, int):
            return reps_value
        if isinstance(reps_value, float):
            return int(reps_value)
        if isinstance(reps_value, str):
            return int(reps_value.split("-")[0].strip())
    except (ValueError, AttributeError, IndexError):
        pass
    return 8


def render_workout_log_form(plan: dict) -> dict | None:
    st.subheader("训练记录")
    st.markdown("请记录每个动作的完成情况。")

    exercises = plan.get("exercises", [])
    if not exercises:
        st.info("今日没有计划动作。")
        return None

    results = []
    with st.form("workout_log_form"):
        for i, ex in enumerate(exercises):
            st.markdown(f"**{i+1}. {ex['name']}** — 计划：{ex.get('sets', 3)}组 × {ex.get('reps', '8-12')}次")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                sets_done = st.number_input("完成组数", min_value=0, max_value=10, value=parse_reps_to_int(ex.get("sets", 3)), key=f"sets_{i}")
            with col2:
                actual_weight = st.number_input("最后组重量(kg)", min_value=0.0, value=float(ex.get("weight_kg", 0)), step=2.5, key=f"weight_{i}")
            with col3:
                last_reps = st.number_input("最后一组完成次数", min_value=0, max_value=50, value=parse_reps_to_int(ex.get("reps", 8)), key=f"last_reps_{i}")
            with col4:
                feeling = st.selectbox("感受", ["有余力", "刚好力竭", "没完成"], key=f"feeling_{i}")
            results.append({
                "name": ex["name"],
                "sets_done": sets_done,
                "actual_weight": actual_weight,
                "last_reps": last_reps,
                "feeling": feeling,
            })

        submitted = st.form_submit_button("保存训练日志", type="primary", use_container_width=True)

        if submitted:
            return {"exercises": results}
    return None
