from typing import TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages


class CoachState(TypedDict):
    # 用户基础
    user_id: str
    user_name: str
    user_profile: dict

    # 长期计划
    macro_plan: dict
    plan_needs_review: bool

    # 意图
    intent: str

    # 每日评估
    today_readiness: dict
    is_override: bool

    # 今日计划（执行层）
    current_plan: dict
    completed_exercises: list
    replan_count: int
    replan_reason: Optional[str]

    # 对话
    messages: Annotated[list, add_messages]
    user_input: str

    # Agent 输出
    agent_response: str
    error: str
