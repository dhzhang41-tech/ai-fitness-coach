# Project Understanding v0

## 1. Project Positioning

This project should be understood as an **Adaptive Training Decision System**, not just an AI fitness chatbot.

The core problem is that most training plans are static: they do not react well to daily readiness, fatigue, pain, missed workouts, stagnation, nutrition, or long-term progression. This project tries to model training as a sequence of decisions:

- What long-term plan should the user follow?
- Is the user ready to train today?
- Should today's workout be adjusted?
- What did the user actually complete?
- Is progress stalling?
- When should the long-term plan be reviewed?

The chat experience is one interface. The deeper value is the state-driven decision loop.

## 2. Current User Experience

The current app is a Streamlit application with these main flows:

1. Onboarding
   - User enters name, birth date, height, weight, training start date, weekly training days, goal, and estimated squat/bench/deadlift 1RM.
   - The app saves the user and profile.
   - The graph runs `review_macro_plan`.
   - `plan_agent` generates and saves a macro training plan.

2. Home
   - Shows whether the user has a valid plan.
   - Shows today's workout preview when possible.
   - Shows recent workout information.
   - Allows navigation to history, plan overview, profile, and plan editing.
   - Includes protein intake logging.
   - Includes a home coach chat interface.

3. Workout
   - User fills daily readiness: sleep, stress, fatigue, pain areas.
   - App loads today's training plan.
   - App applies intensity scaling based on readiness.
   - User progresses through exercises.
   - User can mark actions complete or request mid-workout adjustment.
   - At the end, user logs actual sets, weight, reps, and feeling.
   - Graph runs `start_workout` and logs the result.

4. Plan Management
   - `plan_overview` displays saved macro plans.
   - `plan_edit` lets the user write a free-form plan, which is parsed by an LLM into structured JSON.

5. Profile and History
   - Profile shows basic stats and PR records.
   - Workout history shows recent logs, completion rate, readiness values, and notes.

## 3. Main File Map

### Root

- `main.py`
  - Streamlit entry point.
  - Initializes database and knowledge base.
  - Initializes session state.
  - Performs startup stagnation check.
  - Handles date rollover reset.
  - Routes pages.
  - Contains onboarding and macro-plan regeneration logic inline.

- `config.py`
  - Loads `.env`.
  - Defines DeepSeek API settings.
  - Defines MySQL connection config.

- `requirements.txt`
  - Core dependencies: LangGraph, LangChain, OpenAI client, ChromaDB, Streamlit, dotenv, MySQL connector.

### Agents

- `agents/state.py`
  - Defines `CoachState`.
  - This is the shared graph state and should eventually become the conceptual center of the system.

- `agents/graph.py`
  - Builds the LangGraph graph.
  - Registers `orchestrator`, `plan_agent`, `adjust_agent`, `replan_agent`, and `log_agent`.
  - Current routes do not reach `replan_agent`.
  - Exposes `run_session()`.

- `agents/orchestrator.py`
  - Loads user/profile data.
  - Classifies intent when no explicit intent is supplied.
  - Detects plan-review signals.
  - Checks automatic stagnation.

- `agents/plan_agent.py`
  - Builds a 4-week macro plan from profile data.
  - Chooses split based on training days.
  - Estimates weights from 1RM fields.
  - Saves `macro_plan_json` to MySQL.
  - Uses DeepSeek for a short coach comment, but plan generation itself is mostly deterministic.

- `agents/adjust_agent.py`
  - Computes readiness from sleep, stress, fatigue.
  - Converts readiness into normal/reduced/rest.
  - Adjusts current plan intensity and sets.

- `agents/replan_agent.py`
  - Implements mid-workout replanning strategies.
  - Handles reasons such as too heavy, too tired, discomfort, and lack of time.
  - Currently registered in the graph but unreachable from graph routing.

- `agents/log_agent.py`
  - Saves workout logs.
  - Checks estimated PRs.
  - Advances macro week.
  - Returns a workout summary.

- `agents/home_coach.py`
  - Powers the home chat interface.
  - Uses intent classification and RAG.
  - Reads recent logs, PRs, and profile.
  - Produces personalized coaching answers.

- `agents/nutrition_agent.py`
  - Estimates protein grams from natural-language food descriptions.
  - Used by the home page, not the graph.

- `agents/training_agent.py`
  - Prototype/richer training plan agent.
  - Not wired into the current graph.

- `agents/recovery_agent.py`
  - Prototype/richer recovery assessment agent.
  - Not wired into the current graph.

- `agents/prompts.py`
  - Contains the large coaching decision prompt.
  - Defines training level logic: novice, intermediate, advanced.

### UI

- `ui/forms.py`
  - Onboarding form.
  - Readiness form.
  - Workout log form.

