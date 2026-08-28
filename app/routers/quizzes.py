import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


@router.get("/", response_model=List[schemas.QuizOut])
def list_quizzes(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    quizzes = db.query(models.Quiz).order_by(models.Quiz.created_at.desc()).all()
    return [_serialize_quiz(q) for q in quizzes]


@router.post("/", response_model=schemas.QuizOut)
def create_quiz(
    quiz_in: schemas.QuizCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_teacher),
):
    quiz = models.Quiz(title=quiz_in.title, created_by=current_user.id)
    db.add(quiz)
    db.flush()  # get quiz.id before adding questions

    for q in quiz_in.questions:
        if q.type == models.QuestionType.mcq:
            if q.options is None or q.correct_option is None:
                raise HTTPException(400, "MCQ questions need options and correct_option")
        if q.type == models.QuestionType.numeric and q.correct_value is None:
            raise HTTPException(400, "Numeric questions need correct_value")

        question = models.Question(
            quiz_id=quiz.id,
            text=q.text,
            type=q.type,
            options_json=json.dumps(q.options) if q.options else None,
            correct_option=q.correct_option,
            correct_value=q.correct_value,
            tolerance=q.tolerance or 0.0,
            points=q.points,
        )
        db.add(question)

    db.commit()
    db.refresh(quiz)
    return _serialize_quiz(quiz)


@router.get("/{quiz_id}", response_model=schemas.QuizOut)
def get_quiz(
    quiz_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    quiz = db.query(models.Quiz).filter(models.Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    return _serialize_quiz(quiz)


@router.post("/{quiz_id}/submit", response_model=schemas.QuizResult)
def submit_quiz(
    quiz_id: int,
    submission: schemas.QuizSubmission,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    quiz = db.query(models.Quiz).filter(models.Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(404, "Quiz not found")

    total_score = 0.0
    max_score = 0.0
    breakdown = []

    for question in quiz.questions:
        max_score += question.points
        given = submission.answers.get(question.id)
        correct = False

        if given is not None:
            if question.type == models.QuestionType.mcq:
                try:
                    correct = int(given) == question.correct_option
                except ValueError:
                    correct = False
            else:  # numeric
                try:
                    correct = abs(float(given) - question.correct_value) <= (question.tolerance or 0.0)
                except ValueError:
                    correct = False

        awarded = question.points if correct else 0.0
        total_score += awarded
        breakdown.append(
            schemas.QuestionResult(
                question_id=question.id,
                correct=correct,
                points_awarded=awarded,
                points_possible=question.points,
            )
        )

    attempt = models.QuizAttempt(
        quiz_id=quiz.id,
        student_id=current_user.id,
        score=total_score,
        max_score=max_score,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return schemas.QuizResult(
        attempt_id=attempt.id,
        score=total_score,
        max_score=max_score,
        breakdown=breakdown,
    )


def _serialize_quiz(quiz: models.Quiz) -> schemas.QuizOut:
    questions_out = []
    for q in quiz.questions:
        questions_out.append(
            schemas.QuestionOut(
                id=q.id,
                text=q.text,
                type=q.type,
                options=json.loads(q.options_json) if q.options_json else None,
                points=q.points,
            )
        )
    return schemas.QuizOut(id=quiz.id, title=quiz.title, questions=questions_out)
