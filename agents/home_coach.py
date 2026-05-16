from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODEL_NAME
from database.db import get_recent_logs, get_prs, get_user_profile
from knowledge.rag import (
    search_training_principles,
    search_exercises,
    search_recovery_knowledge,
    search_physiology,
    search_nutrition,
    search_by_decision_type,
    search_all,
)
from agents.prompts import COACH_SYSTEM_PROMPT, determine_training_level

PLAN_CONSULT_SIGNALS = [
    "停滞", "没进步", "瓶颈", "做不上去", "卡住了",
    "加不了重", "一直失败", "进步慢", "练不动",
    "渐进超负荷做不到", "重量上不去", "平台期",
]


def detect_consult_intent(message: str) -> bool:
    return any(s in message for s in PLAN_CONSULT_SIGNALS)


def classify_query_intent(message: str) -> str:
    """判断用户查询意图，返回七种类型之一"""
    msg = message.lower()

    technique_kws = [
        "怎么做", "怎么练", "动作", "姿势", "卧推",
        "深蹲", "硬拉", "划船", "引体", "推举",
        "飞鸟", "弯举", "侧平举", "臀推", "腿举",
        "腿弯举", "下拉", "动作要领", "标准动作",
        "手腕", "肩胛", "膝盖方向", "落点",
    ]
    fix_kws = [
        "停滞", "没进步", "瓶颈", "加不了重",
        "做不上去", "卡住了", "练不动", "平台期",
        "怎么突破", "要不要调整", "哪里错了",
        "姿势不对", "受伤", "疼", "痛",
    ]
    why_kws = [
        "为什么", "原理", "机制", "怎么理解",
        "有什么用", "科学依据", "研究", "证据",
        "神经适应", "肌肉合成", "激素",
    ]
    when_kws = [
        "什么时候", "该不该", "需不需要",
        "多久", "几周", "时机", "要不要",
        "适不适合", "可不可以",
    ]
    recovery_kws = [
        "睡眠", "睡不好", "减载", "deload",
        "疲劳", "恢复", "DOMS", "酸痛",
        "过度训练", "休息", "主动恢复",
    ]
    nutrition_kws = [
        "蛋白质", "蛋白", "热量", "卡路里",
        "碳水", "饮食", "吃什么", "补剂",
        "肌酸", "蛋白粉", "营养",
    ]

    if any(kw in msg for kw in fix_kws):
        return "fix"
    if any(kw in msg for kw in technique_kws):
        return "technique"
    # why/when 优先于 recovery/nutrition，因为"为什么""什么时候"是强意图信号
    if any(kw in msg for kw in why_kws):
        return "why"
    if any(kw in msg for kw in when_kws):
        return "when"
    if any(kw in msg for kw in recovery_kws):
        return "recovery"
    if any(kw in msg for kw in nutrition_kws):
        return "nutrition"
    return "general"


def smart_search(query: str, intent: str) -> list[str]:
    """根据意图选择最合适的检索策略"""
    if intent == "technique":
        results = search_exercises(query, n_results=3)
        results += search_by_decision_type(
            query, "how",
            collections=["exercise_technique"],
            n_results=2,
        )
    elif intent == "fix":
        results = search_by_decision_type(query, "fix", n_results=3)
        results += search_by_decision_type(
            query, "when",
            collections=["training_principles", "recovery_management"],
            n_results=2,
        )
    elif intent == "recovery":
        results = search_recovery_knowledge(query, n_results=3)
        results += search_physiology(query, n_results=2)
    elif intent == "nutrition":
        results = search_nutrition(query, n_results=3)
        results += search_by_decision_type(
            query, "how",
            collections=["nutrition_basics"],
            n_results=2,
        )
    elif intent == "why":
        results = search_physiology(query, n_results=3)
        results += search_by_decision_type(query, "why", n_results=2)
    elif intent == "when":
        results = search_by_decision_type(query, "when", n_results=3)
        results += search_training_principles(query, n_results=2)
    else:
        results = search_all(query, n_results_per_source=2)

    seen = set()
    deduped = []
    for r in results:
        if r and r not in seen:
            seen.add(r)
            deduped.append(r)
    return deduped[:5]


