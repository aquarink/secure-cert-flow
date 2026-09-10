"""
Event Analytics and Metrics Endpoints
Provides high-level event statistics, role breakdowns, attendance analytics,
claim rate tracking, institution insights, and exportable reports.
"""

import io
import csv
import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, case, desc

from app.database import get_db
from app.models import Event, Participant, Certificate, Attendance, Paper, Template, User
from app.schemas.analytics import (
    EventAnalyticsResponse,
    EventAnalyticsSummary,
    RoleMetric,
    InstitutionMetric,
    HourlyMetric,
    TemplateUsageMetric,
)
from app.api.deps import get_current_user

router = APIRouter(prefix="/events", tags=["Analytics"])


@router.get("/{event_id}/analytics", response_model=EventAnalyticsResponse)
def get_event_analytics(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns comprehensive analytics, KPIs, role breakdown, and attendance metrics for an event.
    """
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Acara tidak ditemukan.")

    # 1. Summary Counts
    total_participants = db.query(Participant).filter(Participant.event_id == event_id).count()
    total_attendances = db.query(Attendance).filter(Attendance.event_id == event_id).count()
    total_certificates = db.query(Certificate).filter(Certificate.event_id == event_id).count()

    total_claimed = db.query(Certificate).filter(
        Certificate.event_id == event_id,
        (Certificate.claimed_at.isnot(None)) | (Certificate.status == "CLAIMED")
    ).count()
    total_unclaimed = max(0, total_certificates - total_claimed)
    claim_rate = round((total_claimed / total_certificates * 100), 1) if total_certificates > 0 else 0.0

    total_downloads = db.query(func.coalesce(func.sum(Certificate.download_count), 0)).filter(
        Certificate.event_id == event_id
    ).scalar() or 0

    total_papers = db.query(Paper).filter(Paper.event_id == event_id).count()
    papers_with_presenter = db.query(Paper).filter(
        Paper.event_id == event_id,
        Paper.presenter_name.isnot(None),
        Paper.presenter_name != ""
    ).count()
    papers_without_presenter = max(0, total_papers - papers_with_presenter)

    geotag_verified = db.query(Attendance).filter(
        Attendance.event_id == event_id,
        Attendance.latitude.isnot(None),
        Attendance.longitude.isnot(None)
    ).count()
    geotag_percentage = round((geotag_verified / total_attendances * 100), 1) if total_attendances > 0 else 0.0

    summary = EventAnalyticsSummary(
        total_participants=total_participants,
        total_attendances=total_attendances,
        total_certificates=total_certificates,
        total_claimed=total_claimed,
        total_unclaimed=total_unclaimed,
        claim_rate_percentage=claim_rate,
        total_downloads=int(total_downloads),
        total_papers=total_papers,
        papers_with_presenter=papers_with_presenter,
        papers_without_presenter=papers_without_presenter,
        geotag_verified_count=geotag_verified,
        geotag_percentage=geotag_percentage
    )

    # 2. Role Breakdown Metrics
    p_roles = db.query(
        Participant.role,
        func.count(Participant.id)
    ).filter(Participant.event_id == event_id).group_by(Participant.role).all()

    a_roles = db.query(
        Attendance.role,
        func.count(Attendance.id)
    ).filter(Attendance.event_id == event_id).group_by(Attendance.role).all()

    c_roles = db.query(
        Participant.role,
        func.count(Certificate.id),
        func.count(case(((Certificate.claimed_at.isnot(None)) | (Certificate.status == "CLAIMED"), 1)))
    ).join(Certificate, Certificate.participant_id == Participant.id)\
     .filter(Participant.event_id == event_id)\
     .group_by(Participant.role).all()

    p_map = {r: cnt for r, cnt in p_roles if r}
    a_map = {r: cnt for r, cnt in a_roles if r}
    c_map = {r: (tot, clm) for r, tot, clm in c_roles if r}

    all_roles = sorted(list(set(list(p_map.keys()) + list(a_map.keys()) + list(c_map.keys()))))
    role_metrics: List[RoleMetric] = []
    for role in all_roles:
        reg = p_map.get(role, 0)
        att = a_map.get(role, 0)
        cert_tot, cert_clm = c_map.get(role, (0, 0))
        unclm = max(0, cert_tot - cert_clm)
        crate = round((cert_clm / cert_tot * 100), 1) if cert_tot > 0 else 0.0

        role_metrics.append(RoleMetric(
            role=role,
            registered_count=reg,
            attendance_count=att,
            certificate_count=cert_tot,
            claimed_count=cert_clm,
            unclaimed_count=unclm,
            claim_rate_percentage=crate
        ))

    # 3. Top Institutions
    top_inst_rows = db.query(
        Attendance.institution,
        func.count(Attendance.id).label("cnt")
    ).filter(
        Attendance.event_id == event_id,
        Attendance.institution.isnot(None),
        Attendance.institution != ""
    ).group_by(Attendance.institution)\
     .order_by(desc("cnt"))\
     .limit(10).all()

    top_institutions: List[InstitutionMetric] = []
    for inst, count in top_inst_rows:
        pct = round((count / total_attendances * 100), 1) if total_attendances > 0 else 0.0
        top_institutions.append(InstitutionMetric(
            institution=inst,
            count=count,
            percentage=pct
        ))

    # 4. Hourly Distribution (WIB / Asia/Jakarta)
    hourly_rows = db.query(
        func.to_char(func.timezone("Asia/Jakarta", Attendance.created_at), "YYYY-MM-DD HH24:00").label("time_bucket"),
        func.count(Attendance.id).label("cnt")
    ).filter(Attendance.event_id == event_id)\
     .group_by("time_bucket")\
     .order_by("time_bucket")\
     .limit(24).all()

    hourly_attendances: List[HourlyMetric] = [
        HourlyMetric(time_bucket=bucket, count=cnt)
        for bucket, cnt in hourly_rows if bucket
    ]

    # 5. Template Usage
    template_rows = db.query(
        Template.id,
        Template.name,
        func.count(Certificate.id).label("cert_count"),
        func.count(case(((Certificate.claimed_at.isnot(None)) | (Certificate.status == "CLAIMED"), 1))).label("claimed_count")
    ).outerjoin(Certificate, Certificate.template_id == Template.id)\
     .filter(Template.event_id == event_id)\
     .group_by(Template.id, Template.name).all()

    template_usage: List[TemplateUsageMetric] = [
        TemplateUsageMetric(
            template_id=str(t_id) if t_id else None,
            template_name=t_name,
            certificate_count=cert_cnt,
            claimed_count=clm_cnt
        )
        for t_id, t_name, cert_cnt, clm_cnt in template_rows
    ]

    return EventAnalyticsResponse(
        event_id=str(event.id),
        event_name=event.name,
        is_cert_open=bool(event.is_cert_open),
        summary=summary,
        role_metrics=role_metrics,
        top_institutions=top_institutions,
        hourly_attendances=hourly_attendances,
        template_usage=template_usage,
        generated_at=datetime.now(timezone.utc)
    )


@router.get("/{event_id}/analytics/export-csv")
def export_event_analytics_csv(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Exports full event analytics report to CSV format.
    """
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Acara tidak ditemukan.")

    analytics = get_event_analytics(event_id=event_id, db=db, current_user=current_user)

    output = io.StringIO()
    output.write('\ufeff')  # UTF-8 BOM for Microsoft Excel
    writer = csv.writer(output)

    # 1. Header Information
    writer.writerow(["LAPORAN ANALISIS & STATISTIK ACARA"])
    writer.writerow(["Nama Acara", event.name])
    writer.writerow(["ID Acara", str(event.id)])
    writer.writerow(["Tanggal Ekspor", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    writer.writerow(["Status Klaim Terbuka", "Ya (Terbuka)" if event.is_cert_open else "Tidak (Terkunci)"])
    writer.writerow([])

    # 2. Ringkasan Eksekutif (KPIs)
    writer.writerow(["--- RINGKASAN EKSEKUTIF (KEY PERFORMANCE INDICATORS) ---"])
    writer.writerow(["Metrik", "Nilai", "Keterangan"])
    writer.writerow(["Total Peserta & Panitia Terdaftar", analytics.summary.total_participants, "Seluruh entitas terdaftar dalam sistem"])
    writer.writerow(["Total Presensi Kehadiran Terverifikasi", analytics.summary.total_attendances, f"{analytics.summary.geotag_percentage}% terverifikasi GPS"])
    writer.writerow(["Total Sertifikat Diterbitkan", analytics.summary.total_certificates, ""])
    writer.writerow(["Sertifikat Sudah Diklaim", analytics.summary.total_claimed, f"Rasio Klaim: {analytics.summary.claim_rate_percentage}%"])
    writer.writerow(["Sertifikat Belum Diklaim", analytics.summary.total_unclaimed, ""])
    writer.writerow(["Total Unduhan Sertifikat", analytics.summary.total_downloads, "Total frekuensi download file PDF/Gambar"])
    writer.writerow(["Total Judul Paper Terdaftar", analytics.summary.total_papers, f"{analytics.summary.papers_with_presenter} paper memiliki presenter"])
    writer.writerow([])

    # 3. Matriks Komparasi Peran
    writer.writerow(["--- MATRIKS ANALISIS PER PERAN (ROLES BREAKDOWN) ---"])
    writer.writerow(["Peran (Role)", "Terdaftar", "Hadir Presensi", "Sertifikat Terbit", "Sertifikat Diklaim", "Belum Diklaim", "Rasio Klaim (%)"])
    for r in analytics.role_metrics:
        writer.writerow([
            r.role,
            r.registered_count,
            r.attendance_count,
            r.certificate_count,
            r.claimed_count,
            r.unclaimed_count,
            f"{r.claim_rate_percentage}%"
        ])
    writer.writerow([])

    # 4. Top 10 Institusi
    writer.writerow(["--- TOP 10 INSTITUSI / KAMPUS DENGAN KEHADIRAN TERBANYAK ---"])
    writer.writerow(["Peringkat", "Nama Institusi / Lembaga", "Jumlah Hadir", "Persentase (%)"])
    for idx, inst in enumerate(analytics.top_institutions, 1):
        writer.writerow([idx, inst.institution, inst.count, f"{inst.percentage}%"])
    writer.writerow([])

    # 5. Distribusi Waktu Presensi
    writer.writerow(["--- DISTRIBUSI WAKTU PRESENSI (WIB) ---"])
    writer.writerow(["Jam / Waktu", "Jumlah Presensi"])
    for h in analytics.hourly_attendances:
        writer.writerow([h.time_bucket, h.count])
    writer.writerow([])

    # 6. Penggunaan Template Sertifikat
    writer.writerow(["--- PENGGUNAAN DESAIN TEMPLATE SERTIFIKAT ---"])
    writer.writerow(["Nama Desain Template", "Jumlah Sertifikat Terbit", "Jumlah Diklaim"])
    for t in analytics.template_usage:
        writer.writerow([t.template_name, t.certificate_count, t.claimed_count])

    csv_data = output.getvalue()
    clean_event_name = re.sub(r'[^a-zA-Z0-9]', '_', event.name)
    filename = f"Analisis_Statistik_{clean_event_name}.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )
