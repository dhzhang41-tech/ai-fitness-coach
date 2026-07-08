# Architecture Review v0

## Purpose

This review captures the current state of the project before turning it from a simple AI fitness coach into an adaptive training decision system.

Iteration 1 should preserve behavior. The goal is to understand the existing system, document the current architecture, identify structural risks, and prepare a cleaner framing for future iterations.

## Current Product Framing

The project is better described as an **Adaptive Training Decision System** than as a chatbot.

The current system already makes several training decisions:

- Generates or updates a macro training plan.
- Assesses daily readiness from sleep, stress, and fatigue.
- Adjusts workout intensity when readiness is abnormal.
- Logs workout completion and PR signals.
- Detects plan stagnation signals and marks a plan as stale.
- Provides home-page coaching and nutrition estimation.

The chatbot is one interface, not the core product.

## Current Entry Points

### Streamlit app

- `main.py` is the Streamlit entry point.
- It initializes the database and in-memory knowledge base.
- It owns global `st.session_state` defaults.
- It performs page routing by checking `st.session_state.page`.
- It includes onboarding, macro-plan regeneration, and daily reset logic inline.

### LangGraph workflow

- `agents/graph.py` builds and compiles the LangGraph workflow.
- `agents/state.py` defines the shared `CoachState`.
- `run_session()` prepares initial state, loads the user profile, parses `macro_plan_json`, applies readiness assessment when form data exists, and invokes the graph.

## Current Graph

Registered nodes:

- `orchestrator`
- `plan_agent`
- `adjust_agent`
- `replan_agent`
- `log_agent`

Current graph routes:

```text
START
  -> orchestrator
    -> plan_agent -> END                    when intent == "review_macro_plan"
    -> adjust_agent -> log_agent -> END     when intent == "start_workout" and is_override
    -> log_agent -> END                     when intent == "start_workout" and not is_override
    -> END                                  otherwise
```

`replan_agent` is registered and has an edge to `END`, but no route currently returns `"replan_agent"`.

## Current State Shape

`CoachState` currently contains:

- User identity and profile: `user_id`, `user_name`, `user_profile`
- Long-term plan state: `macro_plan`, `plan_needs_review`
- Intent: `intent`
- Daily readiness: `today_readiness`, `is_override`
- Current workout execution: `current_plan`, `completed_exercises`, `replan_count`, `replan_reason`
- Conversation fields: `messages`, `user_input`
- Agent output fields: `agent_response`, `error`

This is a useful foundation for a state-driven system, but the state is not yet the single source of truth. Some decisions are still duplicated in UI code.

## Main Behavior Paths

### Onboarding and macro-plan generation

`main.py` collects onboarding input through `ui.forms.render_onboarding_form()`, saves the user and profile, then calls:

```text
run_session(user_id, "review_macro_plan")
```

The graph routes to `plan_agent`, which builds a 4-week macro plan and writes it into `user_profiles.macro_plan_json`.

### Starting a workout

`ui/pages/workout.py` collects readiness values, reads the current day plan from `macro_plan_json`, applies local intensity adjustment, and then drives the workout loop through Streamlit session state.

At summary time, it calls:

```text
run_session(user_id, "start_workout", form_data=..., completed_exercises=..., current_plan=...)
```

Inside `run_session()`, readiness is assessed again and `is_override` is set based on the computed readiness level.

### Normal readiness

When `intent == "start_workout"` and `is_override` is false, the graph routes:

```text
orchestrator -> log_agent -> END
```

The workout log is saved and macro week advancement is attempted.

### Abnormal readiness

When `intent == "start_workout"` and `is_override` is true, the graph routes:

```text
orchestrator -> adjust_agent -> log_agent -> END
```

`adjust_agent` adjusts the plan based on readiness, then `log_agent` saves the workout log.

### Mid-workout replanning

`ui/pages/workout.py` exposes a mid-workout replan action and calls:

```text
run_session(
    user_id=user_id,
    intent="start_workout",
    replan_reason=reason,
    completed_exercises=completed,
    current_plan=plan,
    replan_count=replan_count,
)
```

However, the graph does not route to `replan_agent` for this state. With the current route function, this call is treated as a normal `start_workout` path and goes to `log_agent` unless `is_override` is true.

This is the clearest current mismatch between UI intent and graph behavior.

## Structural Findings

### `main.py` has too many responsibilities

`main.py` currently handles:

- App configuration.
- Startup initialization.
- Global session defaults.
- Automatic stagnation checks.
- Cross-day session reset.
- Page routing.
- Onboarding orchestration.
- Macro-plan regeneration flow.

This makes the app hard to reason about as a decision system. A later cleanup could move page routing and session initialization into dedicated UI/application modules without changing behavior.

### Decision logic is split across graph and UI

Examples:

- `run_session()` assesses readiness via `assess_readiness()`.
- `ui/pages/workout.py` also calls `assess_readiness()` and adjusts weights locally.
- `adjust_agent` has an adjustment path, but `workout.py` also performs plan standardization and intensity scaling before workout execution.

For Iteration 1, this should be documented rather than refactored. A future iteration can decide which layer owns readiness and plan adjustment.

### Macro plan schema has two active formats

The code supports at least two plan shapes:

- `plan_agent` format:

```json
{
  "split": "PPL_3",
  "weeks": []
}
```

