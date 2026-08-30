import os
import shutil
import uuid
from typing import List

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/materials", tags=["materials"])

UPLOAD_DIR = "uploads/materials"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload", response_model=schemas.MaterialOut)
def upload_material(
    title: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_teacher),
):
    ext = os.path.splitext(file.filename)[1]
    stored_name = f"{uuid.uuid4().hex}{ext}"
    stored_path = os.path.join(UPLOAD_DIR, stored_name)

    with open(stored_path, "wb") as out_file:
        shutil.copyfileobj(file.file, out_file)

    material = models.Material(
        title=title,
        filename=file.filename,
        file_path=stored_path,
        uploaded_by=current_user.id,
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    return material


@router.get("/", response_model=List[schemas.MaterialOut])
def list_materials(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return db.query(models.Material).order_by(models.Material.uploaded_at.desc()).all()


@router.get("/{material_id}/download")
def download_material(
    material_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    material = db.query(models.Material).filter(models.Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    return FileResponse(material.file_path, filename=material.filename)


@router.delete("/{material_id}", status_code=204)
def delete_material(
    material_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_teacher),
):
    material = db.query(models.Material).filter(models.Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    delete_file_quietly(material.file_path)
    db.delete(material)
    db.commit()
    return None


def delete_file_quietly(file_path: str) -> None:
    """Remove a file from disk if it exists; never raise on failure."""
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    except OSError:
        pass
