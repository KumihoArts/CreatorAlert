# CreatorAlert — Setup Guide

This guide walks you through setting up CreatorAlert as a supporter or as a creator. No technical knowledge required.

**Support server:** [discord.gg/KVcu3HvHB3](https://discord.gg/KVcu3HvHB3)
**Invite the bot:** [Click here](https://discord.com/oauth2/authorize?client_id=1483970800477409422&permissions=277025392640&scope=bot+applications.commands)

---

## For supporters — getting personal notifications

Supporters get private DM notifications whenever a creator they back on Patreon publishes something new.

### Step 1 — Invite the bot or find it in a server

If you're already in a server where CreatorAlert is present, you can use it straight away. If not, use the invite link above to add it to your own server, or ask a creator to add it to theirs.

### Step 2 — Connect your Patreon account

Run `/connect` in any server where the bot is present. You'll get a private message with a link — click it, and you'll be taken to Patreon to authorise the connection. Once you approve, your account is linked.

### Step 3 — You're done

That's it. CreatorAlert will check for new posts from every creator you support on Patreon and send you a private DM when something is published. You don't need to do anything else.

Notifications arrive as a DM from the bot and look like this:

> **📬 New post from [Creator Name]**
> **Post title here**
> [Link to the post]

### Checking your status

Run `/status` at any time to see:
- Which Patreon account is connected
- When you connected
- Whether you have Premium

### Disconnecting

Run `/disconnect` if you want to unlink your account and stop notifications. You'll be asked to confirm before anything is deleted.

---

## For creators — announcing posts to your Discord server

Creators can have CreatorAlert automatically announce new Patreon posts to a channel in their Discord server. This requires the **Manage Server** permission.

### Step 1 — Invite the bot to your server

Use the invite link at the top of this guide. Make sure to keep the default permissions — the bot needs to be able to send messages and embed links.

### Step 2 — Connect your Patreon account

Run `/connect` and authorise CreatorAlert to access your Patreon account, the same as subscribers do.

### Step 3 — Set up your announcement channel

Run `/setup #channel-name`, replacing `#channel-name` with the channel where you want new posts to be announced. For example:

```
/setup #patreon-updates
```

The bot will confirm the channel is set. From this point on, whenever you publish a new post on Patreon, CreatorAlert will automatically post an announcement in that channel.

> **Note:** Make sure the bot has permission to send messages and embed links in the channel you choose. If it doesn't, `/setup` will tell you.

### Step 4 (optional) — Set a ping role

If you want a specific role to be pinged with each announcement, run `/pingrole @role-name`. For example, if you have a role called `@Patreon Updates`:

```
/pingrole @Patreon Updates
```

Every announcement will then ping that role. To remove the ping role later, run `/pingrole` without specifying a role.

> **Note:** `@everyone` and `@here` cannot be used as ping roles. The role must also be below the bot's own role in the server's role hierarchy.

### What an announcement looks like

When you publish a new post on Patreon, the bot will post something like this in your designated channel:

> @Patreon Updates
> **📬 New post from [Your Creator Name]**
> **Post title here**
> [Link to the post]

---

## Both modes together

If you're a creator and you've set up an announcement channel, your fans can still use the bot independently to get their own private DM notifications — for your content or any other creator they support. They just need to run `/connect` themselves. The two modes don't interfere with each other.

---

## Premium

CreatorAlert Premium is available via Discord subscription. Use `/premium` in Discord to see the details and subscribe.

Premium members get:

- **Faster polling** — posts are checked every 3 minutes instead of 10, so you hear about new posts sooner
- **Custom embed colour** — personalise the colour of your DM notification embeds
- **Custom notification message** — add your own text that gets prepended to every notification

To customise your colour and message after subscribing, use `/customize`. For example:

```
/customize colour:#ff6600 message:New post just dropped!
```

---

## Command reference

| Command | Who it's for | What it does |
|---|---|---|
| `/connect` | Everyone | Links your Patreon account to CreatorAlert |
| `/disconnect` | Everyone | Unlinks your account and stops all notifications |
| `/status` | Everyone | Shows your connection status and settings |
| `/setup` | Creators (Manage Server) | Sets the channel for automatic post announcements |
| `/pingrole` | Creators (Manage Server) | Sets a role to ping with each announcement |
| `/premium` | Everyone | Shows Premium status and subscribe button |
| `/customize` | Premium subscribers | Sets a custom embed colour and notification message |
| `/invite` | Everyone | Gets the bot's invite link |
| `/about` | Everyone | Shows bot info and links |
| `/help` | Everyone | Shows a summary of available commands |

---

## Troubleshooting

**I ran `/connect` but didn't get a DM.**
Make sure your DMs are open for the server where you ran the command. In Discord, go to the server settings and enable "Allow direct messages from server members."

**I'm not receiving notifications.**
Run `/status` to confirm your account is connected. If it is, the bot may have just checked recently — it polls every 10 minutes (3 for Premium). If you've been waiting longer than that, join the support server and we'll take a look.

**The bot says it can't send messages in my channel.**
Go to your channel settings → Permissions and make sure CreatorAlert has `Send Messages` and `Embed Links` enabled.

**I disconnected from Patreon on the Patreon website.**
CreatorAlert will detect this automatically on the next poll and send you a DM letting you know. Just run `/connect` again to re-link.

---

## Need help?

Join the [KumihoArts support server](https://discord.gg/KVcu3HvHB3) or DM **Sly** on Discord.
