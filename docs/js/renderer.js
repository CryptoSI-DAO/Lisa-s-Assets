/**
 * Lisa's Assets — Scorecard Renderer
 * Builds score tables and project cards from JSON data.
 * Supports both TAO subnet data and ETH/HYPE ecosystem data.
 */
const Renderer = (() => {
  const AGENT_KEYS = ['truthSeeker', 'mavenMetrics', 'liquidEdge', 'tokenLogic', 'hypePulse', 'codeCrafter', 'riskEye'];
  const AGENT_LABELS = { truthSeeker: 'TruthSeeker', mavenMetrics: 'MavenMetrics', liquidEdge: 'LiquidEdge', tokenLogic: 'TokenLogic', hypePulse: 'HypePulse', codeCrafter: 'CodeCrafter', riskEye: 'RiskEye' };
  const AGENT_EMOJIS = { truthSeeker: '🔍', mavenMetrics: '🧮', liquidEdge: '💧', tokenLogic: '📊', hypePulse: '🔥', codeCrafter: '👨‍💻', riskEye: '⚠️' };

  const TAO_AGENT_KEYS = ['emission', 'economics', 'code', 'hype', 'oracle', 'stakeflow', 'risk'];
  const TAO_AGENT_LABELS = { emission: 'Emission', economics: 'Economics', code: 'Code', hype: 'Hype', oracle: 'Oracle', stakeflow: 'StakeFlow', risk: 'Risk' };
  const TAO_AGENT_EMOJIS = { emission: '🧮', economics: '📊', code: '👨‍💻', hype: '🔥', oracle: '🔍', stakeflow: '💧', risk: '⚠️' };

  function lisaCoefficient(item, weights, agentKeys) {
    const s = item.scores;
    return agentKeys.reduce((sum, k) => sum + (s[k] || 0) * (weights[k] || 0), 0);
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
   * Render the TAO score summary table.
   */
  function renderScoreTable(subnets, weights, verdicts) {
    const visible = subnets.filter(s => !s.hidden);
    const rows = visible.map(s => {
      const coef = lisaCoefficient(s, weights, TAO_AGENT_KEYS);
      const v = verdict(coef, verdicts);
      const id = 'sn' + s.netuid;
      const star = s.details && s.details.featured ? ' ⭐' : '';
      return `<tr onclick="Router.showProject('${id}')">
        <td>${s.details ? s.details.rank : '-'}</td>
        <td>SN${s.netuid}</td>
        <td>${s.name}${star}</td>
        ${TAO_AGENT_KEYS.map(k => `<td>${s.scores[k]}</td>`).join('')}
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
   * Render a single TAO subnet scorecard.
   */
  function renderSubnetCard(subnet, weights, verdicts) {
    const coef = lisaCoefficient(subnet, weights, TAO_AGENT_KEYS);
    const v = verdict(coef, verdicts);
    const id = 'sn' + subnet.netuid;
    const bull = (subnet.bull_case || []).map(x => `<li>${x}</li>`).join('');
    const bear = (subnet.bear_case || []).map(x => `<li>${x}</li>`).join('');
    const gradients = {
      green: 'linear-gradient(135deg, var(--accent-glow), rgba(34,197,94,0.04))',
      blue: 'linear-gradient(135deg, var(--accent-glow), rgba(59,130,246,0.04))'
    };

    return `<div class="subnet-card" id="card-${id}">
      <div class="subnet-header" style="background: ${gradients[v.color] || 'none'}">
        <div>
          <h2>SN${subnet.netuid} — ${subnet.name}</h2>
          <div class="subtitle">${subnet.category || ''}${subnet.website ? ' · ' + subnet.website : ''}</div>
        </div>
        <div style="text-align:right;">
          <div class="score-display" style="color:var(--${v.color});">${coef.toFixed(1)}</div>
          <div class="score-max">/ 10 — ${v.icon} ${v.label}</div>
        </div>
      </div>
      <div class="subnet-body">
        <div class="agent-grid">
          ${TAO_AGENT_KEYS.map(k => `<div class="agent-cell"><div class="emoji">${TAO_AGENT_EMOJIS[k]}</div><div class="agent-name">${TAO_AGENT_LABELS[k]}</div><div class="agent-score">${subnet.scores[k]}</div></div>`).join('')}
        </div>
        <div class="analyst-section"><h3>🔍 Oracle Analysis</h3><p>${subnet.description || ''}</p></div>
        ${bull ? `<div class="bull-bear">
          <div class="bull-box"><h4>Bull Case</h4><ul>${bull}</ul></div>
          ${bear ? `<div class="bear-box"><h4>Bear Case</h4><ul>${bear}</ul></div>` : ''}
        </div>` : ''}
      </div>
    </div>`;
  }

  /**
   * Render all TAO subnet cards.
   */
  function renderSubnetCards(subnets, weights, verdicts) {
    const visible = subnets.filter(s => !s.hidden);
    const cards = visible.map(s => renderSubnetCard(s, weights, verdicts)).join('');
    const hidden = subnets.filter(s => s.hidden);
    const hiddenSummary = hidden.length ? `
      <details>
        <summary>🔴 Low-Scoring Subnets (${hidden.length})</summary>
        <div style="padding:1rem;background:var(--card);border:1px solid var(--border);border-top:none;border-radius:0 0 12px 12px;">
          ${hidden.map(s => `<p style="font-size:0.82rem;color:var(--muted);margin-bottom:0.5rem;"><strong>SN${s.netuid} ${s.name}</strong> — ${s.description || ''}</p>`).join('')}
        </div>
      </details>` : '';
    return cards + hiddenSummary;
  }

  /**
   * Render the ETH/HYPE ecosystem project table.
   */
  function renderProjectTable(projects, weights, verdicts) {
    const rows = projects.map(p => {
      const coef = lisaCoefficient(p, weights, AGENT_KEYS);
      const v = verdict(coef, verdicts);
      const featured = p.details && p.details.featured ? ' ⭐' : '';
      return `<tr onclick="Router.showProject('${p.id}')">
        <td>${p.details ? p.details.rank : '-'}</td>
        <td>${p.name}${featured}</td>
        <td>${p.category || ''}</td>
        <td>${p.token || 'N/A'}</td>
        ${AGENT_KEYS.map(k => `<td>${p.scores[k]}</td>`).join('')}
        <td><span class="score-badge ${scoreClass(coef)}">${coef.toFixed(1)}</span></td>
        <td><span class="verdict verdict-${v.color}">${v.icon} ${v.label}</span></td>
      </tr>`;
    }).join('');

    return `<div class="table-wrap"><table class="score-table">
      <thead><tr><th>Rank</th><th>Project</th><th>Category</th><th>Token</th>
        <th>🔍</th><th>🧮</th><th>💧</th><th>📊</th><th>🔥</th><th>👨‍💻</th><th>⚠️</th>
        <th>Lisa C</th><th>Verdict</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>`;
  }

  /**
   * Render a single ETH/HYPE project card.
   */
  function renderProjectCard(project, weights, verdicts) {
    const coef = lisaCoefficient(project, weights, AGENT_KEYS);
    const v = verdict(coef, verdicts);
    const bull = (project.bull_case || []).map(x => `<li>${x}</li>`).join('');
    const bear = (project.bear_case || []).map(x => `<li>${x}</li>`).join('');
    const gradients = {
      green: 'linear-gradient(135deg, var(--accent-glow), rgba(34,197,94,0.04))',
      blue: 'linear-gradient(135deg, var(--accent-glow), rgba(59,130,246,0.04))',
      yellow: 'linear-gradient(135deg, var(--accent-glow), rgba(234,179,8,0.04))',
      orange: 'linear-gradient(135deg, var(--accent-glow), rgba(249,115,22,0.04))',
      red: 'linear-gradient(135deg, var(--accent-glow), rgba(239,68,68,0.04))'
    };

    const tvlStr = project.tvl ? '$' + (project.tvl >= 1e9 ? (project.tvl / 1e9).toFixed(1) + 'B' : (project.tvl / 1e6).toFixed(0) + 'M') : 'N/A';

    return `<div class="subnet-card" id="card-${project.id}">
      <div class="subnet-header" style="background: ${gradients[v.color] || 'none'}">
        <div>
          <h2>${project.name}${project.token ? ' (' + project.token + ')' : ''}</h2>
          <div class="subtitle">${project.category || ''}${project.website ? ' · ' + project.website : ''}</div>
          <div class="subtitle" style="margin-top:0.25rem;font-size:0.75rem;">TVL: ${tvlStr}${project.tokenPrice ? ' · Price: $' + project.tokenPrice : ''}${project.mcap ? ' · MCap: $' + (project.mcap / 1e6).toFixed(0) + 'M' : ''}</div>
        </div>
        <div style="text-align:right;">
          <div class="score-display" style="color:var(--${v.color});">${coef.toFixed(1)}</div>
          <div class="score-max">/ 10 — ${v.icon} ${v.label}</div>
        </div>
      </div>
      <div class="subnet-body">
        <div class="agent-grid">
          ${AGENT_KEYS.map(k => `<div class="agent-cell"><div class="emoji">${AGENT_EMOJIS[k]}</div><div class="agent-name">${AGENT_LABELS[k]}</div><div class="agent-score">${project.scores[k]}</div></div>`).join('')}
        </div>
        <div class="analyst-section"><h3>🔍 TruthSeeker Analysis</h3><p>${project.description || ''}</p></div>
        ${bull ? `<div class="bull-bear">
          <div class="bull-box"><h4>Bull Case</h4><ul>${bull}</ul></div>
          ${bear ? `<div class="bear-box"><h4>Bear Case</h4><ul>${bear}</ul></div>` : ''}
        </div>` : ''}
      </div>
    </div>`;
  }

  /**
   * Render all ETH/HYPE project cards.
   */
  function renderProjectCards(projects, weights, verdicts) {
    return projects.map(p => renderProjectCard(p, weights, verdicts)).join('');
  }

  return {
    renderScoreTable, renderSubnetCard, renderSubnetCards,
    renderProjectTable, renderProjectCard, renderProjectCards,
    lisaCoefficient, verdict, scoreClass
  };
})();
