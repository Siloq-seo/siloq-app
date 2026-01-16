"""State Machine for content generation jobs with transition guards."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import ClassVar, Dict, List, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.decision.error_codes import ErrorCode, ErrorCodeDictionary
from app.db.models import GenerationJob


class JobState(str, Enum):
    """Valid states for content generation jobs."""
    
    DRAFT = "draft"
    PREFLIGHT_APPROVED = "preflight_approved"
    PROMPT_LOCKED = "prompt_locked"
    POSTCHECK_PASSED = "postcheck_passed"
    POSTCHECK_FAILED = "postcheck_failed"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    
    @classmethod
    def from_string(cls, value: str) -> "JobState":
        """
        Parse state from string with fallback to DRAFT.
        
        Args:
            value: State string value
            
        Returns:
            JobState enum value, defaults to DRAFT if invalid
        """
        try:
            return cls(value.lower())
        except ValueError:
            return cls.DRAFT


@dataclass
class StateTransition:
    """
    Represents a state transition with metadata.
    
    Attributes:
        from_state: Source state
        to_state: Target state
        timestamp: When the transition occurred
        reason: Optional reason for transition
        error_code: Optional error code if transition failed
    """
    
    from_state: JobState
    to_state: JobState
    timestamp: datetime
    reason: Optional[str] = None
    error_code: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert transition to dictionary for serialization."""
        return {
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason,
            "error_code": self.error_code,
        }


class StateMachine:
    """
    Type-safe state machine with transition guards.
    
    Enforces valid state transitions and prevents skipping states.
    Maintains transition history for audit trail.
    """
    
    # Define valid state transitions
    VALID_TRANSITIONS: ClassVar[Dict[JobState, Set[JobState]]] = {
        JobState.DRAFT: {
            JobState.PREFLIGHT_APPROVED,
            JobState.FAILED,
        },
        JobState.PREFLIGHT_APPROVED: {
            JobState.PROMPT_LOCKED,
            JobState.FAILED,
        },
        JobState.PROMPT_LOCKED: {
            JobState.PROCESSING,
            JobState.FAILED,
        },
        JobState.PROCESSING: {
            JobState.POSTCHECK_PASSED,
            JobState.POSTCHECK_FAILED,
            JobState.FAILED,
        },
        JobState.POSTCHECK_PASSED: {
            JobState.COMPLETED,
            JobState.FAILED,
        },
        JobState.POSTCHECK_FAILED: {
            JobState.DRAFT,  # Can retry from draft
            JobState.FAILED,
        },
        JobState.COMPLETED: set(),  # Terminal state
        JobState.FAILED: {
            JobState.DRAFT,  # Can retry from draft
        },
    }
    
    # States that lock the job (cannot be modified)
    LOCKED_STATES: ClassVar[Set[JobState]] = {
        JobState.PROMPT_LOCKED,
        JobState.PROCESSING,
    }
    
    # Terminal states (cannot transition from)
    TERMINAL_STATES: ClassVar[Set[JobState]] = {
        JobState.COMPLETED,
    }
    
    def __init__(self, job: GenerationJob):
        """
        Initialize state machine with a job.
        
        Args:
            job: GenerationJob instance to manage state for
        """
        self.job = job
        self.current_state = JobState.from_string(job.status)
        self.transition_history: List[StateTransition] = []
    
    def can_transition_to(
        self, target_state: JobState
    ) -> Tuple[bool, Optional[ErrorCode]]:
        """
        Check if transition to target state is allowed.
        
        Args:
            target_state: Target state to transition to
            
        Returns:
            Tuple of (can_transition, error_code_if_blocked)
        """
        # Check if current state is terminal
        if self.current_state in self.TERMINAL_STATES:
            return False, ErrorCodeDictionary.STATE_001
        
        # Check if target state is in valid transitions
        allowed_states = self.VALID_TRANSITIONS.get(self.current_state, set())
        
        if target_state not in allowed_states:
            return False, ErrorCodeDictionary.STATE_001
        
        # Check if job is locked
        if self.current_state in self.LOCKED_STATES:
            return False, ErrorCodeDictionary.STATE_004
        
        return True, None
    
    def transition_to(
        self,
        target_state: JobState,
        reason: Optional[str] = None,
        error_code: Optional[str] = None,
    ) -> Tuple[bool, Optional[ErrorCode]]:
        """
        Attempt to transition to target state.
        
        Args:
            target_state: Target state to transition to
            reason: Optional reason for transition
            error_code: Optional error code if transition failed
            
        Returns:
            Tuple of (success, error_code_if_failed)
        """
        can_transition, error = self.can_transition_to(target_state)
        
        if not can_transition:
            return False, error
        
        # Record transition
        transition = StateTransition(
            from_state=self.current_state,
            to_state=target_state,
            timestamp=datetime.utcnow(),
            reason=reason,
            error_code=error_code,
        )
        self.transition_history.append(transition)
        
        # Update state
        self.current_state = target_state
        self.job.status = target_state.value
        
        return True, None
    
    def require_preflight_approved(self) -> Tuple[bool, Optional[ErrorCode]]:
        """
        Check if job is in PREFLIGHT_APPROVED state.
        
        Returns:
            Tuple of (is_approved, error_code_if_not)
        """
        if self.current_state != JobState.PREFLIGHT_APPROVED:
            return False, ErrorCodeDictionary.STATE_002
        return True, None
    
    def is_locked(self) -> bool:
        """Check if job is in a locked state."""
        return self.current_state in self.LOCKED_STATES
    
    def is_terminal(self) -> bool:
        """Check if job is in a terminal state."""
        return self.current_state in self.TERMINAL_STATES
    
    def get_transition_history(self) -> List[StateTransition]:
        """Get full transition history (copy)."""
        return self.transition_history.copy()
    
    def get_allowed_transitions(self) -> Set[JobState]:
        """Get all allowed transitions from current state (copy)."""
        return self.VALID_TRANSITIONS.get(self.current_state, set()).copy()


