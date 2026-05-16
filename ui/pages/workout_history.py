import streamlit as st
import json
from database.db import get_recent_logs, save_workout_note
from itertools import groupby


def render_workout_history(user_id: str):
    st.title("📊 训练记录")

    if st.button("← 返回首页"):
        st.session_state.page = "home"
        st.rerun()

    logs = get_recent_logs(user_id, days=90)

    if not logs:
        st.info("暂无训练记录，完成第一次训练后会在这里显示。")
        return

    # 按月分组
    def get_month(log):
        return str(log["log_date"])[:7]

    logs_sorted = sorted(
        logs, key=lambda x: x["log_date"], reverse=True
    )

    for month, group_iter in groupby(logs_sorted, key=get_month):
        year, mon = month.split("-")
        st.markdown(f"### {year}年{int(mon)}月")
        group = list(group_iter)

        for idx, log in enumerate(group):
            actual_json_str = log.get("actual_json") or "[]"
            try:
                actual = json.loads(actual_json_str)
            except (json.JSONDecodeError, TypeError):
                actual = []
            date_str = str(log["log_date"])
            log_id = log.get("id") or f"{date_str}_{idx}"
            completion = log.get("completion_rate", 0)
            is_override = log.get("is_override", False)

            # 卡片标题
            tag = "⚡ 临时调整" if is_override else ""
            label = (
                f"{date_str}  {tag}  "
                f"完练率 {completion*100:.0f}%"
            )

            with st.expander(label):

                # 动作记录
                if actual and isinstance(actual, list):
                    for ex in actual:
                        if not isinstance(ex, dict):
                            continue
                        name = ex.get("name", "")
                        weight = ex.get("actual_weight") or ex.get("weight_kg") or 0
                        sets = ex.get("sets_done") or ex.get("sets") or 0
                        reps = ex.get("last_reps") or ex.get("reps") or "-"
                        feel = ex.get("feel", "")
                        feel_icon = {
                            "有余力": "💪",
                            "刚好力竭": "✅",
                            "没完成": "❌",
                        }.get(feel, "")

                        if name:
                            weight_str = f"{weight}kg" if weight else "重量未记录"
                            sets_str = f"{sets}组" if sets else "-组"
                            reps_str = f"×{reps}次" if reps != "-" else ""
                            st.write(
                                f"**{name}**　"
                                f"{weight_str}　"
                                f"{sets_str}{reps_str}　"
                                f"{feel_icon}"
                            )
                else:
                    # actual_json 为空，尝试显示计划内容作为参考
                    planned_json_str = log.get("planned_json") or "[]"
                    try:
                        planned = json.loads(planned_json_str)
                        exercises = planned.get("exercises", []) if isinstance(planned, dict) else (planned if isinstance(planned, list) else [])
                    except Exception:
                        exercises = []

                    if exercises:
                        st.caption("（实际记录未找到，显示计划内容）")
                        for ex in exercises:
                            if isinstance(ex, dict):
                                name = ex.get("name", "")
                                sets = ex.get("sets", "-")
                                reps = ex.get("reps_range") or ex.get("reps", "-")
                                weight = ex.get("weight_kg", 0)
                                if name:
                                    st.write(
                                        f"**{name}**　"
                                        f"{weight}kg　"
                                        f"{sets}组 × {reps}次"
                                    )
                    else:
                        st.caption("暂无动作记录")

                st.divider()

                # 今日状态
                col1, col2, col3 = st.columns(3)
                col1.metric("睡眠", f"{log.get('sleep_score', '-')}/10")
                col2.metric("压力", f"{log.get('stress_score', '-')}/10")
                col3.metric("疲劳", f"{log.get('fatigue_score', '-')}/10")

                # 心得备注输入框（用 log_id 保证 key 唯一）
                note_key = f"note_{log_id}"
                save_key = f"save_{log_id}"
                existing_note = log.get("note", "")

                note = st.text_area(
                    "训练心得 / 备注",
                    value=existing_note,
                    placeholder=(
                        "记录今天的感受、发现的问题、"
                        "下次要注意的事项..."
                    ),
                    height=80,
                    key=note_key,
                    label_visibility="collapsed",
                )
                if st.button("保存备注", key=save_key):
                    save_workout_note(log_id, note)
                    st.success("已保存")
