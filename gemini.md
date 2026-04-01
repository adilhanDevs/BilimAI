# Mondly-Style Lesson Engine — Backend Rules

This project is a production-grade Django + DRF backend for a language-learning system inspired by Mondly.

The system is NOT an MVP. All decisions must prioritize long-term scalability, clarity, and maintainability.

---

## 🚫 Critical Rules (DO NOT VIOLATE)

1. DO NOT move logic back into JSONField.
2. DO NOT create "God serializers".
3. DO NOT mix all step types into one model.
4. DO NOT break existing API without explicit migration strategy.
5. DO NOT add unnecessary abstraction layers.
6. DO NOT write code without explaining reasoning first.
7. DO NOT modify unrelated files.

---

## 🧠 Core Architecture

### LessonStep = Orchestrator

LessonStep is a base model that contains:
- lesson relation
- step_type
- ordering
- shared UI fields (prompt, instruction, hint)
- XP and metadata

It MUST NOT:
- contain step-specific logic
- contain complex JSON blobs
- contain options or answers

---

### StepDetail Models

Each step type MUST have its own model:

Examples:
- StepMultipleChoice
- StepFillBlank
- StepMatchPairs
- StepListenAndChoose
- StepSpeakPhrase

Each:
- uses OneToOneField → LessonStep
- contains only its own logic
- may have child tables (choices, tokens, pairs)

---

### Media Handling

Media is first-class.

Use:
- FileField / ImageField OR MediaAsset model

Never:
- store media URLs inside JSON
- hardcode paths

---

### Progress Tracking

Each step must support user interaction tracking.

Expected:
- user
- step
- result (correct/incorrect)
- attempts
- response_data
- timestamp

This is critical for analytics and AI.

---

## 🧱 Design Principles

Prefer:
- explicit models
- relational structure
- strong validation
- service layer
- predictable API

Avoid:
- magic
- implicit behavior
- hidden logic
- overuse of signals
- deeply nested serializers

---

## ⚙️ Backend Layers

### Models
- clean
- normalized
- explicit relations
- constraints where needed

### Serializers
Use dispatcher pattern:
- base LessonStepSerializer
- map step_type → detail serializer

Never:
- write 500-line serializer with if/else

---

### Service Layer

All creation logic must go through services.

Examples:
- create step + detail
- validate content
- attach choices/pairs/tokens
- enforce constraints

Views must stay thin.

---

### Validation

Validation must be strict and type-aware.

Examples:
- multiple choice → exactly 1 correct answer
- fill blank → blanks count == answers count
- reorder → valid token sequence
- speak → must have target text

---

## 🧩 API Design

Frontend must receive normalized structure:

```json
{
  "id": "uuid",
  "step_type": "multiple_choice",
  "prompt": "...",
  "instruction": "...",
  "xp": 2,
  "content": { ... }
}