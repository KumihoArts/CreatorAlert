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
                embed_colour            TEXT,
                custom_message          TEXT,
                connected_at            TIMESTAMPTZ DEFAULT NOW()
            )
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
            CREATE TABLE IF NOT EXISTS creator_channels (
                guild_id        BIGINT NOT NULL,
                channel_id      BIGINT NOT NULL,
                patreon_user_id TEXT NOT NULL,
                ping_role_id    BIGINT,
                PRIMARY KEY (guild_id, patreon_user_id)
            )
        """)
        await conn.execute("""
            ALTER TABLE creator_channels
            ADD COLUMN IF NOT EXISTS ping_role_id BIGINT
        """)

        # seen_posts migration check
        has_seen_posts = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'seen_posts'
            )
        """)
        if has_seen_posts:
            discord_id_col = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'seen_posts' AND column_name = 'discord_id'
                )
            """)
            if not discord_id_col:
                print("Migrating seen_posts table to per-user schema...")
                await conn.execute("DROP TABLE seen_posts")
                await conn.execute("""
                    CREATE TABLE seen_posts (
                        discord_id      BIGINT NOT NULL,
                        post_id         TEXT NOT NULL,
                        seen_at         TIMESTAMPTZ DEFAULT NOW(),
                        PRIMARY KEY (discord_id, post_id)
                    )
                """)
                print("seen_posts migration complete.")
        else:
            await conn.execute("""
                CREATE TABLE seen_posts (
                    discord_id      BIGINT NOT NULL,
                    post_id         TEXT NOT NULL,
                    seen_at         TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (discord_id, post_id)
                )
            """)

        # Muted creators — per user, per campaign
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS muted_creators (
                discord_id      BIGINT NOT NULL,
                campaign_id     TEXT NOT NULL,
                muted_at        TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (discord_id, campaign_id)
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


async def get_user_by_patreon_id(patreon_user_id: str) -> dict | None:
    """Look up a Discord user by their Patreon user ID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM patreon_users WHERE patreon_user_id = $1", patreon_user_id
        )
        return dict(row) if row else None


async def delete_user(discord_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM patreon_users WHERE discord_id = $1", discord_id
        )
        await conn.execute(
            "DELETE FROM seen_posts WHERE discord_id = $1", discord_id
        )
        await conn.execute(
            "DELETE FROM muted_creators WHERE discord_id = $1", discord_id
        )


async def update_tokens(discord_id: int, access_token: str, refresh_token: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE patreon_users
            SET access_token = $2, refresh_token = $3
            WHERE discord_id = $1
        """, discord_id, access_token, refresh_token)


async def set_premium_style(discord_id: int, embed_colour: str | None, custom_message: str | None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE patreon_users
            SET embed_colour = $2, custom_message = $3
            WHERE discord_id = $1
        """, discord_id, embed_colour, custom_message)


async def get_all_users() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM patreon_users")
        return [dict(r) for r in rows]


async def mark_post_seen(discord_id: int, post_id: str):
    """Mark a post as seen for a specific Discord user."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO seen_posts (discord_id, post_id)
            VALUES ($1, $2)
            ON CONFLICT (discord_id, post_id) DO NOTHING
        """, discord_id, post_id)


async def is_post_seen(discord_id: int, post_id: str) -> bool:
    """Check if a specific Discord user has already been notified about this post."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM seen_posts WHERE discord_id = $1 AND post_id = $2",
            discord_id, post_id
        )
        return row is not None


async def mute_creator(discord_id: int, campaign_id: str):
    """Mute notifications from a specific creator for a user."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO muted_creators (discord_id, campaign_id)
            VALUES ($1, $2)
            ON CONFLICT (discord_id, campaign_id) DO NOTHING
        """, discord_id, campaign_id)


async def unmute_creator(discord_id: int, campaign_id: str):
    """Unmute notifications from a specific creator for a user."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM muted_creators
            WHERE discord_id = $1 AND campaign_id = $2
        """, discord_id, campaign_id)


async def get_muted_creators(discord_id: int) -> list[str]:
    """Return a list of muted campaign IDs for a user."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT campaign_id FROM muted_creators WHERE discord_id = $1", discord_id
        )
        return [r["campaign_id"] for r in rows]


async def is_muted(discord_id: int, campaign_id: str) -> bool:
    """Check if a user has muted a specific creator."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM muted_creators WHERE discord_id = $1 AND campaign_id = $2",
            discord_id, campaign_id
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


async def get_creator_channels_for_patreon_user(patreon_user_id: str) -> list[tuple[int, int, int | None]]:
    """Returns all (guild_id, channel_id, ping_role_id) rows for a given Patreon user ID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT guild_id, channel_id, ping_role_id
            FROM creator_channels
            WHERE patreon_user_id = $1
        """, patreon_user_id)
        return [(r["guild_id"], r["channel_id"], r["ping_role_id"]) for r in rows]


async def set_creator_ping_role(guild_id: int, patreon_user_id: str, role_id: int | None):
    """Set the ping role for a creator's channel in a specific guild."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE creator_channels
            SET ping_role_id = $3
            WHERE guild_id = $1 AND patreon_user_id = $2
        """, guild_id, patreon_user_id, role_id)
