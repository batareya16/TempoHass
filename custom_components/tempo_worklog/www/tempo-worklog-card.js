class TempoWorklogCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._expanded = false;
  }

  setConfig(config) {
    if (!config.entity) throw new Error("entity required");
    this.config = config;
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() { return 4; }

  _render() {
    const state = this._hass.states[this.config.entity];
    if (!state) {
      this.shadowRoot.innerHTML = `<ha-card><div style="padding:16px;color:var(--secondary-text-color)">Entity not found: ${this.config.entity}</div></ha-card>`;
      return;
    }

    const attrs = state.attributes;
    const todayHours   = parseFloat(state.state) || 0;
    const todayLogged  = attrs.today_logged === true;
    const minHours     = attrs.min_hours || 4;
    const streak       = attrs.streak || 0;
    const weekDays     = Array.isArray(attrs.week_days) ? attrs.week_days : [];
    const daysWeek     = attrs.days_logged_this_week || 0;
    const monthHours   = attrs.month_hours || 0;
    const monthReq     = attrs.month_required_hours || 0;
    const issues       = Array.isArray(attrs.month_issues) ? attrs.month_issues : [];
    const name         = this.config.name || "Work Time";

    // Streak badge
    const streakBadge = streak > 0
      ? `<span class="streak">${streak}-day streak 🔥</span>`
      : `<span class="streak muted">No streak yet</span>`;

    // Today status chip
    const todayChip = todayLogged
      ? `<span class="chip green">Logged ✓</span>`
      : `<span class="chip red">${Math.max(0, minHours - todayHours).toFixed(1)}h to go</span>`;

    // Week dots
    const dots = weekDays.map(({ day_name, hours, logged, is_today, is_future }) => {
      let bg, border, inner;
      if (is_future) {
        bg = "transparent";
        border = "0.5px solid var(--divider-color)";
        inner = "";
      } else if (logged) {
        bg = "#97C459";
        border = is_today ? "2px solid #639922" : "none";
        inner = `<svg width="12" height="12" viewBox="0 0 12 12" style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%)">
          <polyline points="2,6 5,9 10,3" fill="none" stroke="#27500A" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>`;
      } else {
        bg = "var(--primary-background-color)";
        border = is_today ? "2px solid var(--error-color,#db4437)" : "0.5px solid var(--divider-color)";
        inner = hours > 0
          ? `<span style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-size:8px;font-weight:600;color:var(--secondary-text-color)">${hours}h</span>`
          : "";
      }
      return `<div style="text-align:center;flex:1">
        <div style="position:relative;width:30px;height:30px;border-radius:50%;background:${bg};border:${border};margin:0 auto 4px">${inner}</div>
        <div style="font-size:9px;color:var(--secondary-text-color);${is_today ? "font-weight:600" : ""}">${day_name}</div>
      </div>`;
    }).join("");

    // Month progress bar
    const monthPct = monthReq > 0 ? Math.min(100, (monthHours / monthReq) * 100) : 0;
    const monthBarColor = monthPct >= 100 ? "#97C459" : monthHours > 0 ? "#f5a623" : "var(--divider-color)";

    // Issues list
    const expanded = this._expanded;
    const visibleIssues = expanded ? issues : issues.slice(0, 5);
    const issueRows = visibleIssues.map(({ key, hours, description }) => {
      const label = description ? `<span class="issue-desc">${description}</span>` : "";
      return `<div class="issue-row">
        <span class="issue-key">${key}</span>
        ${label}
        <span class="issue-hours">${hours}h</span>
      </div>`;
    }).join("");

    const toggleBtn = issues.length > 5
      ? `<div class="toggle-btn" id="toggle">${expanded ? "▲ Show less" : `▼ Show all ${issues.length}`}</div>`
      : "";

    const issuesSection = issues.length > 0
      ? `<div class="section-title">This month's tasks</div>
         <div class="issues">${issueRows}${toggleBtn}</div>`
      : "";

    this.shadowRoot.innerHTML = `
<style>
  :host { display:block; }
  ha-card { padding:14px 16px; }
  .header { display:flex; align-items:center; justify-content:space-between; margin-bottom:10px; }
  .title  { font-size:15px; font-weight:500; color:var(--primary-text-color); display:flex; align-items:center; gap:6px; }
  .streak { font-size:12px; font-weight:500; color:#639922; }
  .streak.muted { color:var(--secondary-text-color); font-weight:400; }
  .chip   { font-size:11px; font-weight:500; padding:2px 8px; border-radius:10px; }
  .chip.green { background:#e8f5e9; color:#639922; }
  .chip.red   { background:#fdecea; color:var(--error-color,#db4437); }
  .dots-row   { display:flex; gap:4px; margin-bottom:10px; }
  .month-row  { display:flex; align-items:center; gap:8px; margin-bottom:10px; }
  .month-label { font-size:11px; color:var(--secondary-text-color); white-space:nowrap; }
  .month-hours { font-size:11px; font-weight:500; color:var(--primary-text-color); white-space:nowrap; }
  .bar-wrap    { flex:1; background:var(--primary-background-color); border-radius:4px; overflow:hidden; height:6px; }
  .bar         { height:6px; border-radius:4px; background:${monthBarColor}; width:${monthPct}%; transition:width .4s; }
  .stats       { display:grid; grid-template-columns:1fr 1fr; gap:7px; margin-bottom:10px; }
  .stat        { background:var(--primary-background-color); border-radius:8px; padding:7px 10px; }
  .stat-l      { font-size:10px; color:var(--secondary-text-color); margin-bottom:2px; }
  .stat-v      { font-size:15px; font-weight:500; color:var(--primary-text-color); }
  .section-title { font-size:10px; color:var(--secondary-text-color); text-transform:uppercase; letter-spacing:.5px; margin-bottom:6px; }
  .issues      { display:flex; flex-direction:column; gap:4px; }
  .issue-row   { display:flex; align-items:center; gap:6px; font-size:12px; padding:4px 0; border-bottom:0.5px solid var(--divider-color); }
  .issue-key   { font-weight:600; color:var(--primary-text-color); min-width:70px; font-size:11px; }
  .issue-desc  { flex:1; color:var(--secondary-text-color); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .issue-hours { color:var(--primary-text-color); font-weight:500; white-space:nowrap; }
  .toggle-btn  { font-size:11px; color:var(--primary-color); cursor:pointer; padding-top:6px; text-align:center; }
</style>
<ha-card>
  <div class="header">
    <div class="title">
      <ha-icon icon="mdi:briefcase-clock-outline" style="--mdc-icon-size:18px"></ha-icon>
      ${name}
    </div>
    ${streakBadge}
  </div>

  <div class="dots-row">${dots}</div>

  <div class="month-row">
    <span class="month-label">Month</span>
    <div class="bar-wrap"><div class="bar"></div></div>
    <span class="month-hours">${monthHours} / ${monthReq}h</span>
  </div>

  <div class="stats">
    <div class="stat">
      <div class="stat-l">Today</div>
      <div class="stat-v">${todayHours}h ${todayChip}</div>
    </div>
    <div class="stat">
      <div class="stat-l">This week</div>
      <div class="stat-v">${daysWeek} <span style="font-size:11px;color:var(--secondary-text-color);font-weight:400">/ 5 days</span></div>
    </div>
  </div>

  ${issuesSection}
</ha-card>`;

    // Wire up expand toggle
    const btn = this.shadowRoot.getElementById("toggle");
    if (btn) {
      btn.addEventListener("click", () => {
        this._expanded = !this._expanded;
        this._render();
      });
    }
  }
}

customElements.define("tempo-worklog-card", TempoWorklogCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "tempo-worklog-card",
  name: "Tempo Worklog Card",
  description: "Work time logging tracker with streak, monthly progress and issue list",
});
