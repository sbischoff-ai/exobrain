## Morning planning check-in

Great question — let's turn this into a focused plan for today.

### Top priorities (suggested)
1. **Ship one meaningful outcome** (for example: finish and review a feature branch).
2. **Reduce uncertainty** (identify one blocker and resolve it early).
3. **Capture reusable notes** (summarize decisions so future-you can move faster).

### Suggested timeline
- **09:00–10:30** Deep work on highest-impact task.
- **10:30–10:45** Break + quick inbox triage.
- **10:45–12:00** Continue execution, aim for a testable checkpoint.
- **After lunch** Reviews, follow-ups, and planning tomorrow's next action.

### Quick reflection prompt
Before you start, write one sentence: *"If today goes well, the most important result will be..."*

If you'd like, I can convert this into a checklist with estimated durations based on your calendar.

--- message ---

## Research summary draft

I pulled together a concise research pattern you can reuse:

### Claim to verify
> "Asynchronous streaming always improves perceived latency."

### What tends to be true
- Streaming usually improves **time-to-first-feedback**.
- It does **not always** reduce total completion time.
- Perceived quality depends on chunk cadence, coherence, and UI behavior.

### What to measure
| Metric | Why it matters |
| --- | --- |
| Time to first token | Perceived responsiveness |
| Time to final token | End-to-end completion |
| Inter-chunk gap p95 | Smoothness/readability |
| User interruption rate | Whether streaming helps task success |

### Recommendation
Run an A/B test with logging for both first-token and full-response latency. Pair quantitative metrics with 5–10 user interviews to catch usability issues not visible in traces.

--- message ---

## Project unblock assistant

Let's get you unstuck quickly. Here's a structured triage:

### 1) Define the blocker precisely
- What are you trying to do?
- What did you expect to happen?
- What happened instead (exact error/output)?

### 2) Fastest path to progress
- Create a minimal reproduction.
- Confirm assumptions one by one.
- Narrow to a single failing boundary (API, DB, auth, or UI state).

### 3) Decision tree
- If it's a **schema mismatch** -> run migrations and compare expected tables.
- If it's **state drift** -> reset local fixtures and rerun a focused test.
- If it's **integration only** -> isolate with deterministic mocks at external boundaries.

### 4) Next action
Send me the failing command and relevant log snippet; I'll help you produce a shortest-path fix plan with confidence checks.
