



new lessons system:
 Frontend Integration Guide: Lesson Engine

  This guide provides the necessary technical details for the frontend team to implement the learning flow. The backend is already production-hardened and localized.

  ---

  1. High-Level User Flow

   1. Discovery: User navigates to a Category and selects a Lesson.
   2. Initialization: 
       * Fetch Lesson Progress to see if a session already exists.
       * Fetch Lesson Steps.
   3. Execution: 
       * Render steps one-by-one based on sort_order.
       * Submit attempts for each step.
       * Handle the Session Snapshot returned by every attempt to update hearts and XP in the UI.
   4. Special Flow (Speaking): 
       * Steps of type speak_phrase require audio upload and async polling.
   5. Completion: 
       * When the session snapshot shows status: "completed", show the success screen.
       * If hearts_remaining: 0 or snapshot shows is_failed: true, show the game-over screen.

  ---

  2. Key Endpoints

  Fetch Lesson Steps
   * Method: GET
   * Path: /api/lessons/{lesson_id}/steps/?lang={ky|en|ru}
   * Purpose: Gets all exercises for a lesson.
   * Notes: Use the lang parameter to get pre-resolved localized strings in prompt_text and instruction_text.

  Submit Step Attempt
   * Method: POST
   * Path: /api/attempts/submit/
   * Payload:

   1     {
   2       "session_id": "UUID",
   3       "step_id": "UUID",
   4       "payload": { ...step_specific_data... }
   5     }
   * Response: Standardized AttemptResponse containing is_correct, xp_awarded, and a full session snapshot.

  Speaking Submission
   * Method: POST
   * Path: /api/speaking/submissions/
   * Payload: Multipart/form-data with session_id, step_id, and audio_file.
   * Response: Returns a submission_id and initial status (pending).

  Speaking Polling
   * Method: GET
   * Path: /api/speaking/submissions/{submission_id}/
   * Purpose: Poll this every 1-2 seconds until status is completed.
   * Response: Includes is_correct, score, and xp_awarded.

  ---

  3. Step Type Rendering Guide


  ┌──────────────────┬─────────────────────────────────────────┬───────────────────────────────────────────┐
  │ Step Type        │ UI Interaction                          │ Submission Payload                        │
  ├──────────────────┼─────────────────────────────────────────┼───────────────────────────────────────────┤
  │ multiple_choice  │ Select one option from choices.         │ {"selected_choice_id": "UUID"}            │
  │ fill_blank       │ Input text into [[blank]] placeholders. │ {"answers": ["string", "string"]}         │
  │ match_pairs      │ Connect left items to right items.      │ {"pairs": [["left_id", "right_id"], ...]} │
  │ reorder_sentence │ Arrange tokens in the correct order.    │ {"token_ids": ["UUID", "UUID", ...]}      │
  │ type_translation │ Type the translation of source_text.    │ {"answer": "string"}                      │
  │ speak_phrase     │ Record and upload audio.                │ N/A (Uses Speaking API)                   │
  └──────────────────┴─────────────────────────────────────────┴───────────────────────────────────────────┘

  ---

  4. Session & Progress Management

  The Session Snapshot
  Every time you submit an attempt (or poll speaking status), the backend returns a session object. This is your source of truth for the UI.

  Snapshot Fields to watch:
   * hearts_remaining: Update the "Lives" counter.
   * xp_earned: Update the lesson score.
   * completed_steps_count: Update the progress bar.
   * status: If completed or failed, trigger the end-of-lesson logic.

  State Strategy Recommendation
   * Component State: Store the current step's user input (e.g., current text in a blank).
   * Global/Context State: Store the session_id and the latest session snapshot.
   * Optimistic UI: You can optimistically show "Correct/Incorrect" animations, but XP and Hearts must only be updated using the backend snapshot.

  ---

  5. Async Speaking Flow

   1. Record: Capture user audio (WAV/AAC/MP3).
   2. Upload: Send to POST /api/speaking/submissions/.
   3. Wait: Show a "Processing..." spinner.
   4. Poll: Call GET /api/speaking/submissions/{id}/.
       * If pending or processing: Continue waiting.
       * If completed: Check is_correct. Update UI using the snapshot.
       * If failed: Show an error (e.g., "Audio too quiet") and allow retry if allow_retry is true in the step content.

  ---

  6. Localization (?lang=)

  The backend handles translation resolution. You do not need to look up translation groups manually.
   * Use prompt_text for the question.
   * Use instruction_text for the hint.
   * All nested content (choices, tokens, pairs) is pre-translated based on the ?lang= parameter provided in the initial GET steps call.

  ---

  7. Example Payloads

  Step Response (Partial)

    1 {
    2   "id": "step-uuid",
    3   "step_type": "multiple_choice",
    4   "prompt_text": "Select the correct word",
    5   "instruction_text": "Choose the one that means 'Hello'",
    6   "content": {
    7     "choices": [
    8       { "id": "choice-1", "text": "Салам" },
    9       { "id": "choice-2", "text": "Жок" }
   10     ]
   11   }
   12 }

  Attempt Response

    1 {
    2   "is_correct": true,
    3   "score": 100,
    4   "xp_awarded": 10,
    5   "feedback": {},
    6   "session": {
    7     "id": "session-uuid",
    8     "status": "active",
    9     "hearts_remaining": 5,
   10     "xp_earned": 50,
   11     "completed_steps_count": 4,
   12     "total_steps": 10
   13   }
   14 }

  ---

  8. Implementation Checklist

   - [ ] Add ?lang= to the Lesson Steps fetch.
   - [ ] Implement a "Step Factory" component that renders the correct sub-component based on step_type.
   - [ ] Ensure the "Check" button is disabled during Speaking processing state.
   - [ ] Handle 403 errors by redirecting to the "Not Enrolled" or "Subscription Required" page.
   - [ ] Add a confirmation modal if the user tries to exit an active session.
   - [ ] Trigger a refresh of GET /api/progress/ after a lesson is completed to update the dashboard.
