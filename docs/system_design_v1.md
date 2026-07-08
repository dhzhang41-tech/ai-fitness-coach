# System Design v1

## 1. Product Thesis

This project is an **Adaptive Training Decision System** for natural lifters who are moving beyond beginner training but are not yet advanced enough to manage training decisions confidently.

The core belief:

> A useful training assistant should not only answer questions. It should help the user make repeatable, explainable training decisions before, during, and after each workout.

Most fitness apps store plans and logs. Most AI fitness products behave like chatbots. This project should sit between them: a stateful system that observes user profile, readiness, plan, execution, and progress signals, then produces structured training decisions with clear explanations.

## 2. Target User

Primary user:

> A natural lifter with 3-18 months of consistent training experience who knows basic exercises, has started following structured workouts, and is beginning to face real progression and recovery problems.

This user is not a complete beginner. They usually know what bench press, squat, deadlift, push/pull/legs, and progressive overload mean. Their problem is not basic motivation or exercise discovery. Their problem is decision uncertainty.

Typical situations:

- They are unsure whether to add weight, add reps, add sets, or maintain.
- They do not know whether poor performance is caused by fatigue, bad sleep, insufficient volume, or poor programming.
- They sometimes push too hard on bad readiness days.
- They sometimes skip or abandon training when a smaller adjustment would have been better.
- They have logs but do not know how to interpret them.
- They hit early plateaus and cannot tell whether they need more work or more recovery.

Secondary users can exist later, but this system should not optimize for everyone at once.

Not the first target:

- Complete beginners who mainly need education and habit formation.
- Advanced bodybuilders or powerlifters who need highly individualized programming.
- Clinical rehab users whose decisions require medical supervision.

## 3. Core Product Promise

The system should help the target user answer:

- Should I train today as planned?
- If not, how should today's workout change?
- If I fail during the workout, what should I do with the remaining work?
- Did today's training count as successful execution?
- What should change next time?
- Is my current long-term plan still working?
- Can the system explain the decision clearly enough that I trust it?

The product should feel like a coach that remembers state and follows a decision policy, not like a blank chat box.

## 4. Core Decisions

### 4.1 Readiness Decision

Question:

> Given today's sleep, stress, fatigue, pain, and recent history, should the user train normally, reduce load/volume, switch to recovery work, or rest?

Inputs:

- Sleep score
- Stress score
- Fatigue score
- Pain areas and future pain severity
- Recent completion rate
- Recent readiness trend
- Recent PR/performance trend

Outputs:

- Readiness score
- Readiness level: `normal`, `reduced`, `recovery_only`, `rest`
- Intensity adjustment
- Volume adjustment
- Pain constraints
- Explanation

Reliability principle:

This decision should be mostly rule-based. LLM can explain the decision but should not invent the score.

### 4.2 Workout Execution Decision

Question:

> During a workout, if the user reports that an exercise is too heavy, too tiring, painful, or time-constrained, how should the remaining workout change?

Inputs:

- Current exercise
- Completed exercises
- Remaining exercises
- Replan reason
- Replan count
- Readiness state
- Pain constraints

Outputs:

- Adjusted remaining exercises
- Whether to reduce load
- Whether to reduce sets
- Whether to remove or substitute exercises
- Whether to end the workout
- Explanation

Reliability principle:

Rules should choose the adjustment category. LLM can generate supportive coaching language and, later, suggest substitutions from a controlled exercise library.

### 4.3 Progression Decision

Question:

> Based on the previous sessions for an exercise, what should happen next time?

Inputs:

- Planned weight/sets/reps
- Actual weight/sets/reps
- Last-set reps
- User feeling: spare reps, barely completed, failed
- Recent exercise history
- Readiness context

Outputs:

- Increase weight
- Increase reps
- Increase sets
- Maintain
- Deload/reduce
- Flag technique or recovery issue

Reliability principle:

Progression should be deterministic and auditable. A simple policy is better than opaque LLM advice.

### 4.4 Plan Review Decision

Question:

> Is the current macro plan still appropriate, or should the system suggest plan review?

Inputs:

- Recent completion rate
- Recent PR trend
- Readiness trend
- Number of workouts completed in the current cycle
- Stagnation duration
- Pain/fatigue flags

Outputs:

- `plan_ok`
- `monitor`
- `review_recommended`
- `deload_recommended`
- Reason codes
- Explanation

Reliability principle:

Plan review should not automatically rewrite the user's plan without confirmation. The system should first explain why review is recommended.

### 4.5 Coaching Explanation

Question:

> How should the system explain its decision so the user understands and follows it?

Inputs:

