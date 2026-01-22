#!/usr/bin/env python3
"""Check if api_keys table exists"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check_table():
    """Check if api_keys table exists"""
    # Use environment variable or connection string from .env
    import os
    from dotenv import load_dotenv
    load_dotenv()
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@host:port/database?ssl=require")

    print("Connecting to database...")
    engine = create_async_engine(db_url, echo=False, connect_args={"timeout": 10, "command_timeout": 10})

    try:
        async with engine.connect() as conn:
            print("✓ Connected successfully!")

            result = await conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'api_keys'
                );
            """))

            exists = result.scalar()

            if exists:
                print("✅ api_keys table EXISTS")

                # Get column info
                result = await conn.execute(text("""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = 'api_keys'
                    ORDER BY ordinal_position;
                """))

                columns = result.fetchall()
                print("\nColumns:")
                for col in columns:
                    print(f"  - {col[0]}: {col[1]}")
            else:
                print("❌ api_keys table DOES NOT EXIST")
                print("Migration needs to be run.")

            return exists

    except asyncio.TimeoutError:
        print("❌ Connection timed out")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_table())
