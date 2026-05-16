import streamlit as st
import pandas as pd
from database.db import (
    get_user, get_user_profile, get_prs, get_pr_trend,
    calculate_age, calculate_training_years,
    update_weight, upsert_pr, update_profile_field,
)


def render_profile(user_id: str):
    st.title("👤 个人档案")

    user = get_user(user_id)
    profile = get_user_profile(user_id)
    if not user or not profile:
        st.error("用户信息不存在")
        return

    tab1, tab2 = st.tabs(["基本信息", "三大项记录"])

    with tab1:
        # 推算年龄和训练年限
        birth_date_str = profile.get("birth_date")
        training_start_str = profile.get("training_start_date")

        age = calculate_age(birth_date_str) if birth_date_str else "未知"
        training_years = (
            calculate_training_years(training_start_str)
            if training_start_str else "未知"
        )

        # 只读展示
        st.markdown("#### 基本信息")
        col1, col2 = st.columns(2)
        col1.metric("姓名", user.get("name", "-"))
        col2.metric("身高", f"{profile.get('height_cm', '-')} cm")
        col1.metric("年龄", f"{age} 岁")
        col2.metric("训练年限", f"{training_years} 年")

        st.divider()

        # 可编辑：体重
        st.markdown("#### 更新体重")
        current_weight = profile.get("weight_kg", 70.0)

        with st.form("update_weight_form"):
            new_weight = st.number_input(
                "当前体重 (kg)",
                min_value=30.0,
                max_value=200.0,
                value=float(current_weight),
                step=0.5,
                key="profile_weight_input",
            )
            if st.form_submit_button("更新体重"):
                update_weight(user_id, new_weight)
                st.success(f"体重已更新为 {new_weight} kg")
                st.rerun()

    with tab2:
        st.markdown("#### 手动录入最大重量")
        st.caption(
            "录入你目前能完成的最大重量和对应次数，"
            "系统会用这个数据计算训练建议重量。"
        )

        BIG_THREE = ["深蹲", "卧推", "硬拉"]

        # 获取现有 PR 数据
        existing_prs = {
            p["exercise_name"]: p
            for p in get_prs(user_id)
            if p["exercise_name"] in BIG_THREE
        }

        with st.form("pr_input_form"):
            pr_inputs = {}
            for exercise in BIG_THREE:
                st.markdown(f"**{exercise}**")
                existing = existing_prs.get(exercise, {})
                col1, col2 = st.columns(2)
                with col1:
                    weight = st.number_input(
                        "重量 (kg)",
                        min_value=0.0,
                        max_value=500.0,
                        value=float(existing.get("weight_kg", 0.0)),
                        step=2.5,
                        key=f"pr_weight_{exercise}",
                    )
                with col2:
                    reps = st.number_input(
                        "次数",
                        min_value=1,
                        max_value=20,
                        value=int(existing.get("reps", 1)),
                        step=1,
                        key=f"pr_reps_{exercise}",
                    )
                pr_inputs[exercise] = {
                    "weight_kg": weight,
                    "reps": reps,
                }

            if st.form_submit_button(
                "保存三大项记录", use_container_width=True
            ):
                for exercise, data in pr_inputs.items():
                    if data["weight_kg"] > 0:
                        upsert_pr(
                            user_id,
                            exercise,
                            data["weight_kg"],
                            data["reps"],
                        )
                        # 同步更新 user_profiles 里的 1RM 字段
                        field_map = {
                            "深蹲": "squat_1rm",
                            "卧推": "bench_1rm",
                            "硬拉": "deadlift_1rm",
                        }
                        field = field_map.get(exercise)
                        if field:
                            update_profile_field(
                                user_id, field, data["weight_kg"]
                            )
                st.success("三大项记录已保存")
                st.rerun()

        st.divider()

        # 展示历史趋势
        st.markdown("#### 重量趋势")
        for exercise in BIG_THREE:
            prs = get_pr_trend(user_id, exercise, weeks=24)
            if len(prs) >= 2:
                df = pd.DataFrame(prs)
                df = df.rename(columns={
                    "pr_date": "日期",
                    "weight_kg": "重量(kg)",
                })
                st.caption(exercise)
                st.line_chart(df.set_index("日期")["重量(kg)"])
            elif len(prs) == 1:
                st.caption(
                    f"{exercise}：{prs[0]['weight_kg']}kg "
                    f"× {prs[0]['reps']}次（至少录入两次才能显示趋势）"
                )
            else:
                st.caption(f"{exercise}：暂无记录")

    if st.button("返回首页"):
        st.session_state.page = "home"
        st.rerun()
