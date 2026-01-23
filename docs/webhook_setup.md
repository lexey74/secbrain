# Webhook setup for SecBrain Telegram Bot

This document explains how to switch the bot to webhook mode, obtain TLS certificates using Let's Encrypt (certbot), and configure Nginx to proxy requests to the local bot.

Summary:
- Bot will run in webhook mode and listen on a local port (default: `127.0.0.1:8080`).
- Nginx terminates TLS on `example.com` and forwards requests to the local bot.
- Telegram sends updates to `https://example.com/<url_path>`; the bot uses `run_webhook` and `setWebhook` automatically.

## 1) Environment variables
Add the following variables to your `.env` (or systemd EnvironmentFile):

```
WEBHOOK_MODE=true
WEBHOOK_LISTEN=127.0.0.1
WEBHOOK_PORT=8080
# Public URL where Telegram will post updates (https://your.domain)
WEBHOOK_PUBLIC_URL=https://example.com
# Path on your domain for webhook (recommended to keep secret-like)
WEBHOOK_PATH=bot_abcd1234
# Optional secret token for additional header verification
WEBHOOK_SECRET_TOKEN=<random-secret-string>
```

- `WEBHOOK_PUBLIC_URL` must be HTTPS. If you plan to use the same host for MCP, configure different paths.
- `WEBHOOK_SECRET_TOKEN` causes Telegram to include the header `X-Telegram-Bot-Api-Secret-Token` with the provided value; the bot will receive it in the request headers via the `secret_token` param.

## 2) Obtain TLS certificate (Let's Encrypt)
Install certbot and request a certificate for your domain (adjust package manager if not Debian/Ubuntu):

```bash
sudo apt update
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d example.com
```

This will configure Nginx automatically and put certificates in `/etc/letsencrypt/live/example.com/`.

If you prefer manual mode (for a Docker host or special setup):
```bash
sudo certbot certonly --standalone -d example.com
```

## 3) Nginx configuration
Use the provided snippet `scripts/nginx_bot.conf` as a basis. Place it under `/etc/nginx/sites-available/secbrain` and symlink to `sites-enabled`:

```bash
sudo cp scripts/nginx_bot.conf /etc/nginx/sites-available/secbrain
sudo ln -s /etc/nginx/sites-available/secbrain /etc/nginx/sites-enabled/secbrain
sudo nginx -t
sudo systemctl reload nginx
```

Notes:
- `proxy_pass` points to `http://127.0.0.1:8080` by default — make sure `WEBHOOK_LISTEN`/`WEBHOOK_PORT` in `.env` match this.
- Forwarded header `X-Telegram-Bot-Api-Secret-Token` is set so Telegram secret token is preserved.

## 4) systemd service
A sample unit `scripts/secbrain-bot.service` is provided. Install it with:

```bash
sudo cp scripts/secbrain-bot.service /etc/systemd/system/secbrain-bot.service
sudo systemctl daemon-reload
sudo systemctl enable --now secbrain-bot.service
sudo journalctl -u secbrain-bot -f
```

The unit uses `/home/lexey/projects/secbrain/.env` as `EnvironmentFile` — adjust path and `User` if needed.

## 5) Verify webhook
After the bot starts, it will call `setWebhook` automatically using the `WEBHOOK_PUBLIC_URL` and `WEBHOOK_PATH` environment variables.

You can verify with:

```bash
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo" | jq .
```

Look for `url` and `last_error_message` fields. If you see `last_error_message`, check `logs/bot.log` for details.

## Troubleshooting
- If `setWebhook` fails with 409 Conflict, it means another webhook is set for the bot token. Use `deleteWebhook` first:

```bash
curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/deleteWebhook"
```

- If Nginx returns 502 bad gateway, check that the bot process is listening on the expected local port and that `proxy_pass` matches.
- If you rely on the `X-Telegram-Bot-Api-Secret-Token`, ensure the value in `.env` matches the header used by Telegram.

---
If you want, I can:
- generate a recommended random `WEBHOOK_SECRET_TOKEN` and add it to `.env` for you,
- prepare the exact nginx config with your real domain (if you provide it),
- install and run certbot (requires sudo) — I can provide the commands to run locally.