- `ui/display.py`
  - Exercise card UI.
  - Training summary UI.
  - Macro plan display helper.
  - Also contains exercise-specific mini chat via RAG and DeepSeek.

- `ui/pages/home.py`
  - Home dashboard.
  - Today's workout preview.
  - Navigation.
  - Protein logging.
  - Home coach chat.

- `ui/pages/workout.py`
  - The most important UI workflow.
  - Runs a Streamlit state machine for readiness -> plan display -> exercise loop -> log form -> summary.
  - Contains local readiness adjustment logic.
  - Calls `run_session()` for workout logging and attempted replanning.

- `ui/pages/plan_overview.py`
  - Displays macro plan.
  - Supports both `weeks` format and `days` format.

- `ui/pages/plan_edit.py`
  - Lets user paste free-form workout plan.
  - Uses LLM to normalize plan into structured JSON.
  - Saves plan as `days` format.

- `ui/pages/profile.py`
  - Shows basic user data.
  - Lets user update body weight.
  - Lets user manually record big-three PRs.

- `ui/pages/workout_history.py`
  - Shows recent workout logs.
  - Allows saving notes.

### Database

- `database/db.py`
  - MySQL schema creation.
  - User/profile CRUD.
  - Macro plan update and stale markers.
  - Workout logs.
  - PR records.
  - Nutrition logs.
  - Basic analytics such as average completion rate and PR stagnation.

- `database/seed_data.py`
  - Creates test user and sample logs.
  - Useful for local demo but still somewhat hardcoded.

### Knowledge

- `knowledge/exercises.py`
  - Structured exercise library.
  - Contains exercise names, categories, target muscles, key points, common mistakes, and cues.

- `knowledge/rag.py`
  - In-memory ChromaDB setup.
  - Inserts training principles, technique knowledge, recovery, physiology, nutrition, and exercise library data.
  - Provides search functions by collection and decision type.

## 4. Current LangGraph Behavior

Registered graph nodes:

```text
orchestrator
plan_agent
adjust_agent
replan_agent
log_agent
```

Actual current routes:

```text
review_macro_plan
  -> orchestrator
  -> plan_agent
  -> END

start_workout, normal readiness
  -> orchestrator
  -> log_agent
  -> END

start_workout, abnormal readiness
  -> orchestrator
  -> adjust_agent
  -> log_agent
  -> END
```

Important finding:

`replan_agent` is implemented and registered but currently has no route into it. The workout UI attempts mid-workout replanning by calling `run_session(intent="start_workout", replan_reason=...)`, but the graph still routes this as `start_workout`, usually to `log_agent`.

## 5. Data Model

Current MySQL tables:

- `users`
  - User id, name, created time.

- `user_profiles`
  - Height, weight, birth date, training start date.
  - Big-three 1RM fields.
  - Weekly training days and current goal.
  - Macro cycle fields: phase, week, start date, `macro_plan_json`.
  - `plan_stale` flag.

- `workout_logs`
  - Readiness scores.
  - Pain areas.
  - Planned exercises JSON.
  - Actual exercises JSON.
  - Completion rate.
  - Override flag.
  - Replan count.
  - Note.

- `prs`
  - Exercise name, weight, reps, PR date.

- `nutrition_logs`
  - Date, protein grams, note.

## 6. Current Knowledge/RAG Design

The knowledge base is not external files yet; it is embedded in Python lists and inserted into an ephemeral ChromaDB client on startup.

Collections/concepts:

- Training principles: MEV, MRV, progressive overload, RIR, periodization, exercise selection.
- Technique knowledge: warm-up, bracing, tempo, full ROM, grip, sticking points.
- Recovery knowledge: sleep, deload, active recovery, DOMS, stress, overtraining, mobility.
- Physiology: MPS, hormones, energy systems, muscle fibers, neural adaptation.
- Nutrition: protein, calorie surplus, pre/post workout nutrition, hydration, supplements.
- Exercise library: structured movement-specific data.

This is already a good base for a defensible project because it connects LLM behavior to explicit domain knowledge.

## 7. Current Decision Points

The system already contains these decision points:

- Whether onboarding is complete.
- Whether a macro plan exists.
- Whether a plan is stale.
- Which page the user should see.
- Which split to generate from training days.
- What working weight to assign from 1RM.
- Whether today's readiness is normal, reduced, or rest.
- Whether to scale workout intensity.
- Whether workout completion indicates good/medium/poor adherence.
- Whether a completed lift may be a PR.
- Whether recent completion or PR trend suggests stagnation.
- How home coach should retrieve knowledge based on query intent.

These are exactly the parts to highlight in an application or interview: the project is becoming a decision engine.

## 8. Main Architecture Problems

### Problem 1: `main.py` is overloaded