class StateMachineManager:
    """
    Manager for state machine operations with database persistence.
    
    Provides static methods for state machine operations that require
    database access and transaction management.
    """
    
    @staticmethod
    async def get_state_machine(
        db: AsyncSession, job_id: UUID
    ) -> Optional[StateMachine]:
        """
        Get state machine for a job.
        
        Args:
            db: Database session
            job_id: Job identifier
            
        Returns:
            StateMachine instance if job exists, None otherwise
        """
        query = select(GenerationJob).where(GenerationJob.id == job_id)
        result = await db.execute(query)
        job = result.scalar_one_or_none()
        
        if not job:
            return None
        
        return StateMachine(job)
    
    @staticmethod
    async def transition_job_state(
        db: AsyncSession,
        job_id: UUID,
        target_state: JobState,
        reason: Optional[str] = None,
        error_code: Optional[str] = None,
    ) -> Tuple[bool, Optional[ErrorCode], Optional[StateMachine]]:
        """
        Transition job to target state with database persistence.
        
        Args:
            db: Database session
            job_id: Job identifier
            target_state: Target state to transition to
            reason: Optional reason for transition
            error_code: Optional error code
            
        Returns:
            Tuple of (success, error_code_if_failed, state_machine)
        """
        state_machine = await StateMachineManager.get_state_machine(db, job_id)
        
        if not state_machine:
            return False, ErrorCodeDictionary.SYSTEM_001, None
        
        success, error = state_machine.transition_to(
            target_state, reason=reason, error_code=error_code
        )
        
        if success:
            # Update timestamps based on state
            if target_state == JobState.PREFLIGHT_APPROVED:
                state_machine.job.preflight_approved_at = datetime.utcnow()
            elif target_state == JobState.PROMPT_LOCKED:
                state_machine.job.prompt_locked_at = datetime.utcnow()
            elif target_state == JobState.PROCESSING:
                state_machine.job.started_at = datetime.utcnow()
            elif target_state in (JobState.COMPLETED, JobState.FAILED):
                state_machine.job.completed_at = datetime.utcnow()
            
            # Store transition history in job
            if not state_machine.job.state_transition_history:
                state_machine.job.state_transition_history = []
            
            state_machine.job.state_transition_history.append(
                state_machine.transition_history[-1].to_dict()
            )
            
            await db.commit()
            await db.refresh(state_machine.job)
        
        return success, error, state_machine
