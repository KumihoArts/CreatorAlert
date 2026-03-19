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
                discord_id              BIGINT PRIMARY KEY,
                patreon_user_id         TEXT NOT NULL,
                access_token            TEXT NOT NULL,
                refresh_token           TEXT NOT NULL,
                token_expires           TIMESTAMPTZ,
                notification_mode       TEXT NOT NULL DEFAULT 'dm',
                notification_channel_id BIGINT,
                embed_colour            TEXT,
                custom_message          TEXT,
                ping_role_id            BIGINT,
                connected_at            TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute("""
            ALTER TABLE patreon_users
            ADD COLUMN IF NOT EXISTS notification_mode TEXT NOT NULL DEFAULT 'dm'
        """)
        await conn.execute("""
            ALTER TABLE patreon_users
            ADD COLUMN IF NOT EXISTS notification_channel_id BIGINT
        """)
        await conn.execute("""
            ALTER TABLE patreon_users
            ADD COLUMN IF NOT EXISTS embed_colour TEXT
        """)
        await conn.execute("""
            ALTER TABLE patreon_users
            ADD COLUMN IF NOT EXISTS custom_message TEXT
        """)
        await conn.execute("""
            ALTER TABLE patreon_users
            ADD COLUMN IF NOT EXISTS ping_role_id BIGINT
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS premium_channels (
                id              SERIAL PRIMARY KEY,
                discord_id      BIGINT NOT NULL,
                channel_id      BIGINT NOT NULL,
                UNIQUE (discord_id, channel_id)
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


async def get_user(discord_id: int) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM patreon_users WHERE discord_id = $1", discord_id
        )
        return dict(row) if row else None


async def delete_user(discord_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM patreon_users WHERE discord_id = $1", discord_id
        )
        await conn.execute(
            "DELETE FROM premium_channels WHERE discord_id = $1", discord_id
        )


async def update_tokens(discord_id: int, access_token: str, refresh_token: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE patreon_users
            SET access_token = $2, refresh_token = $3
            WHERE discord_id = $1
        """, discord_id, access_token, refresh_token)


async def set_notification_mode(discord_id: int, mode: str, channel_id: int | None = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE patreon_users
            SET notification_mode = $2, notification_channel_id = $3
            WHERE discord_id = $1
        """, discord_id, mode, channel_id)


async def set_premium_style(discord_id: int, embed_colour: str | None, custom_message: str | None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE patreon_users
            SET embed_colour = $2, custom_message = $3
            WHERE discord_id = $1
        """, discord_id, embed_colour, custom_message)


async def set_ping_role(discord_id: int, role_id: int | None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE patreon_users
            SET ping_role_id = $2
            WHERE discord_id = $1
        """, discord_id, role_id)


async def add_premium_channel(discord_id: int, channel_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO premium_channels (discord_id, channel_id)
            VALUES ($1, $2)
            ON CONFLICT (discord_id, channel_id) DO NOTHING
        """, discord_id, channel_id)


async def remove_premium_channel(discord_id: int, channel_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM premium_channels
            WHERE discord_id = $1 AND channel_id = $2
        """, discord_id, channel_id)


async def get_premium_channels(discord_id: int) -> list[int]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT channel_id FROM premium_channels WHERE discord_id = $1", discord_id
        )
        return [r["channel_id"] for r in rows]


async def get_all_users() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM patreon_users")
        return [dict(r) for r in rows]


async def mark_post_seen(post_id: str, patreon_user_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO seen_posts (post_id, patreon_user_id)
            VALUES ($1, $2)
            ON CONFLICT (post_id) DO NOTHING
        """, post_id, patreon_user_id)


async def is_post_seen(post_id: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM seen_posts WHERE post_id = $1", post_id
        )
        return row is not None


async def set_creator_channel(guild_id: int, channel_id: int, patreon_user_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO creator_channels (guild_id, channel_id, patreon_user_id)
            VALUES ($1, $2, $3)
            ON CONFLICT (guild_id, patreon_user_id) DO UPDATE
            SET channel_id = $2
        """, guild_id, channel_id, patreon_user_id)


async def get_creator_channel(guild_id: int, patreon_user_id: str) -> int | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT channel_id FROM creator_channels WHERE guild_id = $1 AND patreon_user_id = $2",
            guild_id, patreon_user_id
        )
        return row["channel_id"] if row else None
