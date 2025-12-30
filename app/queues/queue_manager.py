"""Redis-based queue manager for job scheduling (BullMQ-compatible pattern)"""
import json
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
import asyncio

from app.core.redis import redis_client
from app.queues.job_processor import process_job


class QueueManager:
    """Manages Redis-based queues for content generation (BullMQ-compatible)"""

    def __init__(self):
        self.queue_name = "content-generation"
        self.redis_client = None
        self.worker_task = None
        self.running = False

    async def initialize(self):
        """Initialize queue and start worker"""
        self.redis_client = await redis_client.get_client()
        self.running = True
        
        # Start background worker
        self.worker_task = asyncio.create_task(self._worker_loop())

    async def _worker_loop(self):
        """Background worker loop to process jobs"""
        while self.running:
            try:
                # Use Redis BLPOP to get jobs (blocking pop)
                result = await self.redis_client.blpop(
                    f"{self.queue_name}:pending",
                    timeout=1
                )
                
                if result:
                    _, job_data_str = result
                    job_data = json.loads(job_data_str)
                    
                    # Process job
                    try:
                        result = await process_job(job_data)
                        
                        # Store result
                        job_id = job_data.get("job_id")
                        if job_id:
                            await self.redis_client.hset(
                                f"{self.queue_name}:jobs:{job_id}",
                                mapping={
                                    "status": "completed",
                                    "result": json.dumps(result),
                                    "completed_at": datetime.utcnow().isoformat(),
                                }
                            )
                    except Exception as e:
                        # Store error
                        job_id = job_data.get("job_id")
                        if job_id:
                            await self.redis_client.hset(
                                f"{self.queue_name}:jobs:{job_id}",
                                mapping={
                                    "status": "failed",
                                    "error": str(e),
                                    "failed_at": datetime.utcnow().isoformat(),
                                }
                            )
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Worker error: {e}")
                await asyncio.sleep(1)

    async def add_generation_job(
        self,
        page_id: str,
        title: str,
        path: str,
        site_id: str,
        prompt: str,
        silo_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Week 5: Add a content generation job to the queue
        
        Args:
            page_id: Page ID (changed from content_id)
            title: Page title
            path: Page path (changed from slug)
            site_id: Site ID
            prompt: Generation prompt
            silo_id: Optional silo ID
            metadata: Optional metadata
            
        Returns:
            job_id: The job ID
        """
        if not self.redis_client:
            await self.initialize()

        job_id = str(uuid.uuid4())
        job_data = {
            "job_id": job_id,
            "page_id": page_id,
            "title": title,
            "path": path,
            "site_id": site_id,
            "silo_id": silo_id,
            "prompt": prompt,
            "metadata": metadata or {},
            "created_at": datetime.utcnow().isoformat(),
        }

        # Add to pending queue
        await self.redis_client.rpush(
            f"{self.queue_name}:pending",
            json.dumps(job_data)
        )

        # Store job metadata
        await self.redis_client.hset(
            f"{self.queue_name}:jobs:{job_id}",
            mapping={
                "status": "pending",
                "data": json.dumps(job_data),
                "created_at": datetime.utcnow().isoformat(),
            }
        )

        return job_id
    
    async def add_bulk_generation_jobs(
        self,
        jobs: list[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Week 5: Add multiple generation jobs to the queue (bulk processing).
        
        Args:
            jobs: List of job dictionaries, each with:
                - page_id: str
                - title: str
                - path: str
                - site_id: str
                - prompt: str
                - silo_id: Optional[str]
                - metadata: Optional[Dict]
        
        Returns:
            Dictionary with:
                - total: Total jobs added
                - job_ids: List of job IDs
                - errors: List of errors (if any)
        """
        if not self.redis_client:
            await self.initialize()
        
        job_ids = []
        errors = []
        
        for job_data in jobs:
            try:
                job_id = await self.add_generation_job(
                    page_id=job_data["page_id"],
                    title=job_data["title"],
                    path=job_data["path"],
                    site_id=job_data["site_id"],
                    prompt=job_data["prompt"],
                    silo_id=job_data.get("silo_id"),
                    metadata=job_data.get("metadata"),
                )
                job_ids.append(job_id)
            except Exception as e:
                errors.append({
                    "job": job_data,
                    "error": str(e),
                })
        
        return {
            "total": len(jobs),
            "added": len(job_ids),
            "failed": len(errors),
            "job_ids": job_ids,
            "errors": errors,
        }

    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get status of a job"""
        if not self.redis_client:
            await self.initialize()

        job_data = await self.redis_client.hgetall(f"{self.queue_name}:jobs:{job_id}")
        
        if not job_data:
            return {"status": "not_found"}

        result = {
            "id": job_id,
            "status": job_data.get("status", "unknown"),
        }

        if "data" in job_data:
            result["data"] = json.loads(job_data["data"])
        if "result" in job_data:
            result["returnvalue"] = json.loads(job_data["result"])
        if "error" in job_data:
            result["failedReason"] = job_data["error"]

        return result

    async def close(self):
        """Close queue and worker"""
        self.running = False
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass


# Global queue manager instance
queue_manager = QueueManager()