- Structured decision
- User profile
- Relevant knowledge snippets
- Recent user context

Outputs:

- Short user-facing explanation
- Action recommendation
- Optional educational note

Reliability principle:

LLM is well suited here. The explanation should be grounded in structured decision outputs and retrieved knowledge.

## 5. Rule vs LLM Boundary

The system should not use the LLM as the source of truth for numeric training decisions.

### Rules / Deterministic Logic Should Own

- Readiness score formula
- Readiness thresholds
- Load reduction percentage
- Volume reduction rules
- Maximum replan count
- Completion rate calculation
- PR detection
- Stagnation thresholds
- Plan schema validation
- State transition rules
- Safety gates for pain and severe fatigue

### LLM Should Own

- Explaining decisions in natural language
- Summarizing workout outcomes
- Turning free-form plan input into structured JSON, with validation afterward
- Answering exercise and training knowledge questions using RAG
- Generating coach-like comments from structured decision data
- Helping compare options when the rule system has already narrowed the valid choices

### Hybrid Decisions

Some decisions should combine both:

- Exercise substitution:
  - Rules define constraints.
  - LLM proposes substitutions from a controlled exercise library.
  - Validator checks allowed muscles/equipment/pain constraints.

- Plan review summary:
  - Rules detect stagnation or fatigue.
  - LLM explains likely causes and next steps.

- Long-term plan generation:
  - Rules define split, volume range, progression pattern, and deload structure.
  - LLM writes rationale and optionally formats the plan.

## 6. Agent Architecture

The system should avoid adding agents just to look complex. Agent count should follow decision boundaries.

Recommended core graph:

```text
Orchestrator
  -> ReadinessDecisionAgent
  -> WorkoutDecisionAgent
  -> ProgressionEvaluationAgent
  -> PlanReviewAgent
  -> ExplanationAgent
```

However, for near-term implementation, keep it simpler:

### Core Agents for v1

1. `orchestrator`
   - Reads intent and state.
   - Routes to the correct decision path.
   - Should stay thin.

2. `readiness_agent`
   - Owns daily readiness decision.
   - Can start as a renamed/refactored version of current `adjust_agent` logic.

3. `workout_agent`
   - Owns workout execution decisions.
   - Absorbs current `replan_agent` behavior.
   - Handles mid-workout adjustments.

4. `log_eval_agent`
   - Logs workout results.
   - Computes completion and PR signals.
   - Produces evaluation signals for future decisions.

5. `explanation_agent`
   - Converts structured decisions into user-facing language.
   - Can use RAG and LLM.

### Agents That Should Be Reconsidered

- `training_agent.py`
  - Useful future concept, but currently not wired.
  - Should not become central until plan schema is unified.

- `recovery_agent.py`
  - Contains richer readiness design.
  - Could become the future `readiness_agent`.

- `home_coach.py`
  - Useful interface agent.
  - Should remain outside the core training decision graph for now.

- `nutrition_agent.py`
  - Useful feature, but not central to the first adaptive training decision loop.

## 7. Future State Design

Current `CoachState` is a good starting point, but future state should be more explicit and layered.

Proposed conceptual state:

```python
CoachState = {
    "user": UserIdentity,
    "profile": UserProfile,
    "plan": PlanState,
    "readiness": ReadinessState,
    "workout_session": WorkoutSessionState,
    "progression": ProgressionState,
    "review": PlanReviewState,
    "decision_trace": list[DecisionTrace],
    "messages": list,
    "error": str,
}
```

### UserProfile

Should include:

- Age or birth date
- Height
- Weight
- Training start date
- Training level
- Goal
- Weekly availability
- Current estimated strength levels

### PlanState

Should include:

- Canonical plan schema version
- Split type
- Current cycle
- Current week
- Current day index
- Exercises
- Progression rules
- Deload rules

### ReadinessState

Should include:

- Sleep
- Stress
- Fatigue
- Pain areas
- Pain severity
- Computed score
- Level
- Adjustment policy
- Reason codes

### WorkoutSessionState

Should include:

- Today's planned exercises
- Adjusted exercises
- Current exercise index
- Completed exercises
- Failed/skipped exercises
- Replan count
- Replan reasons
- Session status

### ProgressionState

Should include:

- Per-exercise recent performance
- Last progression decision
- Suggested next load/reps/sets
- Plateau flags

### PlanReviewState

Should include:

- Completion trend
- Readiness trend
- PR trend
- Stagnation flags
- Recommendation

### DecisionTrace

Every important system decision should leave a trace:

