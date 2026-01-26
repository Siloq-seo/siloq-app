"""Week 5: AI Draft Engine - Job processor with structured outputs, retry logic, and cost tracking."""
import json
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from openai import AsyncOpenAI

from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.db.models import Page, GenerationJob, ContentStatus
from app.governance.ai.ai_output import AIOutputGovernor
from app.governance.content.publishing import PublishingSafety
from app.governance.ai.structured_output import StructuredOutputGenerator, StructuredContent
from app.governance.ai.cost_calculator import CostCalculator
from app.schemas.jsonld import JSONLDGenerator
from app.decision.postcheck_validator import PostcheckValidator
from app.decision.error_codes import ErrorCodeDictionary


class ContentGenerationProcessor:
    """
    Week 5: Processes AI content generation jobs with:
    - Structured output generation
    - Retry-cost safety
    - Enhanced postcheck (entity coverage, FAQ minimum, link validation)
    """

    def __init__(self):
        self.governor = AIOutputGovernor()
        self.publishing_safety = PublishingSafety()
        self.jsonld_generator = JSONLDGenerator()
        self.postcheck_validator = PostcheckValidator()
        self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.structured_generator = StructuredOutputGenerator(self.openai_client)
        self.cost_calculator = CostCalculator()

    async def process_generation_job(
        self, 
        job_data: Dict[str, Any],
        retry: bool = False
    ) -> Dict[str, Any]:
        """
        Process a content generation job through all governance stages.
        
        Week 5: Enhanced with structured outputs, retry logic, and cost tracking.
        
        Job data structure:
        {
            "page_id": str,
            "title": str,
            "path": str,
            "silo_id": str (optional),
            "site_id": str,
            "prompt": str,
            "metadata": dict (optional)
        }
        """
        page_id = job_data.get("page_id")
        if not page_id:
            raise ValueError("page_id is required")

        async with AsyncSessionLocal() as db:
            # Get page
            page = await db.get(Page, uuid.UUID(page_id))
            if not page:
                raise ValueError(f"Page {page_id} not found")

            # Get generation job
            job_query = select(GenerationJob).where(
                GenerationJob.page_id == page.id
            ).order_by(GenerationJob.created_at.desc())
            job_result = await db.execute(job_query)
            job = job_result.scalar_one_or_none()

            if not job:
                raise ValueError(f"Generation job not found for page {page_id}")

            # Week 5: Check retry limit
            if job.retry_count >= job.max_retries:
                job.status = "ai_max_retry_exceeded"
                job.error_code = "AI_MAX_RETRY_EXCEEDED"
                job.error_message = f"Maximum retries ({job.max_retries}) exceeded"
                await db.commit()
                return {
                    "success": False,
                    "error_code": "AI_MAX_RETRY_EXCEEDED",
                    "error": job.error_message,
                    "retry_count": job.retry_count,
                }

            # Week 5: Check cost limit
            if job.total_cost_usd >= settings.ai_max_cost_per_job_usd:
                job.status = "failed"
                job.error_code = "AI_COST_LIMIT_EXCEEDED"
                job.error_message = f"Cost limit ({settings.ai_max_cost_per_job_usd} USD) exceeded"
                await db.commit()
                return {
                    "success": False,
                    "error_code": "AI_COST_LIMIT_EXCEEDED",
                    "error": job.error_message,
                    "total_cost_usd": job.total_cost_usd,
                }

            try:
                # PRE-GENERATION GOVERNANCE
                pre_check = await self.governor.pre_generation_checks(db, page)
                job.pre_generation_passed = pre_check["passed"]
                page.governance_checks = page.governance_checks or {}
                page.governance_checks["pre_generation"] = pre_check

                if not pre_check["passed"]:
                    job.status = "failed"
                    job.error_message = f"Pre-generation check failed: {pre_check.get('reason', 'Unknown')}"
                    await db.commit()
                    return {
                        "success": False,
                        "stage": "pre_generation",
                        "error": job.error_message,
                    }

                # DURING GENERATION
                job.status = "processing"
                job.started_at = datetime.utcnow()
                if retry:
                    job.retry_count += 1
                    job.last_retry_at = datetime.utcnow()
                await db.commit()

                # Week 5: Generate structured content using structured outputs
                prompt = job_data.get("prompt", f"Write comprehensive content about: {page.title}")
                
                try:
                    # Extract metadata for entity injection and voice governance
                    metadata = job_data.get("metadata", {})
                    
                    # Get onboarding data from system_events if available
                    # This would be stored when onboarding questionnaire is submitted
                    # For now, metadata should contain scope and brand_voice if available
                    
                    structured_content = await self.structured_generator.generate_structured_content(
                        prompt=prompt,
                        title=page.title,
                        model="gpt-4-turbo-preview",
                        temperature=0.7,
                        max_tokens=4000,
                        metadata=metadata,
                    )
                    
                    # Store page_type in governance_checks for decay logic
                    # Determine page_type from metadata or infer from content
                    page_type = metadata.get("page_type") or metadata.get("pageType")
                    if page_type:
                        if not page.governance_checks:
                            page.governance_checks = {}
                        page.governance_checks["page_type"] = page_type
                    
                    # Calculate cost for structured generation
                    # Note: We need to track this from the actual API response
                    # For now, we'll estimate or track separately
                    generation_cost = 0.05  # Estimated cost per generation
                    job.total_cost_usd += generation_cost
                    
                    # Store structured output metadata
                    job.structured_output_metadata = {
                        "entities": structured_content.entities,
                        "faqs": structured_content.faqs,
                        "links": structured_content.links,
                        "metadata": structured_content.metadata,
                    }
                    
                    generated_content = structured_content.body
                    
                except Exception as e:
                    # Fallback to regular generation if structured outputs fail
                    response = await self.openai_client.chat.completions.create(
                        model="gpt-4-turbo-preview",
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a professional SEO content writer. Write comprehensive, well-structured content that preserves intent and authority.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.7,
                        max_tokens=2000,
                    )
                    
                    generated_content = response.choices[0].message.content
                    
                    # Calculate actual cost
                    generation_cost = self.cost_calculator.calculate_chat_completion_cost(
                        response, "gpt-4-turbo-preview"
                    )
                    job.total_cost_usd += generation_cost
                    
                    # Set empty structured metadata for fallback
                    job.structured_output_metadata = {
                        "entities": [],
                        "faqs": [],
                        "links": [],
                        "metadata": {},
                    }

                # DURING-GENERATION GOVERNANCE
                during_check = await self.governor.during_generation_checks(
                    db, page, generated_content
                )
                job.during_generation_passed = during_check["passed"]
                page.governance_checks["during_generation"] = during_check

                if not during_check["passed"]:
                    # Week 5: Retry if under limit
                    if job.retry_count < job.max_retries:
                        await db.commit()
                        return await self.process_generation_job(job_data, retry=True)
                    
                    job.status = "failed"
                    job.error_message = f"During-generation check failed: {during_check.get('reason', 'Unknown')}"
                    await db.commit()
                    return {
                        "success": False,
                        "stage": "during_generation",
                        "error": job.error_message,
                    }

                # Update page body
                page.body = generated_content

                # Generate embedding for cannibalization detection
                embedding_response = await self.openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=f"{page.title}\n{generated_content}",
                )
                embedding = embedding_response.data[0].embedding
                page.embedding = embedding
                
                # Calculate embedding cost
                usage = embedding_response.usage
                if usage:
                    embedding_tokens = usage.total_tokens or 0
                    embedding_cost = self.cost_calculator.calculate_embedding_cost(
                        embedding_tokens, "text-embedding-3-small"
                    )
                    job.total_cost_usd += embedding_cost

                # Week 5: Enhanced POST-GENERATION GOVERNANCE with structured output checks
                post_check = await self.postcheck_validator.validate(
                    db,
                    page.id,
                    embedding,
                    structured_output_metadata=job.structured_output_metadata,
                )
                job.post_generation_passed = post_check["passed"]
                page.governance_checks["post_generation"] = {
                    "passed": post_check.passed,
                    "errors": post_check.errors,
                    "warnings": post_check.warnings,
                }

                if not post_check["passed"]:
                    # Week 5: Retry if under limit
                    if job.retry_count < job.max_retries:
                        await db.commit()
                        return await self.process_generation_job(job_data, retry=True)
                    
                    job.status = "postcheck_failed"
                    job.error_message = f"Post-generation check failed: {post_check.errors}"
                    job.error_code = post_check.errors[0].get("code") if post_check.errors else None
                    await db.commit()
                    return {
                        "success": False,
                        "stage": "post_generation",
                        "error": job.error_message,
                        "errors": post_check.errors,
                    }

                # Generate JSON-LD schema (backend-driven, not AI)
                jsonld_schema = await self.jsonld_generator.generate_schema(db, page)
                page.governance_checks["jsonld_schema"] = jsonld_schema

                # Publishing safety check
                safety_check = await self.publishing_safety.check_publishing_safety(
                    db, page
                )

                if safety_check["is_safe"]:
                    page.status = ContentStatus.APPROVED
                else:
                    page.status = ContentStatus.BLOCKED
                    await self.publishing_safety.block_unsafe_content(
                        db, page, safety_check.get("reason", "Safety check failed")
                    )

                # Complete job
                job.status = "completed"
                job.completed_at = datetime.utcnow()
                await db.commit()

                return {
                    "success": True,
                    "page_id": str(page.id),
                    "status": page.status.value,
                    "total_cost_usd": job.total_cost_usd,
                    "retry_count": job.retry_count,
                    "structured_output": {
                        "entities": job.structured_output_metadata.get("entities", []),
                        "faqs": job.structured_output_metadata.get("faqs", []),
                        "links": job.structured_output_metadata.get("links", []),
                    },
                }

            except Exception as e:
                # Week 5: Retry on exception if under limit
                if job.retry_count < job.max_retries:
                    await db.commit()
                    return await self.process_generation_job(job_data, retry=True)
                
                job.status = "failed"
                job.error_message = str(e)
                await db.commit()
                return {
                    "success": False,
                    "error": str(e),
                    "retry_count": job.retry_count,
                }


async def process_job(job_data: Dict[str, Any]) -> Dict[str, Any]:
    """Entry point for job processing"""
    processor = ContentGenerationProcessor()
    return await processor.process_generation_job(job_data)
