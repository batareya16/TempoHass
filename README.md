# Tempo Worklog for Home Assistant

Tracks your daily work time logging in [Tempo](https://tempo.io) (Jira) and shows a weekly status card in Home Assistant.

- ✅ Green dot = ≥ 4 hours logged that day
- 🔴 Red ring = today, not enough hours yet
- Shows partial hours inside the dot if something is logged but below threshold

---

## Installation via HACS

1. In HACS → Integrations → ⋮ → Custom repositories
2. Add `https://github.com/<your-username>/tempo-worklog-ha` as type **Integration**
3. Install "Tempo Worklog"
4. Restart Home Assistant

### Manual install

Copy `custom_components/tempo_worklog/` into your HA `custom_components/` folder and restart.

---

## Configuration

Add to `configuration.yaml`:

```yaml
sensor:
  - platform: tempo_worklog
    api_token: !secret tempo_api_token
    min_hours: 4        # optional, default 4
    name: "Work Time"   # optional
```

Add to `secrets.yaml`:

```yaml
tempo_api_token: "your_tempo_api_token_here"
```

Get your token: **Tempo → Settings → API Integration → New Token**

---

## Lovelace card

Copy `www/tempo-worklog-card.js` to your HA `www/` folder, then add as a resource:

```yaml
# configuration.yaml or via UI: Settings → Dashboards → Resources
lovelace:
  resources:
    - url: /local/tempo-worklog-card.js
      type: module
```

Add the card to your dashboard:

```yaml
type: custom:tempo-worklog-card
entity: sensor.tempo_worklog_today
name: Work Time     # optional
min_hours: 4        # optional, overrides sensor default
```

---

## Sensor attributes

| Attribute | Description |
|---|---|
| `week_days` | List of Mon–Fri with `date`, `day_name`, `hours`, `logged`, `is_today`, `is_future` |
| `today_logged` | `true` if today meets the threshold |
| `days_logged_this_week` | Count of logged days so far this week |
| `min_hours` | Configured threshold |
| `week_start_date` | ISO date of Monday |

The sensor state is today's total logged hours (float).
