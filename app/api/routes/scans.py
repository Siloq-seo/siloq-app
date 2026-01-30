"""Website scanning API routes"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from uuid import UUID
from urllib.parse import urlparse
from datetime import datetime

from app.core.database import get_db
from app.db.models import Scan, Site
from app.schemas.scans import (
    ScanRequest,
    ScanResponse,
    ScanSummary,
    ScanReportResponse,
    ScanReportSummary,
    KeywordCannibalizationItem,
)
from app.services.scanning import WebsiteScanner


router = APIRouter(prefix="/scans", tags=["scans"])


async def _run_scan(scan_id: UUID, url: str, scan_type: str):
    """Background task to run the actual scan"""
    from app.core.database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as db:
        try:
            # Update scan status to processing
            scan = await db.get(Scan, scan_id)
            if not scan:
                return
            
            scan.status = 'processing'
            scan.started_at = datetime.now()
            await db.commit()
            
            # Run scanner
            async with WebsiteScanner() as scanner:
                results = await scanner.scan_website(str(url), scan_type)
            
            # Update scan with results
            scan = await db.get(Scan, scan_id)  # Refresh to avoid detached instance
            if not scan:
                return
                
            scan.status = results['status']
            scan.overall_score = results.get('overall_score')
            scan.grade = results.get('grade')
            scan.technical_score = results.get('technical_score')
            scan.content_score = results.get('content_score')
            scan.structure_score = results.get('structure_score')
            scan.performance_score = results.get('performance_score')
            scan.seo_score = results.get('seo_score')
            scan.technical_details = results.get('technical_details', {})
            scan.content_details = results.get('content_details', {})
            scan.structure_details = results.get('structure_details', {})
            scan.performance_details = results.get('performance_details', {})
            scan.seo_details = results.get('seo_details', {})
            scan.recommendations = results.get('recommendations', [])
            scan.pages_crawled = results.get('pages_crawled', 0)
            scan.scan_duration_seconds = results.get('scan_duration_seconds')
            scan.completed_at = datetime.now()
            
            if results.get('error_message'):
                scan.error_message = results['error_message']
            
            await db.commit()
            
        except Exception as e:
            # Update scan with error
            scan = await db.get(Scan, scan_id)
            if scan:
                scan.status = 'failed'
                scan.error_message = str(e)
                scan.completed_at = datetime.now()
                await db.commit()


@router.post("", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
async def create_scan(
    request: ScanRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new website scan.
    
    The scan will run in the background. Use GET /scans/{scan_id} to check status.
    """
    # Extract domain from URL
    parsed_url = urlparse(str(request.url))
    domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
    
    # Verify site_id if provided
    site = None
    if request.site_id:
        site = await db.get(Site, request.site_id)
        if not site:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Site not found"
            )
    
    # Create scan record
    scan = Scan(
        site_id=request.site_id,
        url=str(request.url),
        domain=domain,
        scan_type=request.scan_type,
        status='pending',
    )
    
    db.add(scan)
    await db.commit()
    await db.refresh(scan)
    
    # Start background scan
    background_tasks.add_task(_run_scan, scan.id, request.url, request.scan_type)
    
    return ScanResponse(
        id=scan.id,
        url=scan.url,
        domain=scan.domain,
        scan_type=scan.scan_type,
        status=scan.status,
        overall_score=scan.overall_score,
        grade=scan.grade,
        technical_score=scan.technical_score,
        content_score=scan.content_score,
        structure_score=scan.structure_score,
        performance_score=scan.performance_score,
        seo_score=scan.seo_score,
        technical_details=scan.technical_details or {},
        content_details=scan.content_details or {},
        structure_details=scan.structure_details or {},
        performance_details=scan.performance_details or {},
        seo_details=scan.seo_details or {},
        recommendations=scan.recommendations or [],
        pages_crawled=scan.pages_crawled,
        scan_duration_seconds=scan.scan_duration_seconds,
        error_message=scan.error_message,
        created_at=scan.created_at,
        completed_at=scan.completed_at,
    )


