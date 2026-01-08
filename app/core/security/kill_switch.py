"""Kill switch functionality - Section 7: Emergency controls"""
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os

from app.core.config import settings
from app.db.models import User, Project, ProjectAISettings
from app.exceptions import GovernanceError
from app.decision.error_codes import (
    ErrorCodeDictionary,
    ErrorCode
)


class KillSwitchManager:
    """Manages kill switches at global, project, and user levels"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def check_generation_allowed(
        self,
        project_id: UUID,
        user_id: UUID
    ) -> bool:
        """
        Check if AI generation is allowed for a project and user.
        
        Checks in order:
        1. Global kill switch (environment variable)
        2. Project-level kill switch
        3. User-level kill switch
        
        Args:
            project_id: Project UUID
            user_id: User UUID
            
        Returns:
            True if generation is allowed
            
        Raises:
            GovernanceError: If generation is disabled
        """
        # 1. Check global kill switch
        if not settings.global_generation_enabled:
            error = ErrorCodeDictionary.AI_GENERATION_GLOBALLY_DISABLED
            raise GovernanceError(error, project_id)
        
        # 2. Check project-level kill switch
        project_ai_settings = await self.db.get(ProjectAISettings, project_id)
        if project_ai_settings and not project_ai_settings.generation_enabled:
            error = ErrorCodeDictionary.AI_GENERATION_DISABLED_FOR_PROJECT
            raise GovernanceError(error, project_id)
        
        # 3. Check user-level kill switch
        user = await self.db.get(User, user_id)
        if user and not user.generation_enabled:
            error = ErrorCodeDictionary.AI_GENERATION_DISABLED_FOR_USER
            raise GovernanceError(error, project_id)
        
        return True
    
    async def set_project_kill_switch(
        self,
        project_id: UUID,
        enabled: bool
    ) -> ProjectAISettings:
        """
        Set project-level kill switch.
        
        Args:
            project_id: Project UUID
            enabled: True to enable, False to disable
            
        Returns:
            Updated ProjectAISettings
        """
        project_ai_settings = await self.db.get(ProjectAISettings, project_id)
        
        if not project_ai_settings:
            # Create if doesn't exist
            from app.db.models import ProjectAISettings
            project_ai_settings = ProjectAISettings(
                project_id=project_id,
                generation_enabled=enabled
            )
            self.db.add(project_ai_settings)
        else:
            project_ai_settings.generation_enabled = enabled
        
        await self.db.commit()
        await self.db.refresh(project_ai_settings)
        
        return project_ai_settings
    
    async def set_user_kill_switch(
        self,
        user_id: UUID,
        enabled: bool
    ) -> User:
        """
        Set user-level kill switch.
        
        Args:
            user_id: User UUID
            enabled: True to enable, False to disable
            
        Returns:
            Updated User
        """
        user = await self.db.get(User, user_id)
        
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        user.generation_enabled = enabled
        await self.db.commit()
        await self.db.refresh(user)
        
        return user
    
    @staticmethod
    def get_global_kill_switch_status() -> bool:
        """
        Get global kill switch status from environment.
        
        Returns:
            True if generation is globally enabled
        """
        return settings.global_generation_enabled


def get_kill_switch_manager(db: AsyncSession) -> KillSwitchManager:
    """Get kill switch manager instance"""
    return KillSwitchManager(db)
