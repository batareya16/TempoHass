class TempoWorklogCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {
    if (!config.entity) throw new Error("entity required (sensor.tempo_worklog_today)");
    this.config = config;
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() { return 3; }

  _render() {
    const state = this._hass.states[this.config.entity];
    if (!state) {
      this.shadowRoot.innerHTML = `<ha-card><div style="padding:16px;color:var(--secondary-text-color)">Entity not found: ${this.config.entity}</div></ha-card>`;
      return;
    }

    const attrs = state.attributes;
    const todayHours = parseFloat(state.state) || 0;
    const todayLogged = attrs.today_logged === true;
    const minHours = attrs.min_hours || this.config.min_hours || 4;
    const daysLogged = attrs.days_logged_this_week || 0;
    const weekDays = Array.isArray(attrs.week_days) ? attrs.week_days : [];
    const name = this.config.name || "Work Time";

    // Status badge
    let badge;
    if (todayLogged) {
      badge = `<span style="font-size:12px;font-weight:500;color:#639922">Залогано ✓</span>`;
    } else {
      const remaining = Math.max(0, minHours - todayHours);
      badge = `<span style="font-size:12px;color:var(--error-color,#db4437)">Осталось ${remaining.toFixed(1)}ч</span>`;
    }

    // Day dots (Mon–Fri)
    const dots = weekDays.map((day) => {
      const { day_name, hours, logged, is_today, is_future } = day;

      let bg, border, innerContent;

      if (is_future) {
        // Future day — muted empty circle
        bg = "transparent";
        border = "0.5px solid var(--divider-color)";
        innerContent = "";
      } else if (logged) {
        bg = "#97C459";
        border = is_today ? "2px solid #639922" : "none";
        innerContent = `<svg width="12" height="12" viewBox="0 0 12 12" style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%)">
          <polyline points="2,6 5,9 10,3" fill="none" stroke="#27500A" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>`;
      } else {
        // Past or today, not enough hours logged
        bg = "var(--primary-background-color)";
        border = is_today
          ? "2px solid var(--error-color,#db4437)"
          : "0.5px solid var(--divider-color)";
        // Show partial fill or just empty
        innerContent = hours > 0
          ? `<span style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-size:8px;font-weight:600;color:var(--secondary-text-color)">${hours}h</span>`
          : "";
      }

      return `<div style="text-align:center;flex:1">
        <div style="position:relative;width:30px;height:30px;border-radius:50%;background:${bg};border:${border};margin:0 auto 4px">
          ${innerContent}
        </div>
        <div style="font-size:9px;color:var(--secondary-text-color);${is_today ? "font-weight:600" : ""}">${day_name}</div>
      </div>`;
    }).join("");

    // Progress bar for today
    const pct = Math.min(100, (todayHours / minHours) * 100);
    const barColor = todayLogged ? "#97C459" : (todayHours > 0 ? "#f5a623" : "var(--divider-color)");

    this.shadowRoot.innerHTML = `
<style>
  :host { display: block; }
  ha-card { padding: 14px 16px; }
  .header { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
  .title  { font-size:15px; font-weight:500; color:var(--primary-text-color); display:flex; align-items:center; gap:6px; }
  .stats  { display:grid; grid-template-columns:1fr 1fr; gap:7px; margin-top:12px; }
  .stat   { background:var(--primary-background-color); border-radius:8px; padding:7px 10px; }
  .stat-l { font-size:10px; color:var(--secondary-text-color); margin-bottom:1px; }
  .stat-v { font-size:15px; font-weight:500; color:var(--primary-text-color); }
  .stat-s { font-size:11px; color:var(--secondary-text-color); font-weight:400; }
  .progress-wrap { margin-top:10px; background:var(--primary-background-color); border-radius:4px; overflow:hidden; height:4px; }
  .progress-bar  { height:4px; border-radius:4px; transition:width 0.4s; background:${barColor}; width:${pct}%; }
</style>
<ha-card>
  <div class="header">
    <div class="title">
      <ha-icon icon="mdi:briefcase-clock-outline" style="--mdc-icon-size:18px;color:var(--primary-text-color)"></ha-icon>
      ${name}
    </div>
    ${badge}
  </div>

  <div style="display:flex;gap:4px">${dots}</div>

  <div class="progress-wrap">
    <div class="progress-bar"></div>
  </div>

  <div class="stats">
    <div class="stat">
      <div class="stat-l">сегодня</div>
      <div class="stat-v">${todayHours.toFixed(1)} <span class="stat-s">/ ${minHours}ч</span></div>
    </div>
    <div class="stat">
      <div class="stat-l">эта неделя</div>
      <div class="stat-v">${daysLogged} <span class="stat-s">/ 5 дней</span></div>
    </div>
  </div>
</ha-card>`;
  }
}

customElements.define("tempo-worklog-card", TempoWorklogCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "tempo-worklog-card",
  name: "Tempo Worklog Card",
  description: "Shows daily work time logging status from Tempo (Mon–Fri, configurable min hours)",
});