def home_coach_agent(
    user_input: str,
    user_id: str,
    profile: dict,
) -> str:

    # 1. 智能意图识别 + 精准检索
    intent = classify_query_intent(user_input)
    rag_results = smart_search(user_input, intent)
    rag_text = "\n---\n".join(rag_results) if rag_results else "暂无相关知识"

    # 2. 读取用户数据
    recent_logs = get_recent_logs(user_id, days=28)
    prs = get_prs(user_id)

    weight = profile.get("weight_kg", 70)
    bench = profile.get("bench_1rm", 0)
    squat = profile.get("squat_1rm", 0)
    deadlift = profile.get("deadlift_1rm", 0)

    bench_ratio = round(bench / weight, 2) if weight else 0
    squat_ratio = round(squat / weight, 2) if weight else 0
    deadlift_ratio = round(deadlift / weight, 2) if weight else 0

    avg_completion = (
        sum(l.get("completion_rate", 0) for l in recent_logs)
        / len(recent_logs)
        if recent_logs else 0
    )

    pr_text = "\n".join([
        f"{p['exercise_name']}: {p['weight_kg']}kg × {p['reps']}次"
        for p in prs
    ]) if prs else "暂无PR记录"

    training_stage = determine_training_level(profile, recent_logs)

    # 3. 判断意图，决定模式
    is_consult = detect_consult_intent(user_input)

    # 4. 构建 system prompt
    intent_labels = {
        "technique": "用户在问动作技术，重点给操作要点",
        "fix": "用户在问题诊断，先分析原因再给方案",
        "recovery": "用户在问恢复，结合其状态数据回答",
        "nutrition": "用户在问营养，给具体数字和建议",
        "why": "用户在问原理，解释机制但联系实际",
        "when": "用户在问时机，给明确的判断标准",
        "general": "一般问题，综合回答",
    }

    if is_consult:
        mode_instruction = """
用户遇到了训练瓶颈或计划问题，你需要：
1. 先分析用户的具体情况（结合他的训练数据）
2. 给出有科学依据的诊断（是训练量不足？恢复不够？
   还是需要调整周期？）
3. 给出具体的调整建议（比如：建议进入减载周，
   之后用退重法重新起步，具体重量从XX%1RM开始）
4. 最后告诉用户：可以在「训练计划调整」页面
   按照建议手动输入新计划

回答要有理有据，引用知识库中的原理，
但语气像一个了解你的教练，不要像在背教科书。
"""
    else:
        mode_instruction = """
用户在问健身知识或寻求建议。你需要：
1. 结合用户的实际情况（训练年限、当前水平）
   给出个性化的回答，不是泛泛而谈
2. 用知识库中的内容支撑你的回答
3. 语气专业但不刻板，像一个懂你的教练

如果是原理类问题（什么是渐进超负荷、为什么减载等），
先用一句话给出核心答案，再展开解释，
最后结合用户的情况说明对他意味着什么。
"""

    system_prompt = COACH_SYSTEM_PROMPT + f"""

══ 当前用户数据 ══
姓名：{profile.get('name', '用户')}
体重：{weight}kg
训练阶段判断：{training_stage}
力量比值：
  卧推/体重：{bench_ratio}
  深蹲/体重：{squat_ratio}
  硬拉/体重：{deadlift_ratio}
近28天训练次数：{len(recent_logs)}次
近28天平均完练率：{avg_completion:.0%}
当前目标：{profile.get('current_goal', '增肌')}
PR记录：
{pr_text}
"""

    system_prompt += f"""

══ 本次查询 ══
用户问题类型：{intent}
问题类型说明：{intent_labels.get(intent, '')}

相关知识库内容：
{chr(10).join([f"- {r[:200]}" for r in rag_results]) if rag_results else "（未检索到相关内容）"}

{mode_instruction}

重要规则：
- 回答控制在300字以内
- 遇到需要调整计划的情况，引导用户去「训练计划调整」页面
- 不要回答与健身完全无关的问题
- 所有建议必须基于用户的实际数据，不要给通用建议
"""

    client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
    )
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ],
        max_tokens=600,
        temperature=0.7,
    )
    return response.choices[0].message.content
