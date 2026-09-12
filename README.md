# HA Mains Alert

A Home Assistant add-on that detects mains failure and restoration and sends notifications to multiple Companion App devices.

## Install

1. In Home Assistant, open **Settings → Add-ons → Add-on Store**.
2. Open the three-dot menu, choose **Repositories**, and add this repository URL.
3. Install **Mains Power Alert**, start it, then enable **Start on boot** and **Watchdog**.
4. Open its Web UI. Choose the grid/mains entity and the mobile notification targets.
5. Use **Send test alert**, then save and enable monitoring.

The recommended default is voltage-based detection: outage below 50 V for 15 seconds, restored above 180 V for 10 seconds. Adjust these values to suit the selected entity.

## Support

The Web UI includes live state and attributes, an event log, and a sanitized **Copy diagnostics** report suitable for pasting into ChatGPT or a GitHub issue.

