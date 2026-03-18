import asyncpg
import os

_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))
    return _pool

async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS patreon_users (
                discord_id      BIGINT PRIMARY KEY,
                patreon_user_id TEXT NOT NULL,
                access_token    TEXT NOT NULL,
                refresh_token   TEXT NOT NULL,
                token_expires   TIMESTAMPTZ,
                connected_at    TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS creator_channels (
                guild_id        BIGINT NOT NULL,
                channel_id      BIGINT NOT NULL,
                patreon_user_id TEXT NOT NULL,
                PRIMARY KEY (guild_id, patreon_user_id)
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_posts (
                post_id         TEXT PRIMARY KEY,
                patreon_user_id TEXT NOT NULL,
                seen_at         TIMESTAMPTZ DEFAULT NOW()
            )
        """)

    print("Database initialised.")