@router.get("/{scan_id}/report", response_model=ScanReportResponse)
async def get_scan_report(
    scan_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get full lead-gen report for a scan (Keyword Cannibalization Report).
    No authentication required. Used by WordPress plugin "Get Full Report" CTA.
    """
    scan = await db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found",
        )
    recommendations = scan.recommendations or []
    content_details = scan.content_details or {}
    structure_details = scan.structure_details or {}
    pages_crawled = scan.pages_crawled or 0
    url = scan.url or ""

    # Cannibalization-style conflicts derived from Content/Structure recommendations
    content_issues = content_details.get("issues", [])
    structure_issues = structure_details.get("issues", [])
    content_recs = [r for r in recommendations if (r.get("category") or "").lower() == "content"]
    structure_recs = [r for r in recommendations if (r.get("category") or "").lower() == "structure"]
    conflict_count = len(content_recs) + len(structure_recs)
    if conflict_count == 0:
        conflict_count = len(content_issues) + len(structure_issues)
    if conflict_count == 0 and recommendations:
        conflict_count = min(len(recommendations), 5)

    # Overall risk level from score and conflict count
    score = scan.overall_score or 0
    if conflict_count >= 5 or score < 50:
        risk_level = "High"
    elif conflict_count >= 2 or score < 70:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    # Build keyword cannibalization list from content/structure issues and recommendations
    keyword_details: List[dict] = []
    seen_keys: set = set()
    for rec in recommendations:
        cat = (rec.get("category") or "").lower()
        if cat not in ("content", "structure"):
            continue
        issue = (rec.get("issue") or "Keyword conflict").strip()
        if not issue or issue in seen_keys:
            continue
        seen_keys.add(issue)
        keyword_name = issue[:80] if len(issue) > 80 else issue
        severity = "High" if (rec.get("priority") or "").lower() == "high" else "Medium"
        keyword_details.append({
            "keyword": keyword_name,
            "conflicting_urls": [url] if url else [],
            "conflict_type": "same intent" if cat == "content" else "same keyword",
            "severity": severity,
        })
    for issue in (content_issues + structure_issues)[:5]:
        issue_str = (issue if isinstance(issue, str) else str(issue)).strip()[:80]
        if issue_str and issue_str not in seen_keys:
            seen_keys.add(issue_str)
            keyword_details.append({
                "keyword": issue_str,
                "conflicting_urls": [url] if url else [],
                "conflict_type": "same intent",
                "severity": "Medium",
            })

    if not keyword_details and conflict_count > 0:
        keyword_details = [{
            "keyword": "Multiple pages competing for similar topics",
            "conflicting_urls": [url] if url else [],
            "conflict_type": "same intent",
            "severity": "High" if risk_level == "High" else "Medium",
        }]

    summary = ScanReportSummary(
        website_url=url,
        total_pages_analyzed=pages_crawled,
        total_cannibalization_conflicts=conflict_count,
        overall_risk_level=risk_level,
    )
    educational = {
        "title": "What is keyword cannibalization?",
        "body": "Keyword cannibalization occurs when multiple pages on your site target the same or very similar keywords. Search engines may split rankings between these pages or pick the wrong one, which hurts your visibility and traffic. Consolidating or clearly differentiating content helps you rank better and gives users a clearer path.",
    }
    locked = [
        "Page consolidation",
        "Primary keyword assignment",
        "Content silo restructuring",
    ]
    upgrade_cta = {
        "label": "Unlock Full Report & Fix Issues",
        "scan_id_param": "scan_id",
    }

    return ScanReportResponse(
        scan_id=scan.id,
        scan_summary=summary,
        keyword_cannibalization_details=[KeywordCannibalizationItem(**k) for k in keyword_details],
        educational_explanation=educational,
        locked_recommendations=locked,
        upgrade_cta=upgrade_cta,
    )


@router.get("/{scan_id}", response_model=ScanResponse)
async def get_scan(
    scan_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get scan results by ID"""
    scan = await db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found"
        )
    
    return ScanResponse(
        id=scan.id,
        url=scan.url,
        domain=scan.domain,
        scan_type=scan.scan_type,
        status=scan.status,
        overall_score=scan.overall_score,
        grade=scan.grade,
        technical_score=scan.technical_score,
        content_score=scan.content_score,
        structure_score=scan.structure_score,
        performance_score=scan.performance_score,
        seo_score=scan.seo_score,
        technical_details=scan.technical_details or {},
        content_details=scan.content_details or {},
        structure_details=scan.structure_details or {},
        performance_details=scan.performance_details or {},
        seo_details=scan.seo_details or {},
        recommendations=scan.recommendations or [],
        pages_crawled=scan.pages_crawled,
        scan_duration_seconds=scan.scan_duration_seconds,
        error_message=scan.error_message,
        created_at=scan.created_at,
        completed_at=scan.completed_at,
    )


@router.get("", response_model=List[ScanSummary])
async def list_scans(
    domain: Optional[str] = None,
    site_id: Optional[UUID] = None,
    status_filter: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """
    List scans with optional filters.
    
    Query parameters:
    - domain: Filter by domain
    - site_id: Filter by site ID
    - status: Filter by status (pending, processing, completed, failed)
    - limit: Number of results (default: 20)
    - offset: Pagination offset (default: 0)
    """
    query = select(Scan)
    
    if domain:
        query = query.where(Scan.domain == domain)
    if site_id:
        query = query.where(Scan.site_id == site_id)
    if status_filter:
        query = query.where(Scan.status == status_filter)
    
    query = query.order_by(desc(Scan.created_at)).limit(limit).offset(offset)
    
    result = await db.execute(query)
    scans = result.scalars().all()
    
    return [
        ScanSummary(
            id=scan.id,
            url=scan.url,
            domain=scan.domain,
            status=scan.status,
            overall_score=scan.overall_score,
            grade=scan.grade,
            created_at=scan.created_at,
            completed_at=scan.completed_at,
        )
        for scan in scans
    ]


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scan(
    scan_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a scan"""
    scan = await db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found"
        )
    
    await db.delete(scan)
    await db.commit()
    
    return None
