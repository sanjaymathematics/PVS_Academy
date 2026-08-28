import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, Enum
)
from sqlalchemy.orm import relationship

from .database import Base


class Role(str, enum.Enum):
    teacher = "teacher"
    student = "student"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(Role), nullable=False, default=Role.student)
    created_at = Column(DateTime, default=datetime.utcnow)


class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    uploader = relationship("User")


class QuestionType(str, enum.Enum):
    mcq = "mcq"
    numeric = "numeric"


class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    questions = relationship("Question", back_populates="quiz", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"))
    text = Column(Text, nullable=False)
    type = Column(Enum(QuestionType), nullable=False)

    # MCQ fields
    options_json = Column(Text, nullable=True)      # JSON-encoded list of option strings
    correct_option = Column(Integer, nullable=True)  # index into options_json

    # Numeric fields
    correct_value = Column(Float, nullable=True)
    tolerance = Column(Float, nullable=True, default=0.0)

    points = Column(Float, default=1.0)

    quiz = relationship("Quiz", back_populates="questions")


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"))
    student_id = Column(Integer, ForeignKey("users.id"))
    score = Column(Float, nullable=False)
    max_score = Column(Float, nullable=False)
    submitted_at = Column(DateTime, default=datetime.utcnow)

    quiz = relationship("Quiz")
    student = relationship("User")


class AnswerSheetStatus(str, enum.Enum):
    uploaded = "uploaded"
    graded_pending_review = "graded_pending_review"
    approved = "approved"


class AnswerSheet(Base):
    __tablename__ = "answer_sheets"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"))
    assignment_title = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    status = Column(Enum(AnswerSheetStatus), default=AnswerSheetStatus.uploaded)

    suggested_score = Column(Float, nullable=True)
    max_score = Column(Float, default=10.0)
    ai_feedback = Column(Text, nullable=True)

    final_score = Column(Float, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    uploaded_at = Column(DateTime, default=datetime.utcnow)
    graded_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    student = relationship("User", foreign_keys=[student_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
