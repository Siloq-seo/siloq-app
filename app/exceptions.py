"""Custom exceptions for Siloq governance engine"""
from typing import Optional, Dict, Any
from uuid import UUID

from app.decision.error_codes import ErrorCode


class GovernanceError(Exception):
    """Base exception for governance-related errors"""
    
    def __init__(
        self,
        error_code: ErrorCode,
        entity_id: Optional[UUID] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        self.error_code = error_code
        self.entity_id = entity_id
        self.context = context or {}
        super().__init__(error_code.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        return {
            "code": self.error_code.code,
            "message": self.error_code.message,
            "doctrine_reference": self.error_code.doctrine_reference,
            "remediation_steps": self.error_code.remediation_steps,
            "entity_id": str(self.entity_id) if self.entity_id else None,
            "context": self.context,
        }


class ValidationError(GovernanceError):
    """Exception raised when validation fails"""
    pass


class PublishingError(GovernanceError):
    """Exception raised when publishing fails"""
    pass


class DecommissionError(GovernanceError):
    """Exception raised when decommissioning fails"""
    pass


class CannibalizationError(GovernanceError):
    """Exception raised when cannibalization is detected"""
    pass


class LifecycleGateError(GovernanceError):
    """Exception raised when lifecycle gates fail"""
    pass