```python
DecisionTrace = {
    "decision_type": "readiness | workout_adjustment | progression | plan_review",
    "inputs": {},
    "rule_result": {},
    "llm_used": False,
    "llm_summary": "",
    "final_decision": {},
    "reason_codes": [],
    "timestamp": "",
}
```

This is important for debugging, user trust, and application storytelling.

## 8. Canonical Plan Schema Direction

Current project has at least two macro plan formats:

- `weeks` format from `plan_agent`
- `days` format from `plan_edit`

Future design should choose one canonical schema.

Recommended direction:

```json
{
  "schema_version": "1.0",
  "split_type": "PPL_3",
  "cycle": {
    "length_days": 4,
    "days": [
      {
        "day_index": 0,
        "day_name": "Push",
        "type": "training",
        "exercises": []
      },
      {
        "day_index": 1,
        "day_name": "Pull",
        "type": "training",
        "exercises": []
      },
      {
        "day_index": 2,
        "day_name": "Legs",
        "type": "training",
        "exercises": []
      },
      {
        "day_index": 3,
        "day_name": "Rest",
        "type": "rest",
        "exercises": []
      }
    ]
  },
  "progression_policy": {
    "type": "double_progression"
  },
  "deload_policy": {
    "type": "readiness_and_cycle_based"
  }
}
```

This is better than a pure `weeks` schema for the current app because the UI already uses cycle-day indexing.

## 9. Evaluation Plan

To make this project credible, evaluation should be designed early.

### Product Metrics

- Workout completion rate
- Number of workouts completed per month
- Frequency of mid-workout replans
- Frequency of skipped workouts
- User adherence to suggested adjustments

### Training Metrics

- PR trend for squat/bench/deadlift
- Estimated 1RM trend
- Volume trend
- Exercise-level progression success rate

### Recovery Metrics

- Readiness score trend
- High fatigue frequency
- Pain flag frequency
- Deload recommendation frequency

### Decision Quality Metrics

- Percentage of decisions with reason codes
- Percentage of LLM explanations grounded in structured decisions
- Number of unsafe or invalid recommendations caught by validators

### Application Storytelling Metrics

For a master's application, the evaluation does not need to prove medical or athletic superiority. It should show that the system:

- Makes decisions consistently.
- Separates deterministic safety logic from LLM explanation.
- Tracks outcomes over time.
- Can be improved through feedback.

## 10. Six-Month Roadmap

### Month 1: Stabilize and Document

- Finish architecture review.
- Finish system design v1.
- Move documentation into `docs/`.
- Rewrite README around adaptive decision system.
- Keep behavior mostly unchanged.

### Month 2: State and Schema Cleanup

- Define canonical plan schema.
- Add plan validation helpers.
- Refactor `main.py` routing and session setup.
- Make `CoachState` more explicit.
- Add small tests for pure decision functions.

### Month 3: Decision Graph v1

- Fix mid-workout replanning route.
- Separate readiness decision from workout logging.
- Add reason codes.
- Add decision trace.
- Keep LLM behind structured inputs.

### Month 4: Progression and Plan Review

- Add per-exercise progression decision.
- Add plan review decision.
- Improve stagnation logic.
- Add user confirmation before plan rewrite.

### Month 5: Evaluation Layer

- Add simple dashboard for trends.
- Add synthetic/demo data.
- Compare static plan vs adaptive plan decisions.
- Write evaluation notes.

### Month 6: Portfolio Packaging

- Polish README.
- Add architecture diagram.
- Add screenshots or demo video.
- Write technical report.
- Prepare resume bullets and SOP project paragraph.

## 11. Near-Term Engineering Priorities

Do not start with new features.

Recommended next engineering steps:

1. Move `project_understanding_v0.md` into `docs/`.
2. Rewrite `README.md` after this design is accepted.
3. Define canonical plan schema in a doc or module.
4. Add tests for readiness scoring and plan parsing.
5. Fix `replan_agent` routing only after the intended behavior is written down.

## 12. Open Design Questions

- Should the first version of canonical plan schema be cycle-based only, or support both cycle and week views?
- Should daily readiness adjustment change weight, sets, RIR target, or all three?
- Should pain be a simple area list or include severity and movement pattern?
- Should plan review automatically generate a new plan or only recommend review?
- Should home chat ever trigger core training decisions, or should it remain advisory?
- Should nutrition stay a small supporting feature or become part of readiness/progression later?

## 13. Current Team Decision

For now, the project should optimize for:

- Target user: 3-18 month natural lifter.
- Core value: adaptive training decisions, not generic chat.
- Reliability model: rules for decisions, LLM for explanation and structured assistance.
- Architecture direction: fewer agents, clearer state, explicit decision traces.
- Portfolio value: a serious stateful AI system with measurable decisions.

