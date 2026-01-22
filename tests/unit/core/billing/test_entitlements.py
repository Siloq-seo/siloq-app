"""Unit tests for entitlements module"""
import pytest
from app.core.billing.entitlements import (
    PlanEntitlements,
    FEATURE_MATRIX,
    get_plan_entitlements,
    get_minimum_plan,
)


class TestPlanEntitlements:
    """Tests for plan entitlements"""
    
    def test_trial_entitlements(self):
        """Test trial plan entitlements"""
        trial = PlanEntitlements.TRIAL
        
        assert trial["create_project"] is True
        assert trial["view_governance_dashboard"] is True
        assert trial["draft_generation"] is False
        assert trial["publish"] is False
        assert trial["max_projects"] == 1
    
    def test_blueprint_entitlements(self):
        """Test blueprint plan entitlements"""
        blueprint = PlanEntitlements.BLUEPRINT
        
        assert blueprint["generate_recommendations"] is True
        assert blueprint["draft_generation"] is False  # Still blocked
        assert blueprint["max_projects"] == 1
    
    def test_operator_entitlements(self):
        """Test operator plan entitlements"""
        operator = PlanEntitlements.OPERATOR
        
        assert operator["draft_generation"] is True
        assert operator["apply_content"] is True
        assert operator["publish"] is True
        assert operator["bulk_actions"] is False
        assert operator["max_projects"] == 1
        assert operator["max_concurrent_jobs"] == 5
    
    def test_agency_entitlements(self):
        """Test agency plan entitlements"""
        agency = PlanEntitlements.AGENCY
        
        assert agency["bulk_draft_generation"] is True
        assert agency["client_segmentation"] is True
        assert agency["max_projects"] == 5
        assert agency["max_concurrent_jobs"] == 10
    
    def test_empire_entitlements(self):
        """Test empire plan entitlements"""
        empire = PlanEntitlements.EMPIRE
        
        assert empire["white_label_ui"] is True
        assert empire["agency_command_center"] is True
        assert empire["api_priority_queue"] is True
        assert empire["max_projects"] == 20
        assert empire["max_concurrent_jobs"] == 20


class TestFeatureMatrix:
    """Tests for feature matrix"""
    
    def test_feature_matrix_structure(self):
        """Test that feature matrix has correct structure"""
        assert "governance_dashboard" in FEATURE_MATRIX
        assert "draft_generation" in FEATURE_MATRIX
        assert "bulk_drafts" in FEATURE_MATRIX
        assert "white_label" in FEATURE_MATRIX
    
    def test_governance_dashboard_available_to_all(self):
        """Test that governance dashboard is available to all plans"""
        allowed_plans = FEATURE_MATRIX["governance_dashboard"]
        
        assert "trial" in allowed_plans
        assert "blueprint" in allowed_plans
        assert "operator" in allowed_plans
        assert "agency" in allowed_plans
        assert "empire" in allowed_plans
    
    def test_draft_generation_requires_paid_plan(self):
        """Test that draft generation requires paid plan"""
        allowed_plans = FEATURE_MATRIX["draft_generation"]
        
        assert "trial" not in allowed_plans
        assert "blueprint" not in allowed_plans
        assert "operator" in allowed_plans
        assert "agency" in allowed_plans
        assert "empire" in allowed_plans
    
    def test_white_label_requires_empire(self):
        """Test that white label requires empire plan"""
        allowed_plans = FEATURE_MATRIX["white_label"]
        
        assert "trial" not in allowed_plans
        assert "operator" not in allowed_plans
        assert "agency" not in allowed_plans
        assert "empire" in allowed_plans


class TestPlanHelpers:
    """Tests for plan helper functions"""
    
    def test_get_plan_entitlements(self):
        """Test getting plan entitlements"""
        # Test with string plan keys
        trial_entitlements = get_plan_entitlements("trial")
        assert trial_entitlements["max_projects"] == 1
        
        operator_entitlements = get_plan_entitlements("operator")
        assert operator_entitlements["max_projects"] == 1
        assert operator_entitlements["draft_generation"] is True
    
    def test_get_minimum_plan(self):
        """Test getting minimum plan for feature"""
        assert get_minimum_plan("governance_dashboard") == "trial"
        assert get_minimum_plan("draft_generation") == "operator"
        assert get_minimum_plan("bulk_drafts") == "agency"
        assert get_minimum_plan("white_label") == "empire"
