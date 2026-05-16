import json
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from agents.state import CoachState
from agents.orchestrator import orchestrator_node
from agents.plan_agent import plan_agent_node
from agents.adjust_agent import adjust_agent_node, assess_readiness
from agents.replan_agent import replan_agent_node
from agents.log_agent import log_agent_node
from database.db import get_user_profile


def build_graph():
    graph = StateGraph(CoachState)

    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("plan_agent", plan_agent_node)
    graph.add_node("adjust_agent", adjust_agent_node)
    graph.add_node("replan_agent", replan_agent_node)
    graph.add_node("log_agent", log_agent_node)

    graph.add_edge(START, "orchestrator")

    def route_after_orchestrator(state: CoachState) -> str:
        intent = state.get("intent", "")
        plan_needs_review = state.get("plan_needs_review", False)
        print(f"[graph.route] intent={intent!r}, plan_needs_review={plan_needs_review}")
        if intent == "review_macro_plan":
            print("[graph.route] → plan_agent")
            return "plan_agent"
        elif intent == "start_workout":
            if state.get("is_override"):
                print("[graph.route] → adjust_agent (override)")
                return "adjust_agent"
            else:
                print("[graph.route] → log_agent (normal workout)")
                return "log_agent"
        else:
            print(f"[graph.route] → END (unknown intent: {intent})")
            return END

    graph.add_conditional_edges("orchestrator", route_after_orchestrator)
    graph.add_edge("plan_agent", END)
    graph.add_edge("adjust_agent", "log_agent")
    graph.add_edge("replan_agent", END)
    graph.add_edge("log_agent", END)

    memory = MemorySaver()
    return graph.compile(checkpointer=memory)


coach_graph = build_graph()


def run_session(
    user_id: str,
    intent: str,
    form_data: dict = None,
    replan_reason: str = None,
    completed_exercises: list = None,
    current_plan: dict = None,
    replan_count: int = 0,
) -> dict:
    from langchain_core.messages import HumanMessage
    import traceback

    try:
        profile = get_user_profile(user_id)
    except Exception as e:
        error_msg = f"[graph.run_session] 读取用户档案失败: {e}\n{traceback.format_exc()}"
        print(error_msg)
        raise RuntimeError(f"读取用户档案失败: {e}") from e

    macro_plan = {}
    if profile and profile.get("macro_plan_json"):
        try:
            macro_plan = json.loads(profile["macro_plan_json"])
        except (json.JSONDecodeError, TypeError) as e:
            print(f"[graph.run_session] macro_plan_json 解析失败: {e}")
            macro_plan = {}

    initial_state = {
        "user_id": user_id,
        "user_name": "",
        "user_profile": profile or {},
        "intent": intent,  # 直接传入确定的 intent，orchestrator 不再重新分类
        "macro_plan": macro_plan,
        "plan_needs_review": False,
        "today_readiness": {},
        "is_override": False,
        "current_plan": current_plan or {},
        "completed_exercises": completed_exercises or [],
        "replan_count": replan_count,
        "replan_reason": replan_reason,
        "messages": [HumanMessage(content=intent)],
        "user_input": intent,
        "agent_response": "",
        "error": "",
    }

    if form_data:
        readiness = assess_readiness(
            form_data.get("sleep", 7),
            form_data.get("stress", 5),
            form_data.get("fatigue", 5),
        )
        readiness["pain_areas"] = form_data.get("pain_areas", [])
        initial_state["today_readiness"] = readiness
        initial_state["is_override"] = readiness["level"] != "normal"

    config = {"configurable": {"thread_id": user_id}}

    try:
        result = coach_graph.invoke(initial_state, config=config)
        print(f"[graph.run_session] 执行成功, intent={intent}")
        return result
    except Exception as e:
        error_msg = f"[graph.run_session] LangGraph 执行异常: {e}\n{traceback.format_exc()}"
        print(error_msg)
        raise RuntimeError(f"LangGraph 执行失败: {e}") from e
