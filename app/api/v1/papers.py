"""
Papers and Submissions API Router
Handles conference paper catalog, search autocomplete, bulk Excel import, and Authorship Certificate generation.
"""

import io
import uuid
import re
from datetime import datetime
import pandas as pd
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models import Event, Paper, User, Participant, Certificate
from app.schemas.paper import PaperCreate, PaperUpdate, PaperResponse, PaperBulkCreate
from app.api.deps import get_current_user
from app.services import generate_claim_code

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


@router.post("/events/{event_id}/papers/generate-author-certificates")
def generate_author_certificates(
    event_id: uuid.UUID,
    paper_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generates 1 Authorship Certificate per paper in the catalog.
    Replaces namaLengkap with all author names joined by ' - ' (e.g. Juri - Dery - Dewi).
    """
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Acara tidak ditemukan.")

    query = db.query(Paper).filter(Paper.event_id == event_id)
    if paper_id:
        query = query.filter(Paper.id == paper_id)

    papers = query.all()
    results = []

    for paper in papers:
        if not paper.authors:
            continue

        # Split authors by comma, semicolon, or 'and' and clean whitespace
        raw_authors = re.split(r'[,;]|\band\b| - ', paper.authors)
        cleaned_authors = [a.strip() for a in raw_authors if a.strip() and len(a.strip()) >= 2]
        combined_authors_name = " - ".join(cleaned_authors) if cleaned_authors else paper.authors.strip()

        # Remove any legacy individual author participants for this paper
        db.query(Participant).filter(
            Participant.event_id == event_id,
            Participant.role == "Author",
            Participant.paper_title == paper.title,
            Participant.name != combined_authors_name
        ).delete(synchronize_session=False)

        # Check if combined participant already exists for this paper
        p = db.query(Participant).filter(
            Participant.event_id == event_id,
            Participant.role == "Author",
            Participant.paper_title == paper.title
        ).first()

        if not p:
            p = Participant(
                event_id=event_id,
                name=combined_authors_name,
                email=f"authors_{uuid.uuid4().hex[:6]}@uinjkt.ac.id",
                role="Author",
                paper_title=paper.title,
                custom_data={"paper_code": paper.paper_code}
            )
            db.add(p)
            db.flush()
        else:
            p.name = combined_authors_name
            db.flush()

        cert = db.query(Certificate).filter(Certificate.participant_id == p.id).first()
        if not cert:
            claim_code = generate_claim_code()
            while db.query(Certificate).filter(Certificate.claim_code == claim_code).first():
                claim_code = generate_claim_code()

            prefix = event.name[:4].upper().replace(" ", "C")
            cert_num = f"{prefix}-{datetime.now().year}-{claim_code}"
            cert = Certificate(
                event_id=event_id,
                participant_id=p.id,
                certificate_number=cert_num,
                claim_code=claim_code,
                status="GENERATED",
                download_count=0
            )
            db.add(cert)
            db.flush()
        else:
            # Invalidate image cache so it re-renders on trigger with the updated combined authors name
            cert.image_url = None
            cert.checksum_sha256 = None
            db.flush()

        results.append({
            "paper_code": paper.paper_code,
            "paper_title": paper.title,
            "author_name": combined_authors_name,
            "claim_code": cert.claim_code,
            "cert_url": f"/verify/{cert.claim_code}"
        })

    db.commit()
    return {
        "message": f"Berhasil menerbitkan {len(results)} sertifikat authorship ({len(results)} paper)!",
        "count": len(results),
        "authors": results
    }


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

@router.get("/events/{event_id}/authors-certificates")
def list_authors_certificates(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves all issued author certificates for an event.
    """
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Acara tidak ditemukan.")

    participants = db.query(Participant).filter(
        Participant.event_id == event_id,
        Participant.role == "Author"
    ).all()

    results = []
    for p in participants:
        if p.certificate:
            p_code = p.custom_data.get("paper_code", "") if (p.custom_data and isinstance(p.custom_data, dict)) else ""
            results.append({
                "participant_id": str(p.id),
                "author_name": p.name,
                "paper_title": p.paper_title,
                "paper_code": p_code,
                "claim_code": p.certificate.claim_code,
                "certificate_number": p.certificate.certificate_number,
                "cert_url": f"/verify/{p.certificate.claim_code}",
                "status": p.certificate.status,
                "created_at": p.certificate.created_at.strftime("%d %b %Y, %H:%M") if p.certificate.created_at else "-"
            })

    return results
