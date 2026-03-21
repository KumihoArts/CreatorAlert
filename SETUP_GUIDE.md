# CreatorAlert — Setup Guide

This guide walks you through setting up CreatorAlert as a supporter or as a creator. No technical knowledge required.

**Support server:** [discord.gg/KVcu3HvHB3](https://discord.gg/KVcu3HvHB3)
**Invite the bot:** [Click here](https://discord.com/oauth2/authorize?client_id=1483970800477409422&permissions=277025392640&scope=bot+applications.commands)

---

## For supporters — getting personal notifications

Supporters get private DM notifications whenever a creator they back on Patreon publishes something new. SubscribeStar subscriber notifications are not yet available due to an API limitation.

### Step 1 — Invite the bot or find it in a server

If you're already in a server where CreatorAlert is present, you can use it straight away. If not, use the invite link above to add it to your own server, or ask a creator to add it to theirs.

### Step 2 — Connect your account

Run `/connect` in any server where the bot is present. Choose the platform you want to connect, click the link that appears, authorise the connection on that platform's website, and your account is linked.

You can connect multiple platforms independently. Run `/connect` again to add another.

### Step 3 — You're done

That's it. CreatorAlert will check for new posts from every creator you support and send you a private DM when something is published. You don't need to do anything else.

Notifications look like this:

> **📬 New post from [Creator Name]**
> **Post title here**
>
> Post excerpt (for public posts)
>
> [Link to the post]

### Checking your status

Run `/status` at any time to see:
- Which accounts are connected and when
- Whether free member notifications are on or off
- Whether you have Premium
- How many creators you have muted, if any
- Your announcement channel and ping role (if you're a creator in this server)

### Free member notifications

By default, CreatorAlert notifies you about posts from all creators you follow on Patreon — including ones you follow for free (free tier / follower). If you only want notifications from creators you're paying to support, you can turn this off:

```
/settings platform:Patreon
```

Then click **Turn off free notifications**. You can toggle this back on at any time the same way.

### Muting a creator

Use `/mute` to stop receiving notifications from a specific creator without disconnecting your account. You'll see a dropdown of all the creators you currently support — select one to mute them.

While a creator is muted, their posts are completely skipped. If you unmute them later, you won't have missed anything — you'll still be notified about posts you didn't see while they were muted.

### Unmuting a creator

Run `/unmute` to restore notifications from a muted creator. Notifications resume at the next polling cycle.

### Disconnecting

Run `/disconnect` to unlink an account and stop all notifications from that platform. If you have multiple platforms connected, you'll be asked which one to disconnect. This also clears your muted creators for that platform.

---

## For creators — announcing posts to your Discord server

Creators can have CreatorAlert automatically announce new posts to a channel in their Discord server. Patreon, SubscribeStar, and Gumroad are all supported for creator announcements. This requires the **Manage Server** permission.

### Step 1 — Invite the bot to your server

Use the invite link at the top of this guide. Make sure to keep the default permissions — the bot needs to be able to send messages and embed links.

### Step 2 — Connect your account

Run `/connect` and choose your platform. Authorise CreatorAlert to access your account, the same as subscribers do.

> **SubscribeStar note:** Post notifications are not yet available for SubscribeStar subscribers due to an API limitation on SubscribeStar's side. Creator channel announcements will be added once the API supports it.
>
> **Gumroad note:** Gumroad is creator-only — it announces new products to a channel in your server. There are no subscriber DMs for Gumroad.

### Step 3 — Set up your announcement channel

Run `/setup #channel-name`, replacing `#channel-name` with the channel where you want new posts announced. If you have multiple platforms connected, add the `platform` option to specify which one:

```
/setup #patreon-updates platform:Patreon
/setup #new-products platform:Gumroad
```

The bot will confirm the channel is set. From this point on, whenever you publish a new post or product, CreatorAlert will automatically post an announcement in that channel.

> **Note:** Make sure the bot has permission to send messages and embed links in the channel you choose. If it doesn't, `/setup` will tell you.

### Step 4 (optional) — Set a ping role

Run `/pingrole @role-name` to ping a role with each announcement. Use the `platform` option if you have multiple platforms set up:

```
/pingrole @Patreon Updates platform:Patreon
/pingrole @New Products platform:Gumroad
```

To remove the ping role, run `/pingrole` without specifying a role.

> **Note:** `@everyone` and `@here` cannot be used as ping roles. The role must also be below the bot's own role in the server hierarchy.

### What an announcement looks like

> @Patreon Updates
> **📬 New post from [Your Creator Name]**
> **Post title here**
>
> Post excerpt (for public posts)
>
> [Link to the post]

---

## Both modes together

If you're a creator and you've set up an announcement channel, your fans can still use the bot independently to get their own private DM notifications. They just need to run `/connect` themselves. The two modes don't interfere with each other.

---

## Premium

CreatorAlert Premium is available via Discord subscription. Use `/premium` in Discord to see the details and subscribe.

Premium members get:

- **Faster polling** — posts are checked every 3 minutes instead of 10
- **Custom embed colour** — personalise the colour of your DM notification embeds
- **Custom notification message** — add your own text prepended to every notification

To customise your colour and message after subscribing, use `/customize`:

```
/customize colour:#ff6600 message:New post just dropped!
```

---

## Command reference

| Command | Who it's for | What it does |
|---|---|---|
| `/connect` | Everyone | Links a Patreon, SubscribeStar, or Gumroad account |
| `/disconnect` | Everyone | Unlinks an account and stops notifications from that platform |
| `/status` | Everyone | Shows connection status, settings, and creator channel info |
| `/settings` | Everyone | Toggles notification preferences (e.g. free member notifications) |
| `/setup` | Creators (Manage Server) | Sets the channel for automatic post announcements |
| `/pingrole` | Creators (Manage Server) | Sets a role to ping with each announcement |
| `/premium` | Everyone | Shows Premium status and subscribe button |
| `/customize` | Premium subscribers | Sets a custom embed colour and notification message |
| `/mute` | Everyone | Mutes notifications from a specific creator |
| `/unmute` | Everyone | Restores notifications from a muted creator |
| `/invite` | Everyone | Gets the bot's invite link |
| `/about` | Everyone | Shows bot info and links |
| `/help` | Everyone | Shows a summary of available commands |

---

## Troubleshooting

**I ran `/connect` but didn't get a link / nothing happened.**
Make sure your DMs are open for the server where you ran the command. In Discord, go to the server settings and enable "Allow direct messages from server members."

**I'm not receiving notifications from a creator I support.**
First check if you have them muted — run `/status` to see your mute count, or try `/unmute` to see your muted list. If they're not muted, run `/status` to confirm your account is connected. Check your `/settings` to make sure free member notifications are on if you follow this creator for free. It may also just be that the bot hasn't polled yet — it checks every 10 minutes (3 for Premium).

**I'm not receiving any notifications at all.**
Run `/status` to confirm your account is connected. If it is and you've been waiting longer than 10 minutes, join the support server and we'll take a look.

**The bot says it can't send messages in my channel.**
Go to your channel settings → Permissions and make sure CreatorAlert has `Send Messages` and `Embed Links` enabled.

**I disconnected from Patreon or SubscribeStar on their website.**
CreatorAlert will detect this automatically on the next poll and send you a DM letting you know. Just run `/connect` again to re-link.

**I connected SubscribeStar but I'm not getting notifications.**
SubscribeStar's API does not currently expose post content, so subscriber DM notifications are not available for SubscribeStar at this time. Your account is saved and notifications will be enabled automatically if this changes. Creator channel announcements are also pending this API support.

---

## Need help?

Join the [KumihoArts support server](https://discord.gg/KVcu3HvHB3) or DM **Sly** on Discord.
