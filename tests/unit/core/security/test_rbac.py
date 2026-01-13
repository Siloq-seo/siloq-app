"""Unit tests for RBAC module"""
import pytest
from app.core.security.rbac import (
    Role,
    has_permission,
    get_minimum_role_for_action,
    get_allowed_actions,
)


class TestRoleEnum:
    """Tests for Role enum"""
    
    def test_role_values(self):
        """Test that Role enum has correct values"""
        assert Role.OWNER.value == "owner"
        assert Role.ADMIN.value == "admin"
        assert Role.EDITOR.value == "editor"
        assert Role.VIEWER.value == "viewer"


class TestPermissionChecking:
    """Tests for permission checking"""
    
    def test_owner_has_all_permissions(self):
        """Test that owner role has all permissions"""
        assert has_permission(Role.OWNER, "project.delete") is True
        assert has_permission(Role.OWNER, "billing.update") is True
        assert has_permission(Role.OWNER, "content.create") is True
        assert has_permission(Role.OWNER, "content.read") is True
    
    def test_admin_has_content_permissions(self):
        """Test that admin role has content permissions"""
        assert has_permission(Role.ADMIN, "content.create") is True
        assert has_permission(Role.ADMIN, "content.edit") is True
        assert has_permission(Role.ADMIN, "users.manage") is True
        assert has_permission(Role.ADMIN, "billing.update") is False  # No billing
    
    def test_editor_has_limited_permissions(self):
        """Test that editor role has limited permissions"""
        assert has_permission(Role.EDITOR, "content.create") is True
        assert has_permission(Role.EDITOR, "content.edit") is True
        assert has_permission(Role.EDITOR, "content.read") is True
        assert has_permission(Role.EDITOR, "users.manage") is False
        assert has_permission(Role.EDITOR, "billing.update") is False
    
    def test_viewer_has_read_only_permissions(self):
        """Test that viewer role has read-only permissions"""
        assert has_permission(Role.VIEWER, "content.read") is True
        assert has_permission(Role.VIEWER, "metrics.view") is True
        assert has_permission(Role.VIEWER, "content.create") is False
        assert has_permission(Role.VIEWER, "content.edit") is False
    
    def test_wildcard_permissions(self):
        """Test that wildcard permissions work"""
        # content.* should match content.create, content.edit, etc.
        assert has_permission(Role.OWNER, "content.create") is True
        assert has_permission(Role.ADMIN, "content.edit") is True
        assert has_permission(Role.EDITOR, "content.read") is True


class TestMinimumRole:
    """Tests for minimum role calculation"""
    
    def test_minimum_role_for_billing(self):
        """Test minimum role for billing actions"""
        assert get_minimum_role_for_action("billing.update") == "owner"
        assert get_minimum_role_for_action("project.delete") == "owner"
    
    def test_minimum_role_for_user_management(self):
        """Test minimum role for user management"""
        assert get_minimum_role_for_action("users.manage") == "admin"
    
    def test_minimum_role_for_content(self):
        """Test minimum role for content actions"""
        assert get_minimum_role_for_action("content.create") == "editor"
        assert get_minimum_role_for_action("content.read") == "viewer"


class TestAllowedActions:
    """Tests for allowed actions retrieval"""
    
    def test_owner_allowed_actions(self):
        """Test allowed actions for owner"""
        actions = get_allowed_actions(Role.OWNER)
        
        assert "project.delete" in actions
        assert "billing.update" in actions
        assert "content.*" in actions
        assert len(actions) > 0
    
    def test_viewer_allowed_actions(self):
        """Test allowed actions for viewer"""
        actions = get_allowed_actions(Role.VIEWER)
        
        assert "content.read" in actions
        assert "metrics.view" in actions
        assert "content.create" not in actions
        assert len(actions) > 0
