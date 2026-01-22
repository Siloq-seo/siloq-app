"""
2026 Governance Enhancement: Governance-Safe Personalization

While Siloq's Signal Registry Rule 2 (Deterministic Behavior) and Rule 3
(Configuration-Only AI) prohibit adaptive or self-modifying behavior, there's
a need for "Governance-Safe Personalization" that allows widgets to show
different "Validated Configurations" based on visitor state without violating
the "No AI-generated JS" law.

This module provides configuration-based personalization that:
- Uses pre-validated widget configurations (not AI-generated)
- Allows switching between configurations based on visitor state (new vs returning)
- Maintains deterministic behavior (no self-modification)
- Ensures all configurations pass governance checks before use
"""
from typing import Dict, List, Optional, Any
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import Page, SystemEvent
from app.core.config import settings


class VisitorState(str, Enum):
    """Visitor state types for personalization"""
    NEW_VISITOR = "new_visitor"
    RETURNING_VISITOR = "returning_visitor"
    ENGAGED_VISITOR = "engaged_visitor"
    MOBILE_VISITOR = "mobile_visitor"
    DESKTOP_VISITOR = "desktop_visitor"


class WidgetConfigurationType(str, Enum):
    """Types of widget configurations"""
    DIAGNOSTIC_QUIZ = "diagnostic_quiz"
    COMPARISON_TABLE = "comparison_table"
    TESTIMONIAL_CAROUSEL = "testimonial_carousel"
    CTA_BUTTON = "cta_button"
    PRICING_TABLE = "pricing_table"
    FAQ_ACCORDION = "faq_accordion"


