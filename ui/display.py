import streamlit as st
from knowledge.rag import search_exercises
from knowledge.exercises import EXERCISE_LIBRARY
from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODEL_NAME

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

MAX_REPLANS = 2


def _find_exercise_detail(name: str) -> dict | None:
    for ex in EXERCISE_LIBRARY:
        if ex["name_cn"] == name or ex["name_en"].lower() in name.lower():
            return ex
    return None


def render_exercise_card(exercise: dict, index: int, total: int, replan_count: int) -> str | None:
    ex_detail = _find_exercise_detail(exercise.get("name", ""))

    progress_pct = int((index + 1) / total * 100) if total > 0 else 0
    st.progress(progress_pct / 100, text=f"训练进度：{index + 1}/{total}")

    st.markdown(f"### {exercise.get('name', '')}")
    col1, col2, col3 = st.columns(3)
    col1.metric("组数", exercise.get("sets", 3))
    col2.metric("次数", exercise.get("reps", "8-12"))
    col3.metric("建议重量", f"{exercise.get('weight_kg', 0)}kg")

    if ex_detail:
        with st.expander("动作细节详解"):
            st.markdown("**主要肌肉：**" + "、".join(ex_detail["primary_muscles"]))
            st.markdown("**要点：**")
            for p in ex_detail["key_points"]:
                st.markdown(f"- {p}")
            st.markdown("**常见错误：**")
            for m in ex_detail["common_mistakes"]:
                st.markdown(f"- {m}")
            st.markdown("**提示口诀：**" + "、".join(ex_detail["cues"]))

    col_a, col_b, col_c = st.columns([2, 2, 2])
    result = None

    with col_a:
        if st.button("⬅ 上一个", key=f"prev_{index}", disabled=(index == 0)):
            result = "prev"
    with col_c:
        if st.button("下一个动作 ➡", key=f"next_{index}", disabled=(index >= total - 1)):
            result = "next"

    st.markdown("---")

    with st.expander("💬 问教练"):
        question = st.text_input("关于这个动作你有什么问题？", key=f"q_{index}", placeholder="例如：这个动作怎么呼吸？")
        if question:
            with st.spinner("教练正在思考..."):
                rag_results = search_exercises(question)
                context = "\n".join(rag_results) if rag_results else "无相关参考信息"
                try:
                    resp = client.chat.completions.create(
                        model=MODEL_NAME,
                        messages=[
                            {"role": "system", "content": "你是专业健身教练，用中文简洁回答动作相关问题。控制在100字以内。"},
                            {"role": "user", "content": f"动作：{exercise.get('name', '')}\n问题：{question}\n参考：{context}"},
                        ],
                        temperature=0.7,
                    )
                    answer = resp.choices[0].message.content
                except Exception:
                    answer = "加载中，请稍后再试..."
                st.info(answer)

    st.markdown("### 动作完成情况")
    with st.container():
        reason_col, done_col = st.columns([2, 1])
        with reason_col:
            if total > 0:
                can_replan = replan_count < MAX_REPLANS
                if not can_replan or index >= total - 1:
                    st.warning("已达最大调整次数，可结束训练")
                replan_options = ["太重", "太累", "部位不舒服", "没时间"]
                selected_reason = st.selectbox(
                    "如果动作未完成，请选择原因",
                    [""] + replan_options if can_replan else [""],
                    key=f"replan_reason_{index}",
                    disabled=not can_replan,
                )
                if selected_reason:
                    result = f"replan:{selected_reason}"
        with done_col:
            st.write("")
            if index >= total - 1 or replan_count >= MAX_REPLANS:
                if st.button("✅ 完成今日训练", key=f"done_{index}", type="primary"):
                    result = "done"

    return result


def render_training_summary(log_data: dict, new_prs: list):
    st.subheader("🎉 今日训练总结")

    rate = log_data.get("completion_rate", 0)
    if rate >= 0.9:
        st.success(f"**完练率：{int(rate * 100)}%** — 非常棒，高质量完成！")
    elif rate >= 0.7:
        st.info(f"**完练率：{int(rate * 100)}%** — 不错，基本完成了目标。")
    else:
        st.warning(f"**完练率：{int(rate * 100)}%** — 今天状态一般，下次继续努力。")

    if new_prs:
        st.balloons()
        st.success(f"🎉 **新PR突破！** {'、'.join(new_prs)} - 你又变强了！")

    completed = log_data.get("completed_exercises", [])
    if completed:
        total_volume = sum(
            (e.get("actual_weight") or e.get("weight_kg") or 0) * (e.get("sets_done") or e.get("sets") or 1)
            for e in completed
        )
        st.metric("总训练容量", f"{int(total_volume)} kg")

    st.info(log_data.get("agent_response", "今天辛苦了，好好休息！"))


def render_macro_plan_overview(macro_plan: dict):
    if not macro_plan:
        st.info("暂无长期训练计划。请先完成个人信息设置。")
        return

    split_names = {"PPL_3": "三分化（Push/Pull/Legs）", "UL_4": "四分化（Upper/Lower）", "PPL_5": "五分化高频版"}
    split_key = macro_plan.get("split", "")
    st.subheader(f"当前分化方案：{split_names.get(split_key, split_key)}")

    weeks = macro_plan.get("weeks", [])
    current_week = macro_plan.get("current_week", 1)

    for w in weeks:
        week_num = w.get("week", 1)
        phase = w.get("phase", "accumulation")
        phase_label = "积累期" if phase == "accumulation" else "减载期"
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
