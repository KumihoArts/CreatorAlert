# Privacy Notice — CreatorAlert

**Last updated:** March 2026

## 1. Who We Are
CreatorAlert is a Discord bot developed and operated by Daniël ("we", "us"). It is an independent project and is not affiliated with Patreon, Inc. or Discord, Inc.

## 2. What Data We Collect
When you use CreatorAlert, we collect and store:

| Data | Purpose |
|---|---|
| Your Discord user ID | Identifying you in our system |
| Your Patreon user ID | Linking your Patreon account |
| Patreon OAuth access & refresh tokens | Fetching your memberships and creator posts on your behalf |
| Token expiry timestamp | Refreshing your access token when needed |
| Seen post IDs | Preventing duplicate notifications |
| Guild and channel IDs (creator mode) | Knowing where to post notifications |

We do **not** collect your email address, payment details, or any message content.

## 3. How We Use Your Data
Your data is used solely to:
- Fetch Patreon content on your behalf
- Send you Discord notifications for new creator posts
- Prevent you from receiving duplicate notifications

We do not sell, share, or use your data for any advertising or profiling purpose.

## 4. Data Retention
Your data is retained as long as your account is connected. You can delete all stored data at any time by using `/disconnect`. Post IDs in the `seen_posts` table may be retained briefly after disconnection for system cleanup purposes and are then purged.

## 5. Third-Party Services
CreatorAlert uses:
- **Patreon API** — to access your membership and post data. Subject to [Patreon's Privacy Policy](https://www.patreon.com/privacy).
- **Discord API** — to send you messages and interact with servers. Subject to [Discord's Privacy Policy](https://discord.com/privacy).
- **Railway** — for hosting (database and application servers). Subject to [Railway's Privacy Policy](https://railway.app/legal/privacy).

## 6. Security
OAuth tokens are stored in a private PostgreSQL database with access restricted to the bot's own services. We take reasonable precautions to protect your data, but no system is fully secure.

## 7. Your Rights
You may request deletion of all your data at any time by:
- Using the `/disconnect` command in Discord, or
- Contacting the bot owner directly (see below)

If you are in the EU/EEA, you have rights under GDPR including access, rectification, and erasure of your personal data.

## 8. Changes
This Privacy Notice may be updated from time to time. Significant changes will be announced via the bot's support server or release notes.

## 9. Contact
For privacy-related questions or data deletion requests, contact the bot owner via Discord: **Sly** (`244962442008854540`).
