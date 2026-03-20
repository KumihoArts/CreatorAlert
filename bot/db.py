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

        # -----------------------------------------------------------------------
        # connected_accounts
        # -----------------------------------------------------------------------
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS connected_accounts (
                discord_id       BIGINT NOT NULL,
                platform         TEXT NOT NULL DEFAULT 'patreon',
                platform_user_id TEXT NOT NULL,
                access_token     TEXT NOT NULL,
                refresh_token    TEXT NOT NULL,
                token_expires    TIMESTAMPTZ,
                embed_colour     TEXT,
                custom_message   TEXT,
                connected_at     TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (discord_id, platform)
            )
        """)

        has_old_table = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'patreon_users'
            )
        """)
        if has_old_table:
            print("Migrating patreon_users -> connected_accounts...")
            await conn.execute("""
                INSERT INTO connected_accounts (
                    discord_id, platform, platform_user_id, access_token,
                    refresh_token, token_expires, embed_colour, custom_message, connected_at
                )
                SELECT
                    discord_id, 'patreon', patreon_user_id, access_token,
                    refresh_token, token_expires, embed_colour, custom_message, connected_at
                FROM patreon_users
                ON CONFLICT (discord_id, platform) DO NOTHING
            """)
            await conn.execute("DROP TABLE patreon_users")
            print("patreon_users migration complete.")

        # -----------------------------------------------------------------------
        # creator_channels
        # -----------------------------------------------------------------------
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS creator_channels (
                guild_id         BIGINT NOT NULL,
                channel_id       BIGINT NOT NULL,
                platform_user_id TEXT NOT NULL,
                platform         TEXT NOT NULL DEFAULT 'patreon',
                ping_role_id     BIGINT,
                PRIMARY KEY (guild_id, platform_user_id, platform)
            )
        """)

        # Migrate old creator_channels schema (had patreon_user_id, no platform)
        has_platform_col = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'creator_channels' AND column_name = 'platform'
            )
        """)
        if not has_platform_col:
            print("Migrating creator_channels schema...")
            await conn.execute("""
                ALTER TABLE creator_channels
                ADD COLUMN IF NOT EXISTS platform TEXT NOT NULL DEFAULT 'patreon'
            """)
            has_old_col = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'creator_channels' AND column_name = 'patreon_user_id'
                )
            """)
            if has_old_col:
                await conn.execute("""
                    ALTER TABLE creator_channels
                    RENAME COLUMN patreon_user_id TO platform_user_id
                """)
            # Drop old PK and recreate with platform included
            await conn.execute("""
                ALTER TABLE creator_channels
                DROP CONSTRAINT IF EXISTS creator_channels_pkey
            """)
            await conn.execute("""
                ALTER TABLE creator_channels
                ADD PRIMARY KEY (guild_id, platform_user_id, platform)
            """)
            print("creator_channels migration complete.")

        # -----------------------------------------------------------------------
        # seen_posts
        # -----------------------------------------------------------------------
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
                        discord_id BIGINT NOT NULL,
                        post_id    TEXT NOT NULL,
                        seen_at    TIMESTAMPTZ DEFAULT NOW(),
                        PRIMARY KEY (discord_id, post_id)
                    )
                """)
                print("seen_posts migration complete.")
        else:
            await conn.execute("""
                CREATE TABLE seen_posts (
                    discord_id BIGINT NOT NULL,
                    post_id    TEXT NOT NULL,
                    seen_at    TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (discord_id, post_id)
                )
            """)

        # -----------------------------------------------------------------------
        # muted_creators
        # -----------------------------------------------------------------------
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS muted_creators (
                discord_id  BIGINT NOT NULL,
                platform    TEXT NOT NULL DEFAULT 'patreon',
                campaign_id TEXT NOT NULL,
                muted_at    TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (discord_id, platform, campaign_id)
            )
        """)

        muted_has_platform = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'muted_creators' AND column_name = 'platform'
            )
        """)
        if not muted_has_platform:
            print("Migrating muted_creators schema...")
            await conn.execute("""
                ALTER TABLE muted_creators
                ADD COLUMN IF NOT EXISTS platform TEXT NOT NULL DEFAULT 'patreon'
            """)
            await conn.execute("""
                ALTER TABLE muted_creators
                DROP CONSTRAINT IF EXISTS muted_creators_pkey
            """)
            await conn.execute("""
                ALTER TABLE muted_creators
                ADD PRIMARY KEY (discord_id, platform, campaign_id)
            """)
            print("muted_creators migration complete.")

    print("Database initialised.")


# ---------------------------------------------------------------------------
# connected_accounts
# ---------------------------------------------------------------------------

async def get_user(discord_id: int, platform: str = "patreon") -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM connected_accounts WHERE discord_id = $1 AND platform = $2",
            discord_id, platform
        )
        return dict(row) if row else None


