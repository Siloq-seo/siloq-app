"""Test and verification commands for Siloq CLI."""
from typing import Any

import click
import psycopg2
from psycopg2.extensions import connection

from app.cli.db import db_connection


class TestResult:
    """Container for test results."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0

    def add_pass(self) -> None:
        """Increment passed test count."""
        self.passed += 1

    def add_fail(self) -> None:
        """Increment failed test count."""
        self.failed += 1

    def is_success(self) -> bool:
        """Check if all tests passed."""
        return self.failed == 0


@click.group()
def test_group() -> None:
    """Test and verification commands."""
    pass


@test_group.command()
def uniqueness() -> None:
    """Verify path and canonical uniqueness constraints."""
    click.echo(click.style("Testing uniqueness constraints...", fg="yellow"))
    
    result = TestResult()
    
    with db_connection() as conn:
        cur = conn.cursor()
        
        # Test 1: Duplicate normalized path
        _test_duplicate_path(cur, conn, result)
        
        # Test 2: Keyword one-to-one mapping
        _test_keyword_mapping(cur, conn, result)
        
        cur.close()
    
    _print_test_results(result, "uniqueness")


@test_group.command()
def keyword_lock() -> None:
    """Verify one-to-one keyword mapping constraint."""
    click.echo(
        click.style("Testing keyword one-to-one mapping...", fg="yellow")
    )
    # This is covered in uniqueness test
    uniqueness.callback()


@test_group.command()
def silo_decay() -> None:
    """Verify SILO_DECAY trigger functionality."""
    click.echo(click.style("Testing SILO_DECAY trigger...", fg="yellow"))
    
    result = TestResult()
    
    with db_connection() as conn:
        cur = conn.cursor()
        
        try:
            _test_silo_decay_trigger(cur, conn, result)
        except Exception as e:
            click.echo(click.style(f"    ✗ ERROR: {e}", fg="red"))
            result.add_fail()
            conn.rollback()
        finally:
            cur.close()
    
    _print_test_results(result, "SILO_DECAY")


@test_group.command()
def all() -> None:
    """Run all verification tests."""
    run_all_tests()


def run_all_tests() -> None:
    """Run all verification tests."""
    click.echo(
        click.style(
            "=== Running All Verification Tests ===",
            fg="green",
            bold=True,
        )
    )
    click.echo()
    
    uniqueness.callback()
    click.echo()
    silo_decay.callback()
    click.echo()
    
    click.echo(
        click.style("=== Test Suite Complete ===", fg="green", bold=True)
    )


def _test_duplicate_path(
    cur: Any, conn: connection, result: TestResult
) -> None:
    """Test that duplicate normalized paths are rejected."""
    click.echo("  Test 1: Duplicate normalized path (should fail)...")
    
    try:
        # Create test site
        cur.execute("""
            INSERT INTO sites (id, name, domain) 
            VALUES (gen_random_uuid(), 'Test Site', 'test.com')
            ON CONFLICT DO NOTHING;
        """)
        cur.execute("SELECT id FROM sites WHERE domain = 'test.com' LIMIT 1")
        site_row = cur.fetchone()
        
        if not site_row:
            click.echo(click.style("    ✗ ERROR: Could not create test site", fg="red"))
            result.add_fail()
            return
        
        site_id = site_row[0]
        
        # Create first page
        cur.execute(
            """
            INSERT INTO pages (site_id, path, title) 
            VALUES (%s, '/test-page', 'Test Page');
        """,
            (site_id,),
        )
        
        # Try to create duplicate (different case)
        try:
            cur.execute(
                """
                INSERT INTO pages (site_id, path, title) 
                VALUES (%s, '/TEST-PAGE', 'Test Page 2');
            """,
                (site_id,),
            )
            conn.commit()
            click.echo(
                click.style(
                    "    ✗ FAILED: Duplicate path was allowed",
                    fg="red",
                )
            )
            result.add_fail()
        except psycopg2.IntegrityError:
            conn.rollback()
            click.echo(
                click.style(
                    "    ✓ PASSED: Duplicate path correctly rejected",
                    fg="green",
                )
            )
            result.add_pass()
    except Exception as e:
        click.echo(click.style(f"    ✗ ERROR: {e}", fg="red"))
        result.add_fail()
        conn.rollback()


def _test_keyword_mapping(
    cur: Any, conn: connection, result: TestResult
) -> None:
    """Test that keyword reassignment is prevented."""
    click.echo(
        "  Test 2: Keyword one-to-one mapping (should fail on reassignment)..."
    )
    
    try:
        # Get or create test site
        cur.execute("SELECT id FROM sites WHERE domain = 'test.com' LIMIT 1")
        site_row = cur.fetchone()
        
        if not site_row:
            click.echo(click.style("    ✗ ERROR: Test site not found", fg="red"))
            result.add_fail()
            return
        
        site_id = site_row[0]
        
        # Create first page
        cur.execute(
            """
            INSERT INTO pages (site_id, path, title) 
            VALUES (%s, '/page1', 'Page 1')
            RETURNING id;
        """,
            (site_id,),
        )
        page1_id = cur.fetchone()[0]
        
        # Create keyword for first page
        cur.execute(
            """
            INSERT INTO keywords (keyword, page_id) 
            VALUES ('test-keyword', %s);
        """,
            (page1_id,),
        )
        
        # Create second page
        cur.execute(
            """
            INSERT INTO pages (site_id, path, title) 
            VALUES (%s, '/page2', 'Page 2')
            RETURNING id;
        """,
            (site_id,),
        )
        page2_id = cur.fetchone()[0]
        
        # Try to reassign keyword
        try:
            cur.execute(
                """
                UPDATE keywords 
                SET page_id = %s 
                WHERE keyword = 'test-keyword';
            """,
                (page2_id,),
            )
            conn.commit()
            click.echo(
                click.style(
                    "    ✗ FAILED: Keyword reassignment was allowed",
                    fg="red",
                )
            )
            result.add_fail()
        except Exception:
            conn.rollback()
            click.echo(
                click.style(
                    "    ✓ PASSED: Keyword reassignment correctly prevented",
                    fg="green",
                )
            )
            result.add_pass()
    except Exception as e:
        click.echo(click.style(f"    ✗ ERROR: {e}", fg="red"))
        result.add_fail()
        conn.rollback()


def _test_silo_decay_trigger(
    cur: Any, conn: connection, result: TestResult
) -> None:
    """Test that SILO_DECAY trigger works correctly."""
    # Create test site
    cur.execute("""
        INSERT INTO sites (id, name, domain) 
        VALUES (gen_random_uuid(), 'Decay Test Site', 'decay-test.com')
        ON CONFLICT DO NOTHING;
    """)
    cur.execute("SELECT id FROM sites WHERE domain = 'decay-test.com' LIMIT 1")
    site_row = cur.fetchone()
    
    if not site_row:
        raise ValueError("Could not create test site")
    
    site_id = site_row[0]
    
    # Create a stale proposal page
    cur.execute(
        """
        INSERT INTO pages (site_id, path, title, is_proposal, status, created_at) 
        VALUES (%s, '/old-proposal', 'Old Proposal', true, 'draft', NOW() - INTERVAL '91 days')
        RETURNING id;
    """,
        (site_id,),
    )
    page_id = cur.fetchone()[0]
    conn.commit()
    
    # Trigger decay by updating
    cur.execute(
        """
        UPDATE pages 
        SET is_proposal = true 
        WHERE id = %s;
    """,
        (page_id,),
    )
    conn.commit()
    
    # Check if it was decommissioned
    cur.execute(
        """
        SELECT status, is_proposal 
        FROM pages 
        WHERE id = %s;
    """,
        (page_id,),
    )
    page_result = cur.fetchone()
    
    if page_result and page_result[0] == "decommissioned" and not page_result[1]:
        click.echo(
            click.style(
                "    ✓ PASSED: SILO_DECAY trigger fired correctly",
                fg="green",
            )
        )
        result.add_pass()
    else:
        click.echo(
            click.style(
                f"    ✗ FAILED: Page not decommissioned. "
                f"Status: {page_result[0] if page_result else 'None'}, "
                f"is_proposal: {page_result[1] if page_result else 'None'}",
                fg="red",
            )
        )
        result.add_fail()
    
    # Check system_events
    cur.execute("""
        SELECT COUNT(*) 
        FROM system_events 
        WHERE event_type = 'SILO_DECAY';
    """)
    event_count = cur.fetchone()[0]
    
    if event_count > 0:
        click.echo(
            click.style("    ✓ PASSED: System event logged", fg="green")
        )
        result.add_pass()
    else:
        click.echo(
            click.style("    ✗ FAILED: System event not logged", fg="red")
        )
        result.add_fail()


def _print_test_results(result: TestResult, test_name: str) -> None:
    """Print test results summary."""
    click.echo()
    click.echo(f"Results: {result.passed} passed, {result.failed} failed")
    
    if result.is_success():
        click.echo(
            click.style(f"✓ All {test_name} tests passed", fg="green")
        )
    else:
        click.echo(click.style(f"✗ Some {test_name} tests failed", fg="red"))
