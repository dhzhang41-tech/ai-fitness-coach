# MVP Decision Policy v0

## 1. Purpose

This document defines the first usable decision policy for the project.

The goal is not to build the perfect adaptive training system. The goal is to create a small, conservative, explainable loop that can be used in real training for 2-4 weeks.

The system should help the target user make better decisions without automatically over-changing the long-term plan.

## 2. MVP Principle

MVP v0.1 follows five principles:

- Keep rules simple.
- Prefer conservative adjustments.
- Explain every decision.
- Record outcomes for later review.
- Do not automatically rewrite the long-term plan.

This version is a training decision experiment, not a complete coaching replacement.

## 3. Target User

MVP v0.1 targets:

> A natural lifter with 3-18 months of training experience who has a structured plan but is unsure how to adjust when readiness, fatigue, pain, or workout execution changes.

The MVP does not optimize for complete beginners, advanced competitors, or rehab/medical use cases.

## 4. Existing Agent Usage

MVP v0.1 should be built on the current codebase instead of replacing it.

### Core Agents Used Now

- `orchestrator`
  - Routes graph execution.
  - Should remain thin.

- `plan_agent`
  - Generates initial macro plans.
  - Stays as-is for MVP unless plan schema issues block usage.

- `adjust_agent`
  - Owns simple readiness assessment and daily adjustment.
  - Used for pre-workout readiness decisions.

- `replan_agent`
  - Owns mid-workout adjustment.
  - Should be activated when `replan_reason` exists.

- `log_agent`
  - Owns workout logging and simple evaluation.
  - Should run only when the workout is being finalized.

### Agents Kept but Frozen

- `training_agent`
  - Experimental future training-plan agent.
  - Not part of MVP v0.1 graph.

- `recovery_agent`
  - Experimental future readiness/recovery agent.
  - Not part of MVP v0.1 graph.

### Peripheral Agents

- `home_coach`
  - Remains a home-page advisory/chat agent.
  - Should not trigger core training decisions in MVP v0.1.

- `nutrition_agent`
  - Remains a protein estimation helper.
  - Does not affect readiness, progression, or plan review in MVP v0.1.

## 5. Readiness Decision Policy

Readiness is evaluated before training.

Inputs:

- Sleep score: 1-10
- Stress score: 1-10
- Fatigue score: 1-10
- Pain areas: list of strings

Current formula:

```text
readiness_score = sleep * 0.4 + (10 - stress) * 0.3 + (10 - fatigue) * 0.3
```

### Readiness Levels

#### Normal

Condition:

```text
readiness_score >= 7
and no serious pain flag
```

Decision:

- Train as planned.
- No load reduction.
- No volume reduction.

User-facing explanation:

> State looks good. Follow the planned workout and record execution quality.

#### Reduced

Condition:

```text
5 <= readiness_score < 7
or mild pain exists
```

Decision:

- Reduce load by about 10-20%, or use current code's intensity policy.
- Reduce one set from major exercises if needed.
- Avoid pushing to failure.
- Keep the workout structure.

User-facing explanation:

> State is not ideal. The goal is to keep training momentum while reducing fatigue cost.

#### Recovery / Rest Bias

Condition:

```text
readiness_score < 5
or multiple pain areas exist
```

Decision:

- Prefer recovery-style training or very conservative reduced training.
- Do not chase PRs.
- Avoid high-risk compound top sets.
- Keep recommendation conservative.

User-facing explanation:

> Today's goal is recovery and consistency, not overload.

### MVP Non-Goals

MVP v0.1 does not:

- Use HRV.
- Use wearable data.
- Diagnose injuries.
- Create detailed pain-specific substitutions.
- Automatically trigger long-term plan rewrite from one bad readiness day.

## 6. Mid-Workout Replan Policy

Mid-workout replanning happens only when the user explicitly reports a problem.

Inputs:

- `replan_reason`
- Completed exercises
- Current plan
- Remaining exercises
- Replan count

### Supported Reasons

#### Too Heavy

Reason:

```text
太重
```

Decision:

- Reduce remaining exercise load by about 15-20%.
- Keep sets unchanged unless user also reports fatigue.

Goal:

- Preserve movement practice and completion.

#### Too Tired

Reason:

```text
太累
```

Decision:

- Reduce remaining exercises by 1 set where possible.
- Keep load mostly unchanged if safe.

Goal:

