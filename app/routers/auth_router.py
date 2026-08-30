from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db
from .quizzes import delete_quiz_cascade
from .materials import delete_file_quietly

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=schemas.UserOut)
def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == user_in.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    if user_in.role == models.Role.teacher:
        if not user_in.teacher_code or user_in.teacher_code != auth.TEACHER_SIGNUP_CODE:
            raise HTTPException(status_code=403, detail="Invalid teacher signup code")

    user = models.User(
        name=user_in.name,
        email=user_in.email,
        hashed_password=auth.hash_password(user_in.password),
        role=user_in.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    email = form_data.username

    if auth.is_login_locked(email):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again in a few minutes.",
        )

    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        auth.register_failed_login(email)
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    auth.clear_failed_logins(email)
    token = auth.create_access_token({"sub": str(user.id), "role": user.role.value})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


@router.put("/change-password")
def change_password(
    body: schemas.ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if not auth.verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.hashed_password = auth.hash_password(body.new_password)
    db.commit()
    return {"detail": "Password updated"}


@router.delete("/me", status_code=204)
def delete_my_account(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    _cascade_delete_user(db, current_user)
    return None


@router.get("/users", response_model=List[schemas.UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_teacher),
):
    return db.query(models.User).order_by(models.User.created_at.desc()).all()


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_teacher),
):
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(404, "User not found")
    if target.id == current_user.id:
        raise HTTPException(400, "Use DELETE /auth/me to delete your own account")
    _cascade_delete_user(db, target)
    return None


@router.post("/users/{user_id}/reset-password", response_model=schemas.ResetPasswordOut)
def reset_user_password(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_teacher),
):
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(404, "User not found")
    new_password = auth.generate_temp_password()
    target.hashed_password = auth.hash_password(new_password)
    db.commit()
    return schemas.ResetPasswordOut(email=target.email, new_password=new_password)


def _cascade_delete_user(db: Session, user: models.User) -> None:
    """Remove a user along with everything that references them, so no
    orphaned foreign keys are left behind on Postgres."""

    # Answer sheets this user submitted (delete the file + row)
    sheets = db.query(models.AnswerSheet).filter(models.AnswerSheet.student_id == user.id).all()
    for s in sheets:
        delete_file_quietly(s.file_path)
        db.delete(s)

    # Answer sheets this user reviewed as a teacher — keep the sheet, just clear the reviewer
    db.query(models.AnswerSheet).filter(models.AnswerSheet.reviewed_by == user.id).update(
        {models.AnswerSheet.reviewed_by: None}
    )

    # This user's quiz attempts
    db.query(models.QuizAttempt).filter(models.QuizAttempt.student_id == user.id).delete()

    # Materials this user uploaded (delete the file + row)
    materials = db.query(models.Material).filter(models.Material.uploaded_by == user.id).all()
    for m in materials:
        delete_file_quietly(m.file_path)
        db.delete(m)

    # Quizzes this user created (cascades their questions + attempts)
    quizzes = db.query(models.Quiz).filter(models.Quiz.created_by == user.id).all()
    for q in quizzes:
        delete_quiz_cascade(db, q)

    db.delete(user)
    db.commit()
