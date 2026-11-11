# 6. Slack alerts

[◀ Put it in the toilet](05-into-the-tank.md) · Next: [Going further ▶](07-going-further.md)

Because your team should be aware. Every counted flush posts one message:

> 🚽 **FLUSH!** The toilet just flushed at 3:07 PM.
> That's the 3rd flush today (41 all time).

Sloshing never posts, and neither does the first reading after the Pi boots. If Slack is down or slow, the watcher keeps counting anyway.

Is this an HR nightmare? Maybe. Pick your battles.

## Step 1: make an incoming webhook

An incoming webhook can only post to the one channel you pick, which makes it the safest way to do this.

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and click **Create New App** → **From scratch**.
2. Name it something like `Flush Control`, pick your workspace, click **Create App**.
3. In the left menu, click **Incoming Webhooks** and switch **Activate Incoming Webhooks** on.
4. Click **Add New Webhook** (at the bottom), pick the channel, and click **Allow**.
5. Copy the webhook URL. It starts with `https://hooks.slack.com/services/`.

Treat that URL like a password. Anyone who has it can post to your channel.

## Step 2: give it to the Pi

```bash
sudo nano /etc/default/toilet-watch
```

Paste it after `TOILET_SLACK_WEBHOOK_URL=`:

```
TOILET_SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T000/B000/XXXX
```

Save (`Ctrl+O`, `Enter`, `Ctrl+X`). The installer already locked this file so only root can read it.

## Step 3: test it, then go live

```bash
sudo bash ~/toilet-monitor-guide/pi/slack-test.sh
```

A test message shows up in your channel. Then restart the watcher so it picks up the setting:

```bash
sudo systemctl restart toilet-watch
sleep 3; journalctl -u toilet-watch -n 3 -o cat
```

```
toilet-watch: GPIO17, full when open, slack webhook
```

Now go flush.

## Already have a Slack bot?

You can use a bot token instead of a webhook. Leave the webhook blank and set both of these. The bot has to be a member of that channel.

```
TOILET_SLACK_BOT_TOKEN=xoxb-...
TOILET_SLACK_CHANNEL=C0123456789
```
