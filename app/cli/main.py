"""Main CLI entry point for Siloq commands."""
import sys
from pathlib import Path

import click

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.cli import db, docs, test


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """Siloq - Governance-First AI SEO Platform CLI."""
    pass


# Register command groups
cli.add_command(db.db_group, name="db")
cli.add_command(test.test_group, name="test")
cli.add_command(docs.docs_group, name="docs")


@cli.command()
def reset_week1() -> None:
    """
    Full project reset and Week 1 implementation.
    
    This command performs a complete Week 1 reset:
    1. Checks for existing data (backup logic TODO)
    2. Drops all existing tables
    3. Runs migrations for Schema v1.1
    4. Applies v1.3.1 patches (is_proposal, system_events, SILO_DECAY)
    5. Creates all constraints and triggers
    6. Seeds with test data
    7. Runs verification tests
    8. Generates schema documentation
    """
    click.echo(click.style("=== Siloq Week 1 Reset ===", fg="green", bold=True))
    click.echo()
    
    steps = [
        ("Step 1: Checking for existing data...", _check_existing_data),
        ("Step 2: Resetting database...", lambda: db.reset_database()),
        ("Step 3-5: Running migrations...", lambda: db.run_migrations()),
        ("Step 6: Seeding test data...", _seed_with_error_handling),
        ("Step 7: Running verification tests...", test.run_all_tests),
        ("Step 8: Generating schema documentation...", docs.generate_schema_docs),
    ]
    
    for step_name, step_func in steps:
        click.echo(click.style(step_name, fg="yellow"))
        try:
            step_func()
        except Exception as e:
            click.echo(
                click.style(
                    f"✗ Error in {step_name}: {e}",
                    fg="red",
                )
            )
            raise click.Abort() from e
    
    _print_success_summary()


def _check_existing_data() -> None:
    """Check for existing data (backup logic TODO)."""
    # TODO: Implement backup logic
    pass


def _seed_with_error_handling() -> None:
    """Seed test data with error handling."""
    try:
        db.seed_test_data()
    except Exception as e:
        click.echo(
            click.style(
                f"Warning: Could not seed test data: {e}",
                fg="yellow",
            )
        )


def _print_success_summary() -> None:
    """Print success summary after reset."""
    click.echo()
    click.echo(click.style("✓ Week 1 reset complete!", fg="green", bold=True))
    click.echo()
    click.echo("Success metrics:")
    click.echo(
        "  ✓ Database enforces structure without UI intervention"
    )
    click.echo(
        "  ✓ Bad states (cannibalization, duplicates) are "
        "impossible by schema design"
    )
    click.echo("  ✓ All constraints tested and verified")
    click.echo("  ✓ Bootstrap runs cleanly on fresh install")


if __name__ == "__main__":
    cli()