- `plan_edit` format:

```json
{
  "days": [],
  "split_type": "PPL_3"
}
```

`ui/pages/plan_overview.py` handles both formats, but `ui/pages/workout.py` expects `days` at the top level. This means automatically generated plans and manually edited plans may not have the same runtime behavior.

This is an architecture concern, but changing it would affect behavior and should be deferred.

### Graph intent classification is mostly bypassed

`orchestrator.classify_intent()` exists, but `run_session()` always passes an explicit `intent`, and `orchestrator_node()` prefers the existing state intent.

This is acceptable if the application intends to use deterministic UI-driven intents. It should be framed as explicit routing rather than natural-language intent detection.

### `plan_needs_review` is computed but not routed

`orchestrator_node()` computes `plan_needs_review`, including automatic stagnation detection, but `route_after_orchestrator()` only routes to `plan_agent` when `intent == "review_macro_plan"`.

This means plan review signals are recorded in state but do not independently trigger graph behavior.

### Debug and development UI are present in user-facing paths

Examples:

- Onboarding prints raw `macro_plan_json` preview and field length.
- Home page contains a "reset today's workout status" test button.
- Database and agent functions print detailed debug logs.

These may be useful during development, but they should eventually be separated from production UI.

## Potentially Unused or Orphaned Modules

Do not delete these without confirmation.

### Registered but unreachable

- `agents/replan_agent.py`
  - Imported and registered in `agents/graph.py`.
  - No graph route currently reaches it.
  - UI appears to expect this behavior during mid-workout replanning.

### Implemented but not wired into the current graph

- `agents/training_agent.py`
  - Defines `training_agent_node()`.
  - Not imported by `agents/graph.py`.
  - Referenced only in comments as a compatible source of `reps_range`.

- `agents/recovery_agent.py`
  - Defines `recovery_agent_node()`.
  - Not imported by `agents/graph.py`.
  - Represents a richer readiness model than the current `adjust_agent.assess_readiness()` path.

### Used outside the graph

- `agents/nutrition_agent.py`
  - Used by `ui/pages/home.py` for protein estimation.

- `agents/home_coach.py`
  - Used by `ui/pages/home.py` for the home chat interface.

These are not orphaned, but they are outside the LangGraph workflow.

## `.gitignore` Review

Current `.gitignore` already covers:

- Virtual environments.
- Environment files.
- Python caches.
- Local database files.
- ChromaDB local data.
- IDE files.
- System files.
- Logs.
- Some test/debug scripts.
- PDFs and `outputs/`.
- `.claude/`.

Recommended addition:

- `tree.txt`, because the current file is a large generated structure snapshot and should not be committed as source.

Question to resolve later:

- Whether `assets/` should be tracked. It is currently untracked. If it contains product assets or documentation, track it. If it contains generated local artifacts, ignore the generated artifacts specifically rather than ignoring the whole directory.

## Current Git Status Notes

At review time, Git reports:

```text
D README.md
?? assets/
?? tree.txt
```

`README.md` is currently deleted in the working tree. This review does not restore or overwrite it.

## Suggested README Structure

The README should present the project as a decision system, not only a chatbot.

Recommended structure:

```text
# Adaptive Training Decision System

## Problem
Why static training plans fail: readiness, recovery, adherence, stagnation, and plan drift.

## Target Users
Lifters who need structured hypertrophy training with day-to-day adaptation.

## Product Positioning
This is a state-driven adaptive training decision system with a chat interface, not a chatbot-only app.

## Core Decisions
- Generate macro training plan
- Assess daily readiness
- Adjust daily training
- Log workout execution
- Detect stagnation
- Support plan review

## Architecture
- Streamlit UI
- LangGraph workflow
- CoachState
- Agents
- MySQL persistence
- In-memory RAG knowledge base

## Current Workflow
Document the current graph paths exactly as implemented.

## Data Model
Summarize users, user_profiles, workout_logs, prs, nutrition_logs.

## Evaluation Plan
How to judge whether decisions are good: consistency, completion rate, PR trend, readiness trend, user override rate.

## Roadmap
Iteration 1: architecture review and cleanup
Iteration 2: unify plan schema and routing
Iteration 3: richer adaptive decision policy
Iteration 4: evaluation and experiments

## Local Development
Setup, environment variables, database, run command.
```

## Recommended Iteration 1 Cleanup Plan

These are cleanup recommendations only; they should not change product behavior.

1. Keep this architecture review in `docs/architecture_review_v0.md`.
2. Add `tree.txt` to `.gitignore`.
3. Decide whether to restore README now or rewrite it after the review is accepted.
4. Create a short architecture diagram in docs after the graph route is confirmed.
5. Do not delete orphaned modules yet; mark them as candidates and decide in Iteration 2.
6. Do not route `replan_agent` yet unless the project owner confirms that mid-workout replanning should be fixed in this iteration.

## Deferred Questions

- Should `replan_agent` be activated as a bug fix, or left untouched until Iteration 2?
- Should `training_agent` and `recovery_agent` replace the simpler current `plan_agent` / `adjust_agent` path, or remain prototypes?
- Which macro plan schema should become canonical: `weeks` or `days`?
- Should automatic stagnation detection trigger a graph route, or only mark `plan_stale` for user confirmation?
- Should the home coach remain outside LangGraph, or become a graph node later?

