# AI 增肌教练

基于 LangGraph Multi-Agent 架构的 AI 增肌教练系统，使用 DeepSeek API 驱动，提供个性化训练计划生成、每日状态调整、训练日志追踪等功能。

## 技术栈

- Python 3.11+
- LangGraph 0.2+ (Multi-Agent Supervisor 模式)
- LangChain + OpenAI SDK (调用 DeepSeek API)
- ChromaDB (本地向量 RAG 知识库)
- MySQL (本地数据库)
- Streamlit (前端界面)

## 安装与运行

### 1. 克隆项目

```bash
cd ai-fitness-coach
```

### 2. 创建虚拟环境

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

复制 `.env.example` 为 `.env`：

```bash
copy .env.example .env
```

编辑 `.env` 文件，填入以下内容：
- `DEEPSEEK_API_KEY`：你的 DeepSeek API 密钥
- `MYSQL_PASSWORD`：你的 MySQL 密码

### 5. 确保 MySQL 已启动

确保 MySQL 服务正在运行。程序首次启动时会自动创建数据库和表。

### 6. 初始化测试数据（可选）

```bash
python -m database.seed_data
```

### 7. 启动应用

```bash
streamlit run main.py
```

## 项目结构

```
ai-fitness-coach/
├── .env.example         # 环境变量示例
├── requirements.txt     # Python 依赖
├── config.py            # 全局配置
├── main.py              # Streamlit 主入口
├── database/
│   ├── db.py            # MySQL 数据库操作
│   └── seed_data.py     # 测试数据初始化
├── knowledge/
│   ├── exercises.py     # 动作库（20个动作）
│   └── rag.py           # ChromaDB RAG 知识检索
├── agents/
│   ├── state.py         # LangGraph 状态定义
│   ├── orchestrator.py  # 意图识别 + 计划检测
│   ├── plan_agent.py    # 长期计划生成
│   ├── adjust_agent.py  # 当日临时调整
│   ├── replan_agent.py  # 训练中重规划
│   ├── log_agent.py     # 训练日志记录
│   └── graph.py         # LangGraph 主图
└── ui/
    ├── forms.py         # Streamlit 表单组件
    ├── display.py       # 展示组件
    └── pages/
        ├── home.py      # 首页
        ├── workout.py   # 训练流程
        └── profile.py   # 个人档案
```

## 功能

- **个性化训练计划**：根据用户档案（1RM、训练频率、年限）自动生成周期化训练计划
- **两种计划架构**：长期周期计划 + 当日临时调整（不写数据库）
- **智能状态评估**：根据睡眠、压力、疲劳度自动调整当日训练强度
- **训练中重规划**：动作未完成可自动调整剩余计划（上限2次）
- **知识库检索**：基于 ChromaDB 的 RAG 系统，提供动作指导和训练原理
- **PR 追踪**：自动检测新 PR 并记录历史趋势
- **长期计划自动检测**：完练率低或 PR 停滞时自动提醒调整计划

## 使用说明

1. 首次使用填写个人档案，系统自动生成训练周期计划
2. 每次训练前填写状态评估，系统自动调整当日强度
3. 训练中按顺序完成动作，可查看动作详解、提问教练
4. 动作未完成可选择原因，系统自动调整剩余计划
5. 训练完成后自动记录日志并检查 PR
6. 首页实时查看蛋白质摄入和训练记录
