# Slate — teaching platform backend

A FastAPI backend covering the three pieces from the design: course materials,
auto-graded quizzes, and an OCR/LLM-assisted answer-sheet review queue.

Tested end-to-end (register → login → create quiz → submit → auto-grade →
upload answer sheet → mock-grade → teacher approve) before delivery.

## Setup

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Runs on SQLite by default (`teaching_platform.db`, created automatically).
For production, set `DATABASE_URL` to a Postgres connection string:

```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/teaching_platform"
```

Also set a real `SECRET_KEY` in production — the default in `app/auth.py` is
for local development only:

```bash
export SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
```

Once running:
- The **app itself** is at **http://localhost:8000/app/** — this is the real frontend, wired to the live API (login/register screen, then materials, quizzes, and answer sheets all talking to the backend below).
- Interactive API docs are at **http://localhost:8000/docs**.

The frontend is served by this same FastAPI process (`app/main.py` mounts `frontend/` as static files), so there's no separate server to run and no CORS configuration needed — it's all one origin.

## How the three pieces map to endpoints

**Materials**
- `POST /materials/upload` (teacher only) — multipart form: `title`, `file`
- `GET /materials/` — list all materials

**Quizzes — auto-graded on submit**
- `POST /quizzes/` (teacher only) — create a quiz with MCQ and/or numeric questions
- `GET /quizzes/{id}` — fetch a quiz (correct answers are never sent to the client)
- `POST /quizzes/{id}/submit` — submit answers, get back a score and a per-question breakdown instantly. MCQ is exact-match; numeric questions compare against `correct_value` within a `tolerance` you set per question.

**Answer sheets — OCR/LLM pipeline with a mandatory teacher review step**
- `POST /answer-sheets/upload` — student uploads a scanned PDF/image; grading runs immediately (see below) and the sheet lands as `graded_pending_review`
- `GET /answer-sheets/?status=graded_pending_review` — teacher's review queue
- `POST /answer-sheets/{id}/approve` — teacher finalizes the score, optionally overriding the AI suggestion

The grading itself lives in `app/grading/pipeline.py`, isolated on purpose.
Right now it's a mock (`mock_grade_answer_sheet`) so the whole API runs with
zero external API keys. The docstring at the top of that file shows exactly
what a real implementation looks like — Mathpix OCR (or a vision LLM
directly on the scanned image) feeding into a Claude call that scores
against your rubric and answer key. Swap that one function's body; nothing
else in the app needs to change.

By design, `upload` never sets a `final_score` directly — only `approve`
does. A suggested AI score is never the grade of record until a teacher
signs off.

## Auth

Standard JWT bearer auth. Register with a `role` of `teacher` or `student`,
log in via `POST /auth/login` (OAuth2 password form: `username` = email,
`password`), then send `Authorization: Bearer <token>` on everything else.
`require_teacher` guards the endpoints only a teacher should touch (creating
quizzes, uploading materials, approving answer sheets).

## Trying it out

1. Run the server, visit `http://localhost:8000/app/`.
2. Click "Create an account" — register once as a teacher, once as a student (two different emails, two browser sessions or just sign out/in between).
3. As the teacher: upload a material, click "+ Create demo quiz" (adds the sequences-and-limits quiz from the design mockup).
4. As the student: open the quiz from the list, answer it, submit — see it auto-graded instantly. Upload a mock answer sheet (any file) — it runs through the mock grading pipeline immediately.
5. Back as the teacher: open Answer sheets, see the AI-suggested score, click Approve.

## What's deliberately left out (next steps)

- **Background jobs**: grading runs inline on upload for simplicity. Once
  real OCR/LLM calls are wired in, move `_run_grading` in
  `routers/answer_sheets.py` to a task queue (Celery, RQ, or FastAPI's
  `BackgroundTasks` at minimum) so uploads don't block on a slow API call.
- **File validation**: no file-type/size limits yet — add them before
  accepting uploads from real students.
- **Pagination**: list endpoints return everything; fine for one course,
  not for scale.
- **CORS**: not configured — add `CORSMiddleware` in `app/main.py` once you
  know which frontend origin(s) will call this API.
