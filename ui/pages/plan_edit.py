import streamlit as st
import json
from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODEL_NAME
from database.db import (
    get_user_profile, update_macro_plan,
    get_user
)
from knowledge.exercises import EXERCISE_LIBRARY

# 标准动作名列表（从 EXERCISE_LIBRARY 提取）
STANDARD_EXERCISE_NAMES = [
    v["name_cn"] for v in EXERCISE_LIBRARY
]


def normalize_plan_input(raw_text: str) -> dict:
    """
    输入：用户手写的训练计划文本
    输出：标准化后的计划 JSON

    AI 负责：
    1. 把非标准动作名映射到数据库标准名
       （平板杠铃卧推 → 卧推）
    2. 解析出动作、组数、次数、重量
    3. 返回结构化 JSON

    返回格式：
    {
        "days": [
            {
                "day_name": "Push",
                "exercises": [
                    {
                        "name": "卧推",
                        "sets": 5,
                        "reps": "5",
                        "weight_kg": 100.0
                    }
                ]
            }
        ]
    }
    """
    standard_names_str = "、".join(STANDARD_EXERCISE_NAMES)

    client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
    )

    system_prompt = f"""你是训练计划格式化助手。
用户输入手写的训练计划，你需要：

1. 将动作名称映射到以下标准名称之一：
   {standard_names_str}
   如果找不到完全匹配的，选最接近的标准名称。

2. 解析出每个动作的组数、次数、重量。

3. 识别休息日：
   如果某天写的是「休息」「rest」「休息日」
   或者没有任何动作，将其解析为休息日。

4. 输出严格的 JSON 格式，不要有任何其他文字。

输出格式：
{{
    "days": [
        {{
            "day_name": "Upper A",
            "exercises": [
                {{
                    "name": "卧推",
                    "sets": 4,
                    "reps_range": "6",
                    "weight_kg": 80.0
                }}
            ]
        }},
        {{
            "day_name": "休息",
            "exercises": []
        }}
    ]
}}

规则：
- 有动作的训练日：day_name 写训练日名称
- 休息日：day_name 固定写「休息」，exercises 为空列表
- 次数可以是范围如「8-12」或固定次数如「6」
- 没有写重量时，weight_kg 填 null
- 没有写组数时，sets 填 null
- 体重类动作（如引体向上体重）weight_kg 填 null
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": raw_text},
        ],
        max_tokens=1000,
        temperature=0,
    )

    try:
        content = response.choices[0].message.content.strip()
        # 清理可能的 markdown 代码块标记
        content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(content)
    except Exception:
        return {"days": [], "error": "解析失败，请检查输入格式"}


def detect_split_type(plan: dict) -> str:
    days = plan.get("days", [])
    day_count = len(days)
    if day_count <= 3:
        return "PPL_3"
    elif day_count == 4:
        return "UL_4"
    else:
        return "PPL_5"


def render_plan_edit(user_id: str):
    st.title("✏️ 训练计划调整")

    if st.button("← 返回首页"):
        st.session_state.page = "home"
        st.rerun()

    st.caption(
        "直接输入你的训练计划，AI 会自动格式化并匹配到标准动作名。"
        "你确认无误后保存为新的长期计划。"
    )

    # 输入区域
    st.markdown("#### 输入训练计划")
    st.caption(
        "支持自由格式，例如：\n"
        "Push日：平板杠铃卧推 5×5 100kg，"
        "上斜哑铃卧推 4×12 30kg，侧平举 3×15\n"
        "Pull日：杠铃划船 4×8，高位下拉 4×10..."
    )

    raw_input = st.text_area(
        "训练计划",
        height=200,
        placeholder=(
            "Push日：\n"
            "平板杠铃卧推 5×5 100kg\n"
            "上斜哑铃卧推 4×12 30kg\n"
            "绳索飞鸟 3×15\n\n"
            "Pull日：\n"
            "杠铃划船 4×8 80kg\n"
            "高位下拉 4×10\n"
            "哑铃弯举 3×12 15kg\n\n"
            "Legs日：\n"
            "深蹲 5×5 90kg\n"
            "腿举 4×12\n"
            "罗马尼亚硬拉 3×10 70kg"
        ),
        label_visibility="collapsed",
    )

    if st.button("AI 格式化", type="primary", disabled=not raw_input):
        with st.spinner("正在解析并标准化..."):
            result = normalize_plan_input(raw_input)
            st.session_state.parsed_plan = result

    # 展示解析结果
    if "parsed_plan" in st.session_state:
        plan = st.session_state.parsed_plan

        if plan.get("error"):
            st.error(f"解析出错：{plan['error']}")
        elif not plan.get("days"):
            st.warning("未能识别出训练计划，请检查格式")
        else:
            st.markdown("#### 解析结果（请确认）")

            all_ok = True
            for day in plan["days"]:
                day_name = day.get("day_name", "")
                exercises = day.get("exercises", [])

                if day_name == "休息" or not exercises:
                    st.markdown(f"**{day_name if day_name else '休息'}**")
                    st.caption("🛌 休息日")
                    st.divider()
                    continue

                st.markdown(f"**{day_name}**")
                for ex in exercises:
                    name = ex.get("name", "")
                    sets = ex.get("sets", "?")
                    reps = ex.get("reps_range") or ex.get("reps", "?")
                    weight = ex.get("weight_kg")
                    weight_str = f"{weight}kg" if weight else "重量待定"
                    is_standard = name in STANDARD_EXERCISE_NAMES
                    icon = "✅" if is_standard else "⚠️"
                    if not is_standard:
                        all_ok = False

                    st.write(
                        f"{icon} **{name}**　"
                        f"{sets}组 × {reps}次　{weight_str}"
                    )

                    if not is_standard:
                        st.caption(
                            f"⚠️「{name}」不在标准动作库中，"
                            f"建议手动修改"
                        )
                st.divider()

            if not all_ok:
                st.warning(
                    "部分动作未能匹配到标准名称，"
                    "建议修改后重新格式化，或联系教练确认。"
                )

            # 确认保存
            col1, col2 = st.columns(2)
            with col1:
                if st.button(
                    "✅ 确认保存为新计划",
                    type="primary",
                    use_container_width=True,
                ):
                    import uuid
                    from datetime import date
                    from database.db import get_macro_plan_raw

                    # 标准化格式后再保存
                    plan_to_save = {
                        "days": plan.get("days", []),
                        "split_type": detect_split_type(plan),
                        "created_at": str(date.today()),
                    }

                    update_macro_plan(
                        user_id=user_id,
                        phase="accumulation",
                        week=1,
                        plan_json=json.dumps(
                            plan_to_save, ensure_ascii=False
                        ),
                        start_date=str(date.today()),
                    )

                    # 临时调试：保存后立刻读回来验证
                    saved = get_macro_plan_raw(user_id)
                    if saved:
                        st.success(f"新训练计划已保存（数据长度：{len(saved)} 字符）！")
                    else:
                        st.error("保存失败：数据库未写入，请检查 update_macro_plan 函数")

                    del st.session_state.parsed_plan
                    st.session_state.page = "home"
                    st.rerun()
            with col2:
                if st.button(
                    "重新输入",
                    use_container_width=True,
                ):
                    del st.session_state.parsed_plan
                    st.rerun()