It is doing app boot, routing, onboarding orchestration, daily reset, and macro-plan regeneration. This makes the app hard to reason about and hard to test.

Later direction:

- Extract session initialization.
- Extract page routing.
- Move onboarding flow into a page module.
- Move macro regeneration flow into a page or service module.

### Problem 2: Plan schema is not unified

Two plan formats exist:

```json
{"split": "PPL_3", "weeks": []}
```

and:

```json
{"split_type": "PPL_3", "days": []}
```

`plan_overview` handles both, but `workout.py` expects top-level `days`. This can cause generated plans and edited plans to behave differently.

Later direction:

- Choose canonical schema.
- Write conversion helpers.
- Add validation.

### Problem 3: Graph and UI both make decisions

Readiness and adjustment logic appear in both:

- `run_session()` / `adjust_agent`
- `ui/pages/workout.py`

Later direction:

- Decide whether the graph owns training decisions and UI only renders them, or whether UI keeps deterministic pre-processing.

### Problem 4: `replan_agent` is unreachable

This is probably the first real behavior bug to fix after documentation. The UI implies mid-workout replanning exists, but graph routing does not execute the replan node.

Later direction:

- Add a route when `replan_reason` is present.
- Decide whether replanning should log immediately or only update current plan.

### Problem 5: Prototype agents are not integrated

`training_agent.py` and `recovery_agent.py` represent a more advanced architecture, but the graph currently uses simpler `plan_agent` and `adjust_agent`.

Later direction:

- Decide whether they are future replacements, experiments, or should be removed.
- Do not delete before deciding the long-term architecture.

## 9. What This Project Can Become

For a master's application, this project can be framed as:

> A state-driven adaptive training system that combines structured user modeling, multi-agent workflow orchestration, retrieval-augmented domain knowledge, and longitudinal workout logs to personalize strength/hypertrophy training decisions.

The strongest technical themes:

- Human-centered AI decision support.
- Stateful agent workflows.
- Personalized recommendation systems.
- RAG for domain-grounded coaching.
- Health/fitness data modeling.
- Evaluation of adaptive decisions over time.

This is stronger than "I built a chatbot" because it has system design, domain modeling, user state, and long-term feedback loops.

## 10. Suggested Development Roadmap

### Phase 1: Understand and stabilize

- Finish architecture docs.
- Restore/rewrite README around the decision-system framing.
- Keep behavior unchanged.
- Identify risky paths.

### Phase 2: Make the current system coherent

- Unify macro plan schema.
- Fix or explicitly defer `replan_agent`.
- Remove debug UI from user-facing pages.
- Split `main.py`.
- Add basic tests for pure functions.

### Phase 3: Make the decision system deeper

- Define formal `TrainingDecision` / `ReadinessDecision` / `PlanReviewDecision` objects.
- Make graph routing depend on explicit state flags.
- Add plan validation.
- Improve stagnation detection.
- Track decision outcomes over time.

### Phase 4: Evaluation layer

- Define metrics:
  - Completion rate.
  - Override frequency.
  - PR trend.
  - Readiness trend.
  - Plan adherence.
  - User-reported fatigue/pain.
- Create synthetic users or replay logs.
- Compare static plan vs adaptive plan behavior.

### Phase 5: Application materials

- Polished README.
- Architecture diagram.
- Technical report.
- Demo screenshots.
- Resume bullets.
- SOP project paragraph.

## 11. Resume / Application Narrative Draft

Possible resume bullet:

> Built an adaptive training decision system using Streamlit, LangGraph, MySQL, ChromaDB, and DeepSeek API to generate personalized hypertrophy plans, assess daily readiness, adjust workouts, log training outcomes, and retrieve domain-grounded coaching knowledge through RAG.

Stronger technical version:

> Designed a state-driven multi-agent fitness coaching system with user profile modeling, readiness assessment, workout adaptation, PR tracking, and retrieval-augmented training knowledge, reframing static workout planning as a longitudinal decision-making problem.

SOP-style framing:

> This project began as a simple AI fitness coach, but I am developing it into an adaptive decision system for personalized training. The system models a user's profile, daily readiness, workout execution, and progress history, then uses a LangGraph workflow and retrieval-augmented training knowledge to support planning, adjustment, and review decisions. Through this project, I am exploring how AI systems can combine structured state, domain knowledge, and longitudinal feedback to provide more reliable personalized recommendations.

## 12. Immediate Next Step

Recommended next task:

Rewrite the root `README.md` around the new positioning:

- Problem
- Target users
- System overview
- Architecture
- Current workflow
- Data model
- RAG design
- Evaluation roadmap
- Development roadmap

Before that, decide whether to restore the deleted `README.md` or create a new one from scratch.

