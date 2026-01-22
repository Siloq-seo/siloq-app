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
from app.schemas.scans import ScanRequest, ScanResponse, ScanSummary
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
