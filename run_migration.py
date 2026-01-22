#!/usr/bin/env python3
"""Run SQL migration file"""
import asyncio
import sys
import os
from sqlalchemy.ext.asyncio import create_async_engine
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def run_migration(sql_file: str):
    """Execute SQL migration file"""
    # Read SQL file
    sql_content = Path(sql_file).read_text()

    # Get database URL from environment
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        raise ValueError("DATABASE_URL environment variable is not set. Please configure it in .env file.")

    # Create engine
    engine = create_async_engine(db_url, echo=True)

    try:
        async with engine.begin() as conn:
            # Split by semicolon and execute each statement
            statements = [s.strip() for s in sql_content.split(';') if s.strip()]

            for statement in statements:
                if statement:
                    print(f"\n>>> Executing:\n{statement[:100]}...")
                    await conn.execute(statement)
                    print("✓ Success")

        print("\n✅ Migration completed successfully!")
        return True

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        return False

    finally:
        await engine.dispose()

if __name__ == "__main__":
    sql_file = sys.argv[1] if len(sys.argv) > 1 else "migrations/V013__api_keys_table.sql"
    success = asyncio.run(run_migration(sql_file))
    sys.exit(0 if success else 1)
