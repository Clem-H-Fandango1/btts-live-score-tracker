BTTS App (DEV) — Telegram Notify Page (v1.1.2-dev, fixed APP_VERSION)
====================================================================

Deploy (DEV, port 8194)
-----------------------
Run these on your server:

    cd /root/btts_tracker

    # nuke old dev container & image
    docker rm -f btts_app_dev 2>/dev/null || true
    docker image rm -f btts_app_dev_image 2>/dev/null || true

    # unzip into dev folder
    unzip -o btts_app_final_bet365_v1.1.2_dev_notify_fix.zip -d btts_app_dev
    cd btts_app_dev

    # build & run
    docker build --no-cache -t btts_app_dev_image .
    docker run -d       --name btts_app_dev       -p 8194:8094       -v $(pwd)/assignments.json:/app/assignments.json       --restart unless-stopped       btts_app_dev_image

Now open: http://<your-host>:8194/notify

Notes
-----
- Fill in your Bot Token and Chat ID, click Save. Values are written to settings.json.
- Restart the container to let the notifier pick up any new values.

Test Notification
-----------------
1) Go to http://<your-host>:8194/notify
2) Paste your Bot Token and Chat ID and click "Save Telegram Settings"
3) Click "Send Test Notification" (optionally edit the text) — you should receive a message in your Telegram group.

v1.1.4-dev additions
--------------------
- Test endpoint now also reads settings.json directly if env is empty, so tests work immediately after saving.
- New /telegram_status endpoint + status panel on /notify to see what the server currently detects.
  (Token is masked in the UI for safety.)
