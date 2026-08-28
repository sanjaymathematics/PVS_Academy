"""
Answer-sheet grading pipeline.

This module is intentionally isolated from the rest of the app so the mock
implementation below can be swapped for real OCR + LLM calls without
touching any router or database code.

Real implementation would look roughly like:

    import requests

    def extract_text(file_path: str) -> str:
        # Mathpix OCR (purpose-built for handwritten math -> LaTeX)
        with open(file_path, "rb") as f:
            r = requests.post(
                "https://api.mathpix.com/v3/text",
                headers={"app_id": MATHPIX_ID, "app_key": MATHPIX_KEY},
                files={"file": f},
            )
        return r.json()["text"]

    def grade_with_llm(extracted_text: str, rubric: str, answer_key: str) -> dict:
        # Call Claude with the extracted text, rubric, and answer key.
        # Ask for a strict JSON response: {"score": ..., "max_score": ...,
        # "feedback": "...", "per_step_notes": [...]}
        # Always treat this as a first-pass suggestion — a teacher reviews
        # and approves before it becomes the final grade (see routers/answer_sheets.py).
        ...

Alternative to a separate OCR step: send the scanned image directly to a
vision-capable LLM (e.g. Claude with an image input) and ask it to read and
grade the handwriting in a single call.
"""

import random


def mock_grade_answer_sheet(file_path: str, max_score: float = 10.0) -> dict:
    """
    Placeholder so the API is fully runnable without any external API keys.
    Replace this function's body with a real OCR + LLM call.
    """
    suggested_score = round(random.uniform(0.5, 1.0) * max_score, 1)
    feedback = (
        "Mock grading result: steps 1-2 correct, minor arithmetic slip in "
        "step 3. Replace this stub with a real OCR + LLM pipeline before "
        "using this for actual grading."
    )
    return {"suggested_score": suggested_score, "feedback": feedback}