class PersonalizationConfiguration:
    """
    Configuration-based personalization system.
    
    This allows different widget configurations to be shown based on visitor
    state, but all configurations must be pre-validated and governance-approved.
    """
    
    def __init__(self):
        # Configuration registry: page_id -> visitor_state -> widget_config
        self.config_registry: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    
    async def register_widget_configuration(
        self,
        db: AsyncSession,
        page_id: str,
        widget_type: WidgetConfigurationType,
        visitor_state: VisitorState,
        config_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Register a widget configuration for a specific visitor state.
        
        All configurations must pass governance validation before registration.
        
        Args:
            db: Database session
            page_id: Page ID
            widget_type: Type of widget
            visitor_state: Visitor state this configuration targets
            config_data: Configuration data (must be deterministic, not AI-generated)
            
        Returns:
            Registration result with validation status
        """
        # Validate configuration structure (deterministic check)
        validation_result = await self._validate_configuration(config_data, widget_type)
        
        if not validation_result["valid"]:
            return {
                "registered": False,
                "reason": validation_result["reason"],
                "errors": validation_result["errors"],
            }
        
        # Store configuration in registry
        page_key = str(page_id)
        if page_key not in self.config_registry:
            self.config_registry[page_key] = {}
        
        if visitor_state.value not in self.config_registry[page_key]:
            self.config_registry[page_key][visitor_state.value] = []
        
        # Check for duplicate configurations
        existing_configs = self.config_registry[page_key][visitor_state.value]
        if any(
            c.get("widget_type") == widget_type.value
            and c.get("config_data") == config_data
            for c in existing_configs
        ):
            return {
                "registered": False,
                "reason": "Configuration already exists for this visitor state",
            }
        
        # Add configuration
        config_entry = {
            "widget_type": widget_type.value,
            "config_data": config_data,
            "validated_at": None,  # Would be set by governance validation
        }
        
        self.config_registry[page_key][visitor_state.value].append(config_entry)
        
        # Log configuration registration
        audit = SystemEvent(
            event_type="personalization_config_registered",
            entity_type="page",
            entity_id=page_id,
            payload={
                "widget_type": widget_type.value,
                "visitor_state": visitor_state.value,
                "config_validated": validation_result["valid"],
            },
        )
        db.add(audit)
        
        return {
            "registered": True,
            "config_id": len(self.config_registry[page_key][visitor_state.value]) - 1,
            "validation_result": validation_result,
        }
    
    async def get_widget_configuration(
        self,
        page_id: str,
        visitor_state: VisitorState,
        widget_type: Optional[WidgetConfigurationType] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get widget configuration for a specific visitor state.
        
        This is deterministic - returns pre-validated configuration based on
        visitor state, with no AI generation or self-modification.
        
        Args:
            page_id: Page ID
            visitor_state: Current visitor state
            widget_type: Optional widget type filter
            
        Returns:
            Widget configuration dict or None
        """
        page_key = str(page_id)
        
        if page_key not in self.config_registry:
            return None
        
        state_configs = self.config_registry[page_key].get(visitor_state.value, [])
        
        if not state_configs:
            return None
        
        # If widget type specified, filter by type
        if widget_type:
            matching_configs = [
                c for c in state_configs
                if c.get("widget_type") == widget_type.value
            ]
            if matching_configs:
                return matching_configs[0]
            return None
        
        # Return first available configuration
        return state_configs[0] if state_configs else None
    
    async def _validate_configuration(
        self,
        config_data: Dict[str, Any],
        widget_type: WidgetConfigurationType,
    ) -> Dict[str, Any]:
        """
        Validate widget configuration structure.
        
        Ensures configuration is deterministic (no AI-generated code/JS).
        
        Args:
            config_data: Configuration data to validate
            widget_type: Type of widget
            
        Returns:
            Validation result
        """
        errors = []
        
        # Check 1: No JavaScript code in configuration (Rule 3: Configuration-Only AI)
        config_str = str(config_data).lower()
        js_indicators = [
            "function(",
            "=>",
            "document.",
            "window.",
            "eval(",
            "settimeout",
            "setinterval",
            "<script",
        ]
        
        for indicator in js_indicators:
            if indicator in config_str:
                errors.append(
                    f"Configuration contains JavaScript code ({indicator}). "
                    "Governance Rule 3 prohibits AI-generated JS."
                )
        
        # Check 2: Widget-specific validation
        widget_validation = self._validate_widget_specific(config_data, widget_type)
        if not widget_validation["valid"]:
            errors.extend(widget_validation["errors"])
        
        # Check 3: Ensure configuration is deterministic (no dynamic content generation)
        if self._has_dynamic_generation(config_data):
            errors.append(
                "Configuration appears to contain dynamic content generation. "
                "All content must be pre-validated (Rule 2: Deterministic Behavior)."
            )
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "reason": "; ".join(errors) if errors else "Configuration valid",
        }
    
    def _validate_widget_specific(
        self,
        config_data: Dict[str, Any],
        widget_type: WidgetConfigurationType,
    ) -> Dict[str, Any]:
        """Validate widget-specific configuration structure."""
        errors = []
        
        if widget_type == WidgetConfigurationType.DIAGNOSTIC_QUIZ:
            if "questions" not in config_data:
                errors.append("Diagnostic quiz requires 'questions' field")
            elif not isinstance(config_data["questions"], list):
                errors.append("Diagnostic quiz 'questions' must be a list")
        
        elif widget_type == WidgetConfigurationType.COMPARISON_TABLE:
            if "columns" not in config_data:
                errors.append("Comparison table requires 'columns' field")
            if "rows" not in config_data:
                errors.append("Comparison table requires 'rows' field")
        
        elif widget_type == WidgetConfigurationType.CTA_BUTTON:
            if "text" not in config_data:
                errors.append("CTA button requires 'text' field")
            if "url" not in config_data:
                errors.append("CTA button requires 'url' field")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }
    
    def _has_dynamic_generation(self, config_data: Dict[str, Any]) -> bool:
        """
        Check if configuration contains dynamic content generation.
        
        Looks for patterns that suggest AI-generated or dynamically generated content.
        """
        config_str = str(config_data).lower()
        
        # Check for AI generation patterns
        ai_indicators = [
            "generate",
            "ai_model",
            "openai",
            "gpt",
            "create_dynamically",
            "random",
            "shuffle",
        ]
        
        return any(indicator in config_str for indicator in ai_indicators)
    
    async def get_all_configurations_for_page(
        self,
        page_id: str,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all widget configurations for a page, organized by visitor state.
        
        Args:
            page_id: Page ID
            
        Returns:
            Dict mapping visitor_state -> list of configurations
        """
        page_key = str(page_id)
        return self.config_registry.get(page_key, {})
    
    async def validate_visitor_state_transition(
        self,
        current_state: VisitorState,
        new_state: VisitorState,
    ) -> bool:
        """
        Validate that a visitor state transition is allowed.
        
        Ensures deterministic state transitions (no arbitrary state changes).
        
        Args:
            current_state: Current visitor state
            new_state: Proposed new visitor state
            
        Returns:
            True if transition is allowed
        """
        # Define allowed state transitions (deterministic rules)
        allowed_transitions = {
            VisitorState.NEW_VISITOR: [
                VisitorState.RETURNING_VISITOR,
                VisitorState.ENGAGED_VISITOR,
            ],
            VisitorState.RETURNING_VISITOR: [
                VisitorState.ENGAGED_VISITOR,
            ],
            VisitorState.ENGAGED_VISITOR: [],  # Terminal state
            VisitorState.MOBILE_VISITOR: [VisitorState.DESKTOP_VISITOR],  # Device change
            VisitorState.DESKTOP_VISITOR: [VisitorState.MOBILE_VISITOR],  # Device change
        }
        
        allowed = allowed_transitions.get(current_state, [])
        return new_state in allowed or new_state == current_state