- Reduce total fatigue while preserving the plan structure.

#### Pain / Discomfort

Reason:

```text
部位不舒服
```

Decision:

- MVP should not confidently diagnose or aggressively substitute.
- Remove or skip movements that stress the uncomfortable area if obvious.
- Encourage conservative handling.
- Log the pain-related reason for later review.

Goal:

- Avoid risky advice.

#### No Time

Reason:

```text
没时间
```

Decision:

- Keep only the most important 2-3 remaining exercises.
- Prefer compound/main movements before isolation movements.

Goal:

- Save the highest-value training work.

### Replan Limit

Current policy:

```text
maximum replans per workout = 2
```

After the limit:

- Recommend ending or logging the workout.
- Do not continue to generate new adjustments.

## 7. Logging and Evaluation Policy

Workout logging happens at the end of the workout.

The system should record:

- Planned exercises
- Completed exercises
- Actual weight
- Sets done
- Last reps
- Feeling
- Readiness inputs
- Completion rate
- Replan count
- Whether the workout was adjusted

### Completion Rate

Completion rate should be treated as an observation signal, not an immediate trigger for plan rewrite.

Interpretation:

- `>= 0.9`: strong execution
- `0.7 - 0.89`: acceptable execution
- `< 0.7`: weak execution, monitor if repeated

### PR Detection

MVP can keep simple estimated PR detection for big-three lifts.

PR detection should:

- Be logged.
- Be celebrated.
- Not automatically change the whole plan.

## 8. Plan Review Policy

MVP v0.1 does not automatically rewrite long-term plans.

It may recommend review when repeated signals appear.

### Review Signals

Plan review may be recommended if any of these persist:

- Low completion rate across multiple workouts.
- Repeated readiness below normal.
- Repeated mid-workout replans.
- Big-three PR stagnation over several weeks.
- Repeated pain-related adjustments.

### MVP Behavior

When review is recommended:

- Set or display a `plan_stale` style signal.
- Explain why review may be needed.
- Ask the user to confirm before generating or editing a new macro plan.

Do not:

- Automatically replace the macro plan.
- Infer complex periodization changes from limited data.
- Treat one bad workout as plan failure.

## 9. Graph Routing Policy

MVP graph routing should follow this intent:

```text
review_macro_plan
  -> orchestrator
  -> plan_agent
  -> END

start_workout with replan_reason
  -> orchestrator
  -> replan_agent
  -> END

start_workout with abnormal readiness and no replan_reason
  -> orchestrator
  -> adjust_agent
  -> log_agent
  -> END

start_workout with normal readiness and no replan_reason
  -> orchestrator
  -> log_agent
  -> END
```

Important distinction:

- Mid-workout replanning should update `current_plan`.
- Workout-end logging should write to the database.

This means future code should avoid logging a workout during a mid-workout replan action.

## 10. Rule vs LLM Policy

### Rules Decide

- Readiness score
- Readiness level
- Replan strategy
- Completion rate
- PR detection
- Replan count limit
- Whether plan review is only suggested

### LLM Explains

- Why the adjustment is recommended.
- How the user should think about today's goal.
- Encouragement and coaching tone.
- Knowledge Q&A.
- Free-form plan parsing.

The LLM should not be the only source of truth for numeric decisions.

## 11. What MVP v0.1 Explicitly Does Not Do

MVP v0.1 does not:

- Automatically rewrite long-term plans after one workout.
- Fully solve progression policy.
- Use advanced `training_agent` and `recovery_agent`.
- Diagnose injuries.
- Implement advanced pain-specific substitution logic.
- Optimize hypertrophy programming perfectly.
- Try to support every user type.

## 12. Success Criteria

MVP v0.1 is successful if:

- The user can complete real workouts with the app.
- Readiness adjustment feels understandable and not reckless.
- Mid-workout replanning works without accidentally logging the workout.
- Logs preserve enough information to review later.
- The system produces useful review signals after 2-4 weeks.
- The codebase becomes easier to reason about, not more complex.

## 13. Next Engineering Steps

Recommended implementation order:

1. Fix graph routing so `replan_reason` routes to `replan_agent`.
2. Ensure mid-workout replan does not call `log_agent`.
3. Keep `adjust_agent` behavior conservative.
4. Add reason fields or notes to make decisions traceable.
5. Later, move `project_understanding_v0.md` into `docs/`.
6. Later, begin plan schema unification.

