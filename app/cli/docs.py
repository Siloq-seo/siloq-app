"""Documentation generation commands for Siloq CLI."""
from pathlib import Path
from typing import List, Tuple

import click

from app.cli.db import db_connection, get_project_root


@click.group()
def docs_group() -> None:
    """Documentation generation commands."""
    pass


@docs_group.command()
def schema() -> None:
    """Generate schema documentation."""
    click.echo(click.style("Generating schema documentation...", fg="yellow"))
    generate_schema_docs()


def generate_schema_docs() -> None:
    """Generate comprehensive schema documentation."""
    project_root = get_project_root()
    docs_dir = project_root / "docs"
    docs_dir.mkdir(exist_ok=True, parents=True)
    
    with db_connection() as conn:
        cur = conn.cursor()
        
        tables = _get_tables(cur)
        constraints = _get_constraints(cur)
        
        doc_content = _build_documentation(tables, constraints)
        
        doc_file = docs_dir / "SCHEMA.md"
        with open(doc_file, "w", encoding="utf-8") as f:
            f.write(doc_content)
        
        cur.close()
    
    click.echo(
        click.style(
            f"✓ Schema documentation generated: {doc_file}",
            fg="green",
        )
    )


def _get_tables(cur) -> List[str]:
    """Get list of all tables in the database."""
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)
    return [row[0] for row in cur.fetchall()]


def _get_constraints(cur) -> List[Tuple[str, str, str, str]]:
    """Get all constraints from the database."""
    cur.execute("""
        SELECT 
            tc.table_name,
            tc.constraint_name,
            tc.constraint_type,
            kcu.column_name
        FROM information_schema.table_constraints tc
        LEFT JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
        WHERE tc.table_schema = 'public'
        ORDER BY tc.table_name, tc.constraint_type;
    """)
    return cur.fetchall()


def _build_documentation(
    tables: List[str], constraints: List[Tuple[str, str, str, str]]
) -> str:
    """Build markdown documentation from database metadata."""
    doc_parts = [
        "# Siloq Database Schema Documentation",
        "",
        "## Overview",
        "",
        (
            "This document describes the Siloq database schema v1.1 with "
            "v1.3.1 patches. The schema is designed to enforce structural "
            "guarantees at the database level, making bad states "
            "(cannibalization, duplicates) impossible by design."
        ),
        "",
        "## Core Principles",
        "",
        "1. **Unique normalized paths** - No two pages can resolve to the same URL",
        (
            "2. **Canonical uniqueness** - One canonical source per content entity"
        ),
        (
            "3. **Keyword → Page one-to-one mapping** - Each keyword targets "
            "exactly one page"
        ),
        (
            "4. **Silo count enforcement** - 3-7 silos per site, enforced at "
            "database level"
        ),
        (
            "5. **Automatic decay** - Stale proposals and orphaned pages are "
            "automatically archived"
        ),
        "",
        "## Tables",
        "",
    ]
    
    # Add table documentation (simplified - full implementation would query columns)
    doc_parts.append("### Table Details")
    doc_parts.append("")
    doc_parts.append(
        "For detailed table structures, constraints, and examples, "
        "see the full documentation below."
    )
    doc_parts.append("")
    
    # Add constraint explanations
    doc_parts.extend(_get_constraint_explanations())
    
    return "\n".join(doc_parts)


def _get_constraint_explanations() -> List[str]:
    """Get constraint explanation documentation."""
    return [
        "## Key Constraints Explained",
        "",
        "### Unique Normalized Paths",
        "",
        (
            "The `uniq_page_normalized_path_per_site` constraint ensures that "
            "no two pages can have the same normalized path within a site. The "
            "`normalized_path` is a generated column that automatically "
            "lowercases and trims the `path` column."
        ),
        "",
        "**Example:**",
        "```sql",
        "-- This will succeed",
        "INSERT INTO pages (site_id, path, title) VALUES (site_id, '/test-page', 'Test');",
        "",
        "-- This will fail (duplicate normalized path)",
        (
            "INSERT INTO pages (site_id, path, title) VALUES "
            "(site_id, '/TEST-PAGE', 'Test 2');"
        ),
        "```",
        "",
        "### Keyword One-to-One Mapping",
        "",
        (
            "The `keywords.page_id UNIQUE` constraint ensures each keyword maps "
            "to exactly one page. The `prevent_keyword_reassignment()` trigger "
            "prevents reassigning a keyword to a different page."
        ),
        "",
        "**Example:**",
        "```sql",
        "-- This will succeed",
        "INSERT INTO keywords (keyword, page_id) VALUES ('seo-tips', page1_id);",
        "",
        "-- This will fail (keyword already exists)",
        "INSERT INTO keywords (keyword, page_id) VALUES ('seo-tips', page2_id);",
        "",
        "-- This will fail (reassignment prevented by trigger)",
        "UPDATE keywords SET page_id = page2_id WHERE keyword = 'seo-tips';",
        "```",
        "",
        "### Silo Count Enforcement",
        "",
        "The `enforce_silo_count()` trigger ensures each site has between 3 and 7 silos.",
        "",
        "**Example:**",
        "```sql",
        "-- This will fail if site already has 7 silos",
        (
            "INSERT INTO silos (site_id, name, slug, position) VALUES "
            "(site_id, 'Silo 8', 'silo-8', 8);"
        ),
        "```",
        "",
        "### SILO_DECAY Trigger",
        "",
        "The `trigger_silo_decay()` function automatically archives:",
        "- Stale proposals (older than 90 days)",
        "- Orphaned pages (no keyword, no silo, older than 90 days)",
        "",
        "**Example:**",
        "```sql",
        "-- Create a stale proposal",
        (
            "INSERT INTO pages (site_id, path, title, is_proposal, created_at) "
            "VALUES (site_id, '/old', 'Old', true, NOW() - INTERVAL '91 days');"
        ),
        "",
        "-- Trigger decay by updating",
        "UPDATE pages SET is_proposal = true WHERE id = page_id;",
        "",
        "-- Page is automatically decommissioned",
        "```",
        "",
        "## Migration History",
        "",
        "- **V001**: Initial schema (v1.1)",
        "- **V002**: SILO_DECAY trigger (v1.3.1)",
        "- **V003**: Additional constraint enforcement (v1.3.1)",
        "",
        "## Rollback",
        "",
        "All migrations have corresponding rollback scripts in `migrations/rollback/`.",
        "",
    ]
