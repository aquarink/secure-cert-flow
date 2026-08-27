"""
Papers and Submissions API Router
Handles conference paper catalog, search autocomplete, bulk Excel import, and paper management.
"""

import io
import uuid
import pandas as pd
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models import Event, Paper, User
from app.schemas.paper import PaperCreate, PaperUpdate, PaperResponse, PaperBulkCreate
from app.api.deps import get_current_user

router = APIRouter(tags=["Papers & Submissions"])


@router.get("/events/{event_id}/papers", response_model=List[PaperResponse])
def list_event_papers(
    event_id: uuid.UUID,
    q: Optional[str] = Query(None, description="Search query for title, authors, or paper code"),
    db: Session = Depends(get_db)
):
    """
    Public / Panitia endpoint to search and list papers for an event.
    Used for autocomplete in attendance form and dashboard management.
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Acara tidak ditemukan.")

    query = db.query(Paper).filter(Paper.event_id == event_id)
    if q:
        search_pattern = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Paper.title.ilike(search_pattern),
                Paper.paper_code.ilike(search_pattern),
                Paper.authors.ilike(search_pattern),
                Paper.presenter_name.ilike(search_pattern)
            )
        )

    return query.order_by(Paper.paper_code.asc(), Paper.created_at.asc()).all()


@router.post("/events/{event_id}/papers", response_model=PaperResponse, status_code=status.HTTP_201_CREATED)
def create_paper(
    event_id: uuid.UUID,
    paper_in: PaperCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Creates a new paper entry for an event (Organizer only)"""
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Acara tidak ditemukan.")

    paper = Paper(
        event_id=event_id,
        paper_code=paper_in.paper_code,
        title=paper_in.title.strip(),
        authors=paper_in.authors.strip() if paper_in.authors else None,
        presenter_name=paper_in.presenter_name.strip() if paper_in.presenter_name else None
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)
    return paper


@router.post("/events/{event_id}/papers/bulk", response_model=List[PaperResponse], status_code=status.HTTP_201_CREATED)
def create_bulk_papers(
    event_id: uuid.UUID,
    bulk_in: PaperBulkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Bulk creates multiple paper entries for an event (Organizer only)"""
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Acara tidak ditemukan.")

    created_papers = []
    for p_in in bulk_in.papers:
        paper = Paper(
            event_id=event_id,
            paper_code=p_in.paper_code,
            title=p_in.title.strip(),
            authors=p_in.authors.strip() if p_in.authors else None,
            presenter_name=p_in.presenter_name.strip() if p_in.presenter_name else None
        )
        db.add(paper)
        created_papers.append(paper)

    db.commit()
    for p in created_papers:
        db.refresh(p)
    return created_papers


@router.post("/events/{event_id}/papers/upload-excel", response_model=List[PaperResponse], status_code=status.HTTP_201_CREATED)
async def upload_papers_excel(
    event_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Bulk imports papers from spreadsheet (.xlsx, .xls, .csv).
    Automatically maps common column headers: title, paper_code, authors, presenter.
    """
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Acara tidak ditemukan.")

    contents = await file.read()
    filename = file.filename.lower() if file.filename else "file.xlsx"

    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal membaca file spreadsheet: {str(e)}")

    if df.empty:
        raise HTTPException(status_code=400, detail="File spreadsheet kosong.")

    # Normalize column names for flexible matching
    col_map = {}
    for col in df.columns:
        c_clean = str(col).strip().lower().replace(" ", "_").replace("-", "_")
        if c_clean in ["title", "judul", "judul_paper", "paper_title", "article"]:
            col_map["title"] = col
        elif c_clean in ["code", "kode", "paper_code", "kode_paper", "id", "paper_id"]:
            col_map["paper_code"] = col
        elif c_clean in ["authors", "author", "penulis", "nama_penulis"]:
            col_map["authors"] = col
        elif c_clean in ["presenter", "presenter_name", "nama_presenter", "pembicara"]:
            col_map["presenter_name"] = col

    if "title" not in col_map:
        raise HTTPException(
            status_code=400,
            detail="Kolom judul paper tidak ditemukan. Pastikan ada kolom bernama 'Judul Paper' atau 'Title'."
        )

    created_papers = []
    for _, row in df.iterrows():
        title_val = str(row[col_map["title"]]).strip() if pd.notna(row[col_map["title"]]) else ""
        if not title_val or title_val.lower() == "nan":
            continue

        code_val = str(row[col_map["paper_code"]]).strip() if "paper_code" in col_map and pd.notna(row[col_map["paper_code"]]) else None
        authors_val = str(row[col_map["authors"]]).strip() if "authors" in col_map and pd.notna(row[col_map["authors"]]) else None
        presenter_val = str(row[col_map["presenter_name"]]).strip() if "presenter_name" in col_map and pd.notna(row[col_map["presenter_name"]]) else None

        paper = Paper(
            event_id=event_id,
            paper_code=code_val,
            title=title_val,
            authors=authors_val,
            presenter_name=presenter_val
        )
        db.add(paper)
        created_papers.append(paper)

    db.commit()
    for p in created_papers:
        db.refresh(p)

    return created_papers


@router.delete("/events/{event_id}/papers/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_paper(
    event_id: uuid.UUID,
    paper_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Deletes a paper entry (Organizer only)"""
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Acara tidak ditemukan.")

    paper = db.query(Paper).filter(Paper.id == paper_id, Paper.event_id == event_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper tidak ditemukan.")

    db.delete(paper)
    db.commit()
    return None
