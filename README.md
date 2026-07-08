# Adaptive Training Decision System

An adaptive training decision system for natural lifters who are moving beyond beginner training and need help making consistent, explainable workout decisions.

This project began as an AI fitness coach prototype. It is being redesigned into a state-driven system that combines structured user data, workout logs, rule-based training decisions, LangGraph agent orchestration, and retrieval-augmented coaching knowledge.

不是健身聊天机器人，而是一个有科学依据、有个人记忆、能随用户状态动态调整的**训练决策引擎**。

## Problem

Most training apps store static workout plans. Most AI fitness products behave like open-ended chatbots. Neither is enough for a lifter who trains consistently but is unsure how to adjust when readiness, fatigue, pain, missed sessions, or plateaus appear.

This project focuses on a narrower and more useful question:

> How can an AI-assisted system help a lifter make repeatable, conservative, and explainable training decisions before, during, and after each workout?

## Target User

The first target user is a natural lifter with roughly 3-18 months of training experience.

This user usually knows the basic movements and follows a structured plan, but still struggles with decisions such as:

- whether to train normally on a low-readiness day;
- whether to reduce weight, reduce sets, or stop;
- what to do when an exercise feels too heavy mid-workout;
- whether poor progress means insufficient volume or insufficient recovery;
- when a long-term plan should be reviewed instead of blindly continued.

The system is not currently designed for clinical rehabilitation, complete beginners, or advanced competitive programming.

## Core Idea

The project separates reliable decisions from natural-language coaching:

- **Rules and state** handle readiness scoring, replan limits, completion rate, PR detection, and plan review signals.
- **LLM calls** help explain decisions, summarize outcomes, parse free-form plan input, and answer training questions with retrieved knowledge.

This boundary keeps the system more predictable than a pure chatbot while still allowing a coach-like user experience.

## Current Capabilities

- User onboarding with profile and training history inputs.
- Macro plan generation from user profile data.
- Daily readiness collection based on sleep, stress, fatigue, and pain areas.
- Workout flow with exercise-by-exercise execution.
- Mid-workout replanning for reasons such as too heavy, too tired, discomfort, or lack of time.
- Workout logging with completion rate and simple PR detection.
- Profile page with body weight and big-three PR tracking.
- Workout history with notes.
- Home coach chat backed by structured training knowledge and recent user data.
- Protein intake estimation and nutrition logging.

## System Architecture

```text
Streamlit UI
  - pages, forms, workout flow, profile, history
        |
        v
LangGraph Workflow
  - routes each user/session action to the relevant agent
        |
        v
Agents
  - plan generation
  - readiness adjustment
  - mid-workout replanning
  - logging and evaluation
  - home coaching
        |
        v
State + Persistence
  - CoachState for graph execution
  - Streamlit session_state for UI flow
  - MySQL for user profile, plans, logs, PRs, nutrition
        |
        v
Knowledge Layer
  - structured exercise library
  - in-memory ChromaDB RAG collections
```

## Key Modules

```text
main.py
  Streamlit entry point and page router.

agents/graph.py
  LangGraph workflow definition and run_session entry point.

agents/state.py
  Shared CoachState used by the graph.

agents/plan_agent.py
  Generates and saves macro training plans.

agents/adjust_agent.py
  Applies simple readiness-based workout adjustment.

agents/replan_agent.py
  Adjusts the remaining workout during a session.

agents/log_agent.py
  Saves workout logs and detects simple PR signals.

ui/pages/workout.py
  Main workout flow: readiness -> plan display -> exercise loop -> log -> summary.

database/db.py
  MySQL schema and persistence functions.

knowledge/rag.py
  Structured RAG knowledge collections and search helpers.

knowledge/exercises.py
  Exercise library with movement cues, target muscles, and common mistakes.
```

## Current Decision Flow

### Macro Plan Review

```text
review_macro_plan
  -> orchestrator
  -> plan_agent
  -> END
```

### Normal Workout Logging

```text
start_workout without replan_reason
  -> orchestrator
  -> log_agent
  -> END
```

### Readiness-Based Adjustment

```text
start_workout with abnormal readiness
  -> orchestrator
  -> adjust_agent
  -> log_agent
  -> END
```

### Mid-Workout Replanning

```text
start_workout with replan_reason
  -> orchestrator
  -> replan_agent
  -> END
```

Mid-workout replanning updates the current session plan. It does not write the final workout log or modify the long-term macro plan.

## Data Model

The current MySQL layer stores:

- `users`: user identity;
- `user_profiles`: body metrics, training start date, 1RM estimates, macro plan, plan status;
- `workout_logs`: readiness inputs, planned and actual workout JSON, completion rate, replan count, notes;
- `prs`: personal record entries;
- `nutrition_logs`: daily protein records.

## Knowledge Design

The current knowledge layer includes:

- training principles such as MEV, MRV, RIR, periodization, and progressive overload;
- exercise technique knowledge;
- recovery management knowledge;
- physiology concepts;
- nutrition basics;
- a structured exercise library.

The home coach and exercise Q&A features retrieve relevant knowledge before generating responses.

## Design Documents

Project design notes are kept in `docs/`:

- `docs/architecture_review_v0.md`: current architecture review and codebase findings.
- `docs/project_understanding_v0.md`: file-level project understanding and application narrative.
- `docs/system_design_v1.md`: six-month system design blueprint.
- `docs/mvp_decision_policy_v0.md`: conservative MVP decision policy.

## Current Development Focus

The project is currently in an architecture cleanup and MVP stabilization phase.

Near-term priorities:

1. Keep the current behavior understandable and stable.
2. Use the existing agents instead of adding new ones.
3. Make mid-workout replanning work as a session-only decision.
4. Keep long-term plan changes user-confirmed rather than automatic.
5. Gradually separate UI flow, graph state, and persistent data.

## Roadmap

### Phase 1: Stabilize the Existing Prototype

- Document current architecture.
- Clarify agent responsibilities.
- Fix unreachable or mismatched workflow paths.
- Keep feature scope small and usable.

### Phase 2: State and Schema Cleanup

- Define a canonical plan schema.
- Reduce duplicated readiness logic between UI and agents.
- Make `CoachState` more explicit.
- Add decision reason codes.

### Phase 3: Adaptive Decision Loop

- Add structured readiness decisions.
- Add workout execution decisions.
- Add progression decisions.
- Add plan review decisions.
- Store decision traces for debugging and evaluation.

### Phase 4: Evaluation and Portfolio Packaging

- Track completion rate, replans, PR trend, readiness trend, and plan review signals.
- Build demo data and screenshots.
- Write a technical report explaining design choices and limitations.

## Local Setup

Requirements:

- Python 3.11+
- MySQL 8.0+
- DeepSeek API key

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m database.seed_data
streamlit run main.py
```

Fill `.env` with:

```text
DEEPSEEK_API_KEY=your_deepseek_key_here
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=ai_fitness_coach
```

## Notes

This project is intentionally being developed as a learning and portfolio system. The current goal is not to claim perfect training recommendations, but to build a transparent adaptive decision loop that can be tested, used, and improved over time.