async def get_all_user_platforms(discord_id: int) -> list[str]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT platform FROM connected_accounts WHERE discord_id = $1", discord_id
        )
        return [r["platform"] for r in rows]


async def get_user_by_platform_id(platform_user_id: str, platform: str) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM connected_accounts WHERE platform_user_id = $1 AND platform = $2",
            platform_user_id, platform
        )
        return dict(row) if row else None


async def delete_user(discord_id: int, platform: str = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if platform:
            await conn.execute(
                "DELETE FROM connected_accounts WHERE discord_id = $1 AND platform = $2",
                discord_id, platform
            )
            await conn.execute(
                "DELETE FROM muted_creators WHERE discord_id = $1 AND platform = $2",
                discord_id, platform
            )
        else:
            await conn.execute(
                "DELETE FROM connected_accounts WHERE discord_id = $1", discord_id
            )
            await conn.execute(
                "DELETE FROM muted_creators WHERE discord_id = $1", discord_id
            )
            await conn.execute(
                "DELETE FROM seen_posts WHERE discord_id = $1", discord_id
            )


async def update_tokens(discord_id: int, platform: str, access_token: str, refresh_token: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE connected_accounts
            SET access_token = $3, refresh_token = $4
            WHERE discord_id = $1 AND platform = $2
        """, discord_id, platform, access_token, refresh_token)


async def set_premium_style(discord_id: int, platform: str, embed_colour: str | None, custom_message: str | None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE connected_accounts
            SET embed_colour = $3, custom_message = $4
            WHERE discord_id = $1 AND platform = $2
        """, discord_id, platform, embed_colour, custom_message)


async def get_all_accounts() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM connected_accounts")
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# seen_posts
# ---------------------------------------------------------------------------

async def mark_post_seen(discord_id: int, post_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO seen_posts (discord_id, post_id)
            VALUES ($1, $2)
            ON CONFLICT (discord_id, post_id) DO NOTHING
        """, discord_id, post_id)


async def is_post_seen(discord_id: int, post_id: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM seen_posts WHERE discord_id = $1 AND post_id = $2",
            discord_id, post_id
        )
        return row is not None


# ---------------------------------------------------------------------------
# muted_creators
# ---------------------------------------------------------------------------

async def mute_creator(discord_id: int, platform: str, campaign_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO muted_creators (discord_id, platform, campaign_id)
            VALUES ($1, $2, $3)
            ON CONFLICT (discord_id, platform, campaign_id) DO NOTHING
        """, discord_id, platform, campaign_id)


async def unmute_creator(discord_id: int, platform: str, campaign_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM muted_creators
            WHERE discord_id = $1 AND platform = $2 AND campaign_id = $3
        """, discord_id, platform, campaign_id)


async def get_muted_creators(discord_id: int, platform: str = None) -> list[str]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        if platform:
            rows = await conn.fetch(
                "SELECT campaign_id FROM muted_creators WHERE discord_id = $1 AND platform = $2",
                discord_id, platform
            )
        else:
            rows = await conn.fetch(
                "SELECT campaign_id FROM muted_creators WHERE discord_id = $1", discord_id
            )
        return [r["campaign_id"] for r in rows]


async def get_muted_creators_with_platform(discord_id: int) -> list[tuple[str, str]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT platform, campaign_id FROM muted_creators WHERE discord_id = $1", discord_id
        )
        return [(r["platform"], r["campaign_id"]) for r in rows]


async def is_muted(discord_id: int, platform: str, campaign_id: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM muted_creators WHERE discord_id = $1 AND platform = $2 AND campaign_id = $3",
            discord_id, platform, campaign_id
        )
        return row is not None


# ---------------------------------------------------------------------------
# creator_channels
# ---------------------------------------------------------------------------

async def set_creator_channel(guild_id: int, channel_id: int, platform_user_id: str, platform: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO creator_channels (guild_id, channel_id, platform_user_id, platform)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (guild_id, platform_user_id, platform) DO UPDATE
            SET channel_id = $2
        """, guild_id, channel_id, platform_user_id, platform)


async def get_creator_channel(guild_id: int, platform_user_id: str, platform: str) -> int | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT channel_id FROM creator_channels WHERE guild_id = $1 AND platform_user_id = $2 AND platform = $3",
            guild_id, platform_user_id, platform
        )
        return row["channel_id"] if row else None


async def get_creator_channels_for_user(platform_user_id: str, platform: str) -> list[tuple[int, int, int | None]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT guild_id, channel_id, ping_role_id
            FROM creator_channels
            WHERE platform_user_id = $1 AND platform = $2
        """, platform_user_id, platform)
        return [(r["guild_id"], r["channel_id"], r["ping_role_id"]) for r in rows]


async def set_creator_ping_role(guild_id: int, platform_user_id: str, platform: str, role_id: int | None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE creator_channels
            SET ping_role_id = $4
            WHERE guild_id = $1 AND platform_user_id = $2 AND platform = $3
        """, guild_id, platform_user_id, platform, role_id)
