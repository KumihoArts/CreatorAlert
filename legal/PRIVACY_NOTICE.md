# Privacy Notice — CreatorAlert

**Last updated:** March 2026

## 1. Who We Are
CreatorAlert is a Discord bot developed and operated by Daniël ("we", "us"). It is an independent project and is not affiliated with Patreon, Inc. or Discord, Inc.

## 2. What Data We Collect
When you use CreatorAlert, we collect and store the following data:

| Data | Purpose |
|---|---|
| Your Discord user ID | Identifying you in our system |
| Your Patreon user ID | Linking your Patreon account |
| Patreon OAuth access & refresh tokens | Fetching your memberships and creator posts on your behalf |
| Notification preference (DM, channel, or both) | Delivering notifications in your preferred way |
| Notification channel ID | Sending notifications to your chosen channel (if applicable) |
| Seen post IDs | Preventing duplicate notifications |
| Guild and channel IDs (creator mode) | Knowing where to post creator notifications |

We do **not** collect your email address, Patreon payment details, message content, or any information beyond what is listed above.

## 3. How We Use Your Data
Your data is used solely to:
- Fetch Patreon content on your behalf
- Send you Discord notifications for new creator posts
- Respect your notification delivery preferences
- Prevent you from receiving duplicate notifications

We do not sell, share, or use your data for advertising, profiling, or any purpose other than delivering the service.

## 4. Token Refresh
CreatorAlert automatically refreshes your Patreon OAuth tokens when they expire to maintain uninterrupted service. If a token cannot be refreshed (e.g. you revoked access on Patreon's side), your data is automatically removed from our database and you will be notified via Discord DM.

## 5. Data Retention
Your data is retained for as long as your Patreon account is connected to CreatorAlert. You can delete all your stored data at any time by using the `/disconnect` command in Discord. Seen post IDs may be retained briefly for deduplication cleanup and are then purged.

## 6. Third-Party Services
CreatorAlert uses the following third-party services:
- **Patreon API** — to access your membership and post data. Subject to [Patreon's Privacy Policy](https://www.patreon.com/privacy).
- **Discord API** — to send you messages and interact with servers. Subject to [Discord's Privacy Policy](https://discord.com/privacy).
- **Railway** — for hosting (application servers and database). Subject to [Railway's Privacy Policy](https://railway.app/legal/privacy).

## 7. Security
OAuth tokens are stored in a private PostgreSQL database hosted on Railway. Access is restricted to CreatorAlert's own services. We take reasonable precautions to protect your data, but no system is entirely secure and we cannot guarantee absolute security.

## 8. Your Rights
You may request deletion of all your data at any time by:
- Using the `/disconnect` command in Discord, or
- Contacting the bot owner directly (see below)

If you are located in the EU/EEA, you have additional rights under the GDPR, including the right to access, rectify, and erase your personal data, and the right to object to or restrict processing. To exercise any of these rights, contact us using the details below.

## 9. Children's Privacy
CreatorAlert is not intended for use by anyone under the age of 13. We do not knowingly collect data from children under 13.

## 10. Changes
This Privacy Notice may be updated from time to time. Significant changes will be communicated via the bot's support server or release notes. The "Last updated" date at the top reflects the most recent revision.

## 11. Contact
For privacy-related questions, data deletion requests, or to exercise your GDPR rights, contact the bot owner via Discord: **Sly** (`244962442008854540`).
