"""Job management routes"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.database import get_db
from app.decision.schemas import StateTransitionRequest, StateTransitionResponse
from app.decision.state_machine import StateMachineManager, JobState
from app.decision.event_logger import EventLogger
from app.queues.queue_manager import queue_manager

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/{job_id}/transition", response_model=StateTransitionResponse)
async def transition_job_state(
    job_id: UUID,
    request: StateTransitionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Transition job to a new state.
    
    This endpoint enforces state machine rules and prevents invalid transitions.
    
    Args:
        job_id: Job UUID
        request: State transition request
        db: Database session
        
    Returns:
        State transition response with current state and allowed transitions
        
    Raises:
        HTTPException: 404 if job not found, 400 if invalid state
    """
    # Get current state machine
    state_machine = await StateMachineManager.get_state_machine(db, job_id)
    if not state_machine:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Parse target state
    try:
        target_state = JobState(request.target_state.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state: {request.target_state}",
        )
    
    # Attempt transition
    success, error, updated_state_machine = await StateMachineManager.transition_job_state(
        db,
        job_id,
        target_state,
        reason=request.reason,
        error_code=request.error_code,
    )
    
    if not success:
        error_dict = {
            "code": error.code,
            "message": error.message,
            "doctrine_reference": error.doctrine_reference,
            "remediation_steps": error.remediation_steps,
        }
        return StateTransitionResponse(
            success=False,
            current_state=state_machine.current_state.value,
            error=error_dict,
            allowed_transitions=[
                state.value for state in state_machine.get_allowed_transitions()
            ],
        )
    
    # Log state transition
    if updated_state_machine and updated_state_machine.transition_history:
        await EventLogger.log_state_transition(
            db, job_id, updated_state_machine.transition_history[-1]
        )
    
    return StateTransitionResponse(
        success=True,
        current_state=updated_state_machine.current_state.value,
        previous_state=state_machine.current_state.value,
        allowed_transitions=[
            state.value
            for state in updated_state_machine.get_allowed_transitions()
        ],
    )


@router.get("/{job_id}/state-history")
async def get_state_history(
    job_id: UUID,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """
    Get state transition history for a job.
    
    Args:
        job_id: Job UUID
        limit: Maximum number of history entries to return
        db: Database session
        
    Returns:
        State transition history
        
    Raises:
        HTTPException: 404 if job not found
    """
    history = await EventLogger.get_state_transition_history(db, job_id, limit)
    return {"job_id": str(job_id), "history": history}


@router.get("/{job_id}")
async def get_job_status(job_id: str):
    """
    Get job status from queue manager.
    
    Args:
        job_id: Job ID string
        
    Returns:
        Job status information
    """
    status = await queue_manager.get_job_status(job_id)
    return status

