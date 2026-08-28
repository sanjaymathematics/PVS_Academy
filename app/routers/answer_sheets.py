import os
import shutil
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db
from ..grading.pipeline import mock_grade_answer_sheet

router = APIRouter(prefix="/answer-sheets", tags=["answer-sheets"])

UPLOAD_DIR = "uploads/answer_sheets"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload", response_model=schemas.AnswerSheetOut)
def upload_answer_sheet(
    assignment_title: str = Form(...),
    max_score: float = Form(10.0),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    ext = os.path.splitext(file.filename)[1]
    stored_name = f"{uuid.uuid4().hex}{ext}"
    stored_path = os.path.join(UPLOAD_DIR, stored_name)

    with open(stored_path, "wb") as out_file:
        shutil.copyfileobj(file.file, out_file)

    sheet = models.AnswerSheet(
        student_id=current_user.id,
        assignment_title=assignment_title,
        filename=file.filename,
        file_path=stored_path,
        max_score=max_score,
        status=models.AnswerSheetStatus.uploaded,
    )
    db.add(sheet)
    db.commit()
    db.refresh(sheet)

    # Run grading immediately for this demo. In production you'd likely
    # push this to a background task queue (Celery/RQ) since OCR + LLM
    # calls are slow enough to block a request.
    _run_grading(sheet, db)
    return sheet


@router.get("/", response_model=List[schemas.AnswerSheetOut])
def list_answer_sheets(
    status: Optional[models.AnswerSheetStatus] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    query = db.query(models.AnswerSheet)
    # Students only see their own submissions; teachers see everything.
    if current_user.role == models.Role.student:
        query = query.filter(models.AnswerSheet.student_id == current_user.id)
    if status:
        query = query.filter(models.AnswerSheet.status == status)
    return query.order_by(models.AnswerSheet.uploaded_at.desc()).all()


@router.post("/{sheet_id}/approve", response_model=schemas.AnswerSheetOut)
def approve_answer_sheet(
    sheet_id: int,
    body: schemas.ApproveRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_teacher),
):
    sheet = db.query(models.AnswerSheet).filter(models.AnswerSheet.id == sheet_id).first()
    if not sheet:
        raise HTTPException(404, "Answer sheet not found")

    sheet.final_score = body.final_score if body.final_score is not None else sheet.suggested_score
    sheet.status = models.AnswerSheetStatus.approved
    sheet.reviewed_by = current_user.id
    sheet.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(sheet)
    return sheet


def _run_grading(sheet: models.AnswerSheet, db: Session):
    result = mock_grade_answer_sheet(sheet.file_path, max_score=sheet.max_score)
    sheet.suggested_score = result["suggested_score"]
    sheet.ai_feedback = result["feedback"]
    sheet.status = models.AnswerSheetStatus.graded_pending_review
    sheet.graded_at = datetime.utcnow()
    db.commit()
    db.refresh(sheet)
