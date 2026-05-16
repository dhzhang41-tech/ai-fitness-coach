import streamlit as st
from database.db import init_db, get_user, get_user_profile
from database.db import mark_plan_stale
from knowledge.rag import init_knowledge_base
from agents.orchestrator import check_auto_stagnation

st.set_page_config(
    page_title="AI 增肌教练",
    page_icon="💪",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_resource
def startup():
    init_db()
    init_knowledge_base()
    return True


startup()

# Session State 初始化
defaults = {
    "user_id": "test_user_001",
    "page": "init",
    "workout_step": "readiness_form",
    "current_exercise_index": 0,
    "completed_exercises": [],
    "replan_count": 0,
    "current_plan": {},
    "today_readiness": {},
    "is_override_setting": False,
    "onboarding_done": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

user_id = st.session_state.user_id

# 启动时自动检测停滞（只在有数据时执行）
try:
    profile = get_user_profile(user_id)
    if profile and profile.get("macro_plan_json"):
        if check_auto_stagnation(user_id):
            mark_plan_stale(user_id)
except Exception:
    pass

# ─── 跨天检测 ────────────────────────────────────────────
from datetime import date

today_str = str(date.today())

if "last_active_date" not in st.session_state:
    st.session_state.last_active_date = today_str

if st.session_state.last_active_date != today_str:
    # 日期变了，重置今日训练相关状态
    st.session_state.last_active_date = today_str
    st.session_state.workout_step = "readiness_form"
    st.session_state.current_exercise_index = 0
    st.session_state.completed_exercises = []
    st.session_state.replan_count = 0
    st.session_state.current_plan = {}
    st.session_state.today_readiness = {}
    # 不重置 home_chat_history，保留对话记录
    # 不重置 user_id，保留登录状态

# ─── 页面路由 ────────────────────────────────────────────
page = st.session_state.get("page", "init")

if page == "init":
    """首次打开：判断是否需要引导"""
    profile = get_user_profile(user_id)
    if profile and profile.get("macro_plan_json") and len(profile["macro_plan_json"]) > 10:
        # 已有完整数据，直接进首页
        st.session_state.page = "home"
        st.session_state.onboarding_done = True
    else:
        # 无数据或数据不完整，进引导
        st.session_state.page = "onboarding"
    st.rerun()

elif page == "onboarding":
    from ui.forms import render_onboarding_form
    from database.db import save_user, save_user_profile
    from agents.graph import run_session

    st.markdown(
        """
        <style>
        .block-container { max-width: 700px; padding-top: 2rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    result = render_onboarding_form()
    if result:
        name = result.pop("name")

        # 第1步：保存用户
        with st.spinner("保存用户信息..."):
            try:
                save_user(user_id, name)
                st.success("✅ 用户信息已保存")
            except Exception as e:
                st.error(f"❌ 保存用户失败: {e}")
                st.stop()

        # 第2步：保存档案
        with st.spinner("保存训练档案..."):
            try:
                save_user_profile(user_id, result)
                st.success("✅ 训练档案已保存")
            except Exception as e:
                st.error(f"❌ 保存训练档案失败: {e}")
                st.stop()

        # 第3步：生成长期计划
        with st.spinner("正在为你生成个性化训练计划..."):
            try:
                graph_result = run_session(user_id, "review_macro_plan")
                st.success("✅ run_session 执行完成")
            except Exception as e:
                st.error(f"❌ run_session 异常: {e}")
                import traceback
                st.code(traceback.format_exc())
                st.stop()

        # 第4步：验证计划是否成功写入
        with st.spinner("验证计划写入结果..."):
            try:
                verify_profile = get_user_profile(user_id)
                raw_json = verify_profile.get("macro_plan_json") if verify_profile else None
                if raw_json:
                    preview = raw_json[:200]
                else:
                    preview = "None"
                st.write(f"**macro_plan_json 原始内容（前200字符）:**")
                st.code(preview)
                st.write(f"**字段长度:** {len(raw_json) if raw_json else 0}")
            except Exception as e:
                st.error(f"❌ 读取数据库验证时出错: {e}")
                st.stop()

        has_plan = (
            verify_profile
            and verify_profile.get("macro_plan_json")
            and len(verify_profile["macro_plan_json"]) > 10
        )

        if has_plan:
            st.success("🎉 训练计划已生成！即将进入首页...")
            st.session_state.onboarding_done = True
            st.session_state.page = "home"
            st.rerun()
        else:
            st.error(
                "计划生成失败：训练计划未能正确保存到数据库。\n\n"
                "可能的原因：\n"
                "1. MySQL 连接异常，update_macro_plan 未正确写入\n"
                "2. DeepSeek API 调用超时导致计划生成中断\n"
                "3. 数据库字符集问题导致 JSON 被截断\n\n"
                "请检查上方日志定位具体原因，修复后刷新页面重试。"
            )

elif page == "home":
    from ui.pages.home import render_home
    render_home(user_id)

elif page == "workout":
    from ui.pages.workout import render_workout
    render_workout(user_id)

elif page == "profile":
    from ui.pages.profile import render_profile
    render_profile(user_id)

elif page == "plan_overview":
    from ui.pages.plan_overview import render_plan_overview
    render_plan_overview(user_id)

elif page == "workout_history":
    from ui.pages.workout_history import render_workout_history
    render_workout_history(user_id)

elif page == "plan_edit":
    from ui.pages.plan_edit import render_plan_edit
    render_plan_edit(user_id)

elif page == "adjust_macro":
    st.subheader("🔄 调整长期训练计划")
    profile = get_user_profile(user_id)
    has_plan = profile and profile.get("macro_plan_json") and len(profile["macro_plan_json"]) > 10
    if has_plan:
        st.write("系统将根据你的训练档案重新生成训练周期计划。当前计划将被替换。")
    else:
        st.info("你还没有训练计划，填写个人档案后即可自动生成。")
        if st.button("✏️ 去填写档案", type="primary"):
            st.session_state.page = "onboarding"
            st.rerun()
        if st.button("取消"):
            st.session_state.page = "home"
            st.rerun()
    if st.button("确认重新生成", type="primary"):
        from agents.graph import run_session
        from database.db import clear_plan_stale
        with st.spinner("正在生成新的训练计划..."):
            run_session(user_id, "review_macro_plan")
            clear_plan_stale(user_id)
        # 验证
        verify = get_user_profile(user_id)
        if verify and verify.get("macro_plan_json") and len(verify["macro_plan_json"]) > 10:
            st.success("长期计划已更新！")
            st.session_state.page = "home"
            st.rerun()
        else:
            st.error("计划更新失败，请检查数据库连接后重试。")
    if st.button("取消"):
        st.session_state.page = "home"
        st.rerun()
