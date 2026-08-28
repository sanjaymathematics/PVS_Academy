from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr

from .models import Role, QuestionType, AnswerSheetStatus


# ---------- Auth ----------
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: Role = Role.student


class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: Role

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Materials ----------
class MaterialOut(BaseModel):
    id: int
    title: str
    filename: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


# ---------- Quizzes ----------
class QuestionCreate(BaseModel):
    text: str
    type: QuestionType
    options: Optional[List[str]] = None       # required for mcq
    correct_option: Optional[int] = None       # required for mcq
    correct_value: Optional[float] = None      # required for numeric
    tolerance: Optional[float] = 0.0
    points: float = 1.0


class QuizCreate(BaseModel):
    title: str
    questions: List[QuestionCreate]


class QuestionOut(BaseModel):
    id: int
    text: str
    type: QuestionType
    options: Optional[List[str]] = None
    points: float

    class Config:
        from_attributes = True


class QuizOut(BaseModel):
    id: int
    title: str
    questions: List[QuestionOut]

    class Config:
        from_attributes = True


class QuizSubmission(BaseModel):
    # question_id -> selected option index (mcq) or numeric value (numeric), as string
    answers: dict[int, str]


class QuestionResult(BaseModel):
    question_id: int
    correct: bool
    points_awarded: float
    points_possible: float


class QuizResult(BaseModel):
    attempt_id: int
    score: float
    max_score: float
    breakdown: List[QuestionResult]


# ---------- Answer sheets ----------
class AnswerSheetOut(BaseModel):
    id: int
    assignment_title: str
    filename: str
    status: AnswerSheetStatus
    suggested_score: Optional[float]
    max_score: float
    ai_feedback: Optional[str]
    final_score: Optional[float]
    uploaded_at: datetime

    class Config:
        from_attributes = True


class ApproveRequest(BaseModel):
    final_score: Optional[float] = None  # teacher can override the AI suggestion
