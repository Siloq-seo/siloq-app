"""Unit tests for reverse silos governance"""
import pytest
from uuid import uuid4
from app.governance.structure.reverse_silos import ReverseSiloEnforcer
from app.db.models import Site, Silo


class TestReverseSiloEnforcer:
    """Tests for reverse silo enforcement"""
    
    @pytest.mark.asyncio
    async def test_get_silo_count_empty(self, test_db_session):
        """Test getting silo count for site with no silos"""
        site = Site(name="Test Site", domain="test.com")
        test_db_session.add(site)
        await test_db_session.commit()
        
        enforcer = ReverseSiloEnforcer(min_silos=3, max_silos=7)
        count = await enforcer.get_silo_count(test_db_session, str(site.id))
        
        assert count == 0
    
    @pytest.mark.asyncio
    async def test_get_silo_count_with_silos(self, test_db_session):
        """Test getting silo count for site with silos"""
        site = Site(name="Test Site", domain="test.com")
        test_db_session.add(site)
        await test_db_session.commit()
        
        # Add some silos
        for i in range(3):
            silo = Silo(
                site_id=site.id,
                name=f"Silo {i+1}",
                slug=f"silo-{i+1}",
                position=i+1
            )
            test_db_session.add(silo)
        await test_db_session.commit()
        
        enforcer = ReverseSiloEnforcer(min_silos=3, max_silos=7)
        count = await enforcer.get_silo_count(test_db_session, str(site.id))
        
        assert count == 3
    
    @pytest.mark.asyncio
    async def test_can_add_silo_when_under_max(self, test_db_session):
        """Test that silo can be added when under max limit"""
        site = Site(name="Test Site", domain="test.com")
        test_db_session.add(site)
        await test_db_session.commit()
        
        enforcer = ReverseSiloEnforcer(min_silos=3, max_silos=7)
        can_add, reason = await enforcer.can_add_silo(test_db_session, str(site.id))
        
        assert can_add is True
        assert reason == ""
    
    @pytest.mark.asyncio
    async def test_cannot_add_silo_when_at_max(self, test_db_session):
        """Test that silo cannot be added when at max limit"""
        site = Site(name="Test Site", domain="test.com")
        test_db_session.add(site)
        await test_db_session.commit()
        
        # Add max silos
        for i in range(7):
            silo = Silo(
                site_id=site.id,
                name=f"Silo {i+1}",
                slug=f"silo-{i+1}",
                position=i+1
            )
            test_db_session.add(silo)
        await test_db_session.commit()
        
        enforcer = ReverseSiloEnforcer(min_silos=3, max_silos=7)
        can_add, reason = await enforcer.can_add_silo(test_db_session, str(site.id))
        
        assert can_add is False
        assert "Maximum silos (7)" in reason
    
    @pytest.mark.asyncio
    async def test_validate_silo_structure_valid(self, test_db_session):
        """Test silo structure validation for valid structure"""
        site = Site(name="Test Site", domain="test.com")
        test_db_session.add(site)
        await test_db_session.commit()
        
        # Add valid number of silos (within 3-7 range)
        for i in range(5):
            silo = Silo(
                site_id=site.id,
                name=f"Silo {i+1}",
                slug=f"silo-{i+1}",
                position=i+1
            )
            test_db_session.add(silo)
        await test_db_session.commit()
        
        enforcer = ReverseSiloEnforcer(min_silos=3, max_silos=7)
        is_valid, message = await enforcer.validate_silo_structure(
            test_db_session, str(site.id)
        )
        
        assert is_valid is True
    
    @pytest.mark.asyncio
    async def test_validate_silo_structure_below_min(self, test_db_session):
        """Test silo structure validation when below minimum"""
        site = Site(name="Test Site", domain="test.com")
        test_db_session.add(site)
        await test_db_session.commit()
        
        # Add only 2 silos (below minimum of 3)
        for i in range(2):
            silo = Silo(
                site_id=site.id,
                name=f"Silo {i+1}",
                slug=f"silo-{i+1}",
                position=i+1
            )
            test_db_session.add(silo)
        await test_db_session.commit()
        
        enforcer = ReverseSiloEnforcer(min_silos=3, max_silos=7)
        is_valid, message = await enforcer.validate_silo_structure(
            test_db_session, str(site.id)
        )
        
        assert is_valid is False
        assert "minimum" in message.lower() or "3" in message
