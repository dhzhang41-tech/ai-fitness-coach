# AI 增肌教练

> 基于 LangGraph Multi-Agent + RAG 的个性化增肌训练决策系统

不是健身聊天机器人，而是一个有科学依据、有个人记忆、
能随用户状态动态调整的**训练决策引擎**。

对齐 Keep AI 方向核心课题：
- 课题四：Multi-Agent 教练体系
- 课题六：基于 RAG 的知识检索问答

---

## 系统架构

```
用户输入
  ↓
Orchestrator（意图识别 + 用户档案读取）
  ↓                    ↓
Training Agent    Recovery Agent     ← 并行执行
（计划生成）       （状态评估）
  ↓                    ↓
        Log Agent（日志写入 + PR检测）
  ↓
LangGraph CoachState（共享状态）
  ↓
RAG 知识库（5个 Collection）+ MySQL + ChromaDB
```

---

## 核心技术决策

**1. 为什么用 Multi-Agent 而不是单个 LLM**

训练建议和恢复建议本质上是相互矛盾的约束：
Training Agent 关心"今天能练多少"，
Recovery Agent 关心"今天能不能练"。
单个 LLM 处理多角色会导致推理质量下降，
分 Agent 后每个只需专注自己的判断域。

**2. RAG 知识库按 decision_type 分层**

传统 RAG 只做语义检索，把"什么是渐进超负荷"和
"渐进超负荷停滞了怎么办"混在一起返回。
本项目给每个知识块打上 decision_type 标签
（what/why/how/when/fix），
结合意图识别精准过滤，
让"问题诊断类"问题只检索 fix 类知识块。

**3. 临时调整不写数据库**

用户状态差时的当日计划调整只存在 session state，
明天自动恢复长期计划，
保证长期训练逻辑不被单日状态污染。

**4. 循环周期索引替代自然周**

训练计划按完整循环存储（含休息日），
用 `(today - macro_start_date).days % 循环总天数`
计算今日应执行哪个分化，
支持三分化/四分化/五分化任意周期，不依赖自然周。

---

## 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| Agent 框架 | LangGraph 0.2+ | Multi-Agent 状态图 |
| LLM | DeepSeek API | 训练决策生成 |
| 向量库 | ChromaDB | RAG 语义检索（5个Collection）|
| 关系库 | MySQL | 用户档案、训练日志、PR记录 |
| 前端 | Streamlit | 交互界面 |

---

## RAG 知识库结构

```
training_principles   训练周期化、MEV/MRV、渐进超负荷
exercise_technique    20个核心动作技术细节
recovery_management   睡眠、减载、疲劳管理
physiology            增肌机制、神经适应、超量恢复
nutrition_basics      蛋白质需求、热量盈余、补剂
```

每个知识块包含 7 个结构化字段：
`id / topic / decision_type / trigger_keywords / source / confidence / content`

检索策略：意图识别 → 精准 Collection 定向检索 → decision_type 过滤 → top-5

---

## 快速开始

**环境要求**：Python 3.11+，MySQL 8.0+

```bash
git clone https://github.com/dhzhang41-tech/ai-fitness-coach.git
cd ai-fitness-coach

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

pip install -r requirements.txt

copy .env.example .env       # Windows
# cp .env.example .env       # Mac/Linux
# 编辑 .env 填入 DEEPSEEK_API_KEY 和 MYSQL_PASSWORD

python -m database.seed_data  # 初始化测试数据

streamlit run main.py
```

---

## 项目结构

```
ai-fitness-coach/
├── agents/
│   ├── state.py           # LangGraph CoachState
│   ├── orchestrator.py    # 意图识别 + 路由
│   ├── training_agent.py  # 训练计划生成
│   ├── recovery_agent.py  # 状态评估 + 恢复建议
│   ├── adjust_agent.py    # 当日临时调整（不写DB）
│   ├── replan_agent.py    # 训练中重规划（上限2次）
│   ├── log_agent.py       # 日志写入 + PR检测
│   ├── home_coach.py      # 首页对话 Agent
│   ├── prompts.py         # COACH_SYSTEM_PROMPT
│   └── graph.py           # LangGraph 主图
├── knowledge/
│   ├── exercises.py       # 20个动作结构化数据
│   └── rag.py             # 5-Collection RAG + 意图检索
├── database/
│   └── db.py              # MySQL 操作层
└── ui/
    └── pages/
        ├── home.py        # 首页（含 AI 教练对话）
        ├── workout.py     # 完整训练流程状态机
        ├── workout_history.py  # 训练记录
        ├── plan_edit.py   # AI 格式化训练计划输入
        └── profile.py     # 个人档案 + PR趋势
```

---

## System Prompt 设计

`agents/prompts.py` 包含 9 个 Section 的完整训练科学决策框架：

- **SECTION 1**：训练阶段动态评分（novice/intermediate/advanced）
- **SECTION 2**：MEV/MRV 参考值 + 动态调整规则
- **SECTION 3**：渐进超负荷五种方式优先级
- **SECTION 4**：减载决策（标准减载 vs 深度减载）
- **SECTION 5**：今日准备度评估（影响 RIR 而非直接降重量）
- **SECTION 6**：停滞诊断（恢复不足型 vs 训练量不足型）
- **SECTION 7**：疼痛处理框架（1-3/4-6/7+ 分级）
- **SECTION 8**：回答模式（知识问答 vs 问题诊断）
- **SECTION 9**：Agent 输出格式规范（含 flags 字段）

---

## 目标用户

| 用户类型 | 痛点 | 系统解法 |
|---------|------|---------|
| 健身小白（0-3个月）| 不知道从哪开始，怕受伤 | 线性进阶逻辑，动作教程库，保守 RIR |
| 瓶颈期用户（1-2年）| 进步停滞，不懂周期化 | RP Strength 体系，停滞诊断，主动减载 |
