/**
 * Lisa's Assets — Scorecard Renderer
 * Builds score tables and subnet cards from JSON data.
 */
const Renderer = (() => {
  const AGENT_KEYS = ['emission', 'economics', 'code', 'hype', 'oracle', 'stakeflow', 'risk'];
  const AGENT_LABELS = { emission: 'Emission', economics: 'Economics', code: 'Code', hype: 'Hype', oracle: 'Oracle', stakeflow: 'StakeFlow', risk: 'Risk' };
  const AGENT_EMOJIS = { emission: '🧮', economics: '📊', code: '👨‍💻', hype: '🔥', oracle: '🔍', stakeflow: '💧', risk: '⚠️' };

  function lisaCoefficient(subnet, weights) {
    const s = subnet.scores;
    return (
      s.emission * weights.emission +
      s.economics * weights.economics +
      s.code * weights.code +
      s.hype * weights.hype +
      s.oracle * weights.oracle +
      s.stakeflow * weights.stakeflow +
      s.risk * weights.risk
    );
  }

  function verdict(score, verdicts) {
    if (score >= 8.0) return verdicts.strong_hold;
    if (score >= 6.0) return verdicts.research;
    if (score >= 4.0) return verdicts.watch;
    if (score >= 2.0) return verdicts.caution;
    return verdicts.avoid;
  }

  function scoreClass(coef) {
    if (coef >= 8.0) return 'score-high';
    if (coef >= 6.0) return 'score-mid';
    if (coef >= 4.0) return 'score-low';
    return 'score-bad';
  }

  /**
   * Render the full score summary table.
   */
  function renderScoreTable(subnets, weights, verdicts) {
    const visible = subnets.filter(s => !s.hidden);
    const rows = visible.map(s => {
      const coef = lisaCoefficient(s, weights);
      const v = verdict(coef, verdicts);
      const id = 'sn' + s.netuid;
      const star = s.details.featured ? ' ⭐' : '';
      return `<tr onclick="Router.showProject('${id}')">
        <td>${s.details.rank}</td>
        <td>SN${s.netuid}</td>
        <td>${s.name}${star}</td>
        ${AGENT_KEYS.map(k => `<td>${s.scores[k]}</td>`).join('')}
        <td><span class="score-badge ${scoreClass(coef)}">${coef.toFixed(1)}</span></td>
        <td><span class="verdict verdict-${v.color}">${v.icon} ${v.label}</span></td>
      </tr>`;
    }).join('');

    return `<div class="table-wrap"><table class="score-table">
      <thead><tr><th>Rank</th><th>Subnet</th><th>Name</th>
        <th>🧮</th><th>📊</th><th>👨‍💻</th><th>🔥</th><th>🔍</th><th>💧</th><th>⚠️</th>
        <th>Lisa C</th><th>Verdict</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>`;
  }

  /**
   * Render a single subnet scorecard.
   */
  function renderSubnetCard(subnet, weights, verdicts) {
    const coef = lisaCoefficient(subnet, weights);
    const v = verdict(coef, verdicts);
    const id = 'sn' + subnet.netuid;
    const bull = subnet.bull_case.map(x => `<li>${x}</li>`).join('');
    const bear = (subnet.bear_case || []).map(x => `<li>${x}</li>`).join('');
    const gradients = {
      green: 'linear-gradient(135deg, var(--accent-glow), rgba(34,197,94,0.04))',
      blue: 'linear-gradient(135deg, var(--accent-glow), rgba(59,130,246,0.04))'
    };

    return `<div class="subnet-card" id="card-${id}">
      <div class="subnet-header" style="background: ${gradients[v.color] || 'none'}">
        <div>
          <h2>SN${subnet.netuid} — ${subnet.name}</h2>
          <div class="subtitle">${subnet.category}${subnet.website ? ' · ' + subnet.website : ''}</div>
        </div>
        <div style="text-align:right;">
          <div class="score-display" style="color:var(--${v.color});">${coef.toFixed(1)}</div>
          <div class="score-max">/ 10 — ${v.icon} ${v.label}</div>
        </div>
      </div>
      <div class="subnet-body">
        <div class="agent-grid">
          ${AGENT_KEYS.map(k => `<div class="agent-cell"><div class="emoji">${AGENT_EMOJIS[k]}</div><div class="agent-name">${AGENT_LABELS[k]}</div><div class="agent-score">${subnet.scores[k]}</div></div>`).join('')}
        </div>
        <div class="analyst-section"><h3>🔍 Oracle Analysis</h3><p>${subnet.description}</p></div>
        ${bull ? `<div class="bull-bear">
          <div class="bull-box"><h4>Bull Case</h4><ul>${bull}</ul></div>
          ${bear ? `<div class="bear-box"><h4>Bear Case</h4><ul>${bear}</ul></div>` : ''}
        </div>` : ''}
      </div>
    </div>`;
  }

  /**
   * Render all subnet cards for the TAO page.
   */
  function renderSubnetCards(subnets, weights, verdicts) {
    const visible = subnets.filter(s => !s.hidden);
    const cards = visible.map(s => renderSubnetCard(s, weights, verdicts)).join('');
    const hidden = subnets.filter(s => s.hidden);
    const hiddenSummary = hidden.length ? `
      <details>
        <summary>🔴 Low-Scoring Subnets (${hidden.length})</summary>
        <div style="padding:1rem;background:var(--card);border:1px solid var(--border);border-top:none;border-radius:0 0 12px 12px;">
          ${hidden.map(s => `<p style="font-size:0.82rem;color:var(--muted);margin-bottom:0.5rem;"><strong>SN${s.netuid} ${s.name}</strong> — ${s.description}</p>`).join('')}
        </div>
      </details>` : '';
    return cards + hiddenSummary;
  }

  return { renderScoreTable, renderSubnetCard, renderSubnetCards, lisaCoefficient, verdict, scoreClass };
})();
