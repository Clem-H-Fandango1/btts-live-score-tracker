// ── viewer_v2.js ─────────────────────────────────────────────────────────────
'use strict';

let assignments  = {};
let groups       = {};
let seasonPoints = {};
let sixerActive  = false;
const matchDataCache = {};

document.addEventListener('DOMContentLoaded', () => {
  Promise.all([
    fetch('/api/assignments').then(r => r.json()),
    fetch('/api/groups').then(r => r.json()),
  ]).then(([a, g]) => {
    assignments  = a;
    groups       = g;
    sixerActive  = groups && Object.values(groups).some(v => v === 'sixer');
    buildCards();
    fetch('/api/season_points').then(r => r.json()).then(d => {
      seasonPoints = d;
      applyGroupClincher();
    }).catch(() => {});
    startPolling();
  });
});

// ── Build cards ─────────────────────────────────────────────────────────────
function buildCards() {
  const topSection    = document.getElementById('top-section');
  const bottomSection = document.getElementById('bottom-section');
  const sixerSection  = document.getElementById('sixer-section');
  const topContainer    = document.getElementById('top-cards');
  const bottomContainer = document.getElementById('bottom-cards');
  const sixerContainer  = document.getElementById('sixer-cards');

  topContainer.innerHTML    = '';
  bottomContainer.innerHTML = '';
  sixerContainer.innerHTML  = '';

  if (sixerActive) {
    topSection.style.display    = 'none';
    bottomSection.style.display = 'none';
    sixerSection.style.display  = 'block';
  } else {
    topSection.style.display    = 'block';
    bottomSection.style.display = 'block';
    sixerSection.style.display  = 'none';
  }

  Object.keys(assignments).forEach((name) => {
    const card = document.createElement('div');
    card.className = 'score-card';
    card.id = `card-${name}`;
    card.dataset.btts = 'false';

    // ── Header row: name pill | pts badge ──────────────────
    const cardHeader = document.createElement('div');
    cardHeader.className = 'card-header';

    const friendBox = document.createElement('div');
    friendBox.className = 'friend-box';
    friendBox.textContent = name;

    const bttsTick = document.createElement('span');
    bttsTick.className = 'btts-tick';
    bttsTick.textContent = '✓';
    bttsTick.style.display = 'none';

    const nameGroup = document.createElement('div');
    nameGroup.className = 'name-group';
    nameGroup.appendChild(friendBox);
    nameGroup.appendChild(bttsTick);
    cardHeader.appendChild(nameGroup);

    const pointsBadge = document.createElement('span');
    pointsBadge.className = 'points-badge pts-zero';
    pointsBadge.textContent = '0 pts';

    // Status goes in the header between name and pts badge
    const statusSpan = document.createElement('div');
    statusSpan.className = 'status';
    cardHeader.appendChild(statusSpan);

    cardHeader.appendChild(pointsBadge);
    card.appendChild(cardHeader);

    // ── Score row: [Home name] [N – N] [Away name] ─────────
    const scoreRow = document.createElement('div');
    scoreRow.className = 'score-row';

    // Left: home name + red cards (right-aligned)
    const scoreLeft = document.createElement('div');
    scoreLeft.className = 'score-left';
    const homeNameSpan  = document.createElement('span');
    homeNameSpan.className = 'score-team';
    const homeCardsSpan = document.createElement('span');
    homeCardsSpan.className = 'red-cards';
    scoreLeft.appendChild(homeNameSpan);
    scoreLeft.appendChild(homeCardsSpan);

    // Centre: home score | sep | away score (fixed width)
    const scoreCentre = document.createElement('div');
    scoreCentre.className = 'score-centre';
    const homeScoreSpan = document.createElement('span');
    homeScoreSpan.className = 'score-num';
    const scoreSep = document.createElement('span');
    scoreSep.className = 'score-sep';
    scoreSep.textContent = '–';
    const awayScoreSpan = document.createElement('span');
    awayScoreSpan.className = 'score-num';
    scoreCentre.appendChild(homeScoreSpan);
    scoreCentre.appendChild(scoreSep);
    scoreCentre.appendChild(awayScoreSpan);

    // Right: red cards + away name (left-aligned)
    const scoreRight = document.createElement('div');
    scoreRight.className = 'score-right';
    const awayCardsSpan = document.createElement('span');
    awayCardsSpan.className = 'red-cards';
    const awayNameSpan  = document.createElement('span');
    awayNameSpan.className = 'score-team';
    scoreRight.appendChild(awayCardsSpan);
    scoreRight.appendChild(awayNameSpan);

    scoreRow.appendChild(scoreLeft);
    scoreRow.appendChild(scoreCentre);
    scoreRow.appendChild(scoreRight);
    card.appendChild(scoreRow);

    // ── Rule / footer ───────────────────────────────────────
    const cardFooter = document.createElement('div');
    cardFooter.className = 'card-footer';

    const scoreRule = document.createElement('div');
    scoreRule.className = 'score-rule';

    const bttsSpan = document.createElement('span');
    bttsSpan.style.display = 'none'; // kept for compat

    const friendBttsTick = document.createElement('span');
    friendBttsTick.className = 'friend-btts-tick';

    cardFooter.appendChild(scoreRule);
    card.appendChild(cardFooter);

    // Store refs
    card.bttsTick      = bttsTick;
    card.homeNameSpan  = homeNameSpan;
    card.homeScoreSpan = homeScoreSpan;
    card.homeCardsSpan = homeCardsSpan;
    card.awayNameSpan  = awayNameSpan;
    card.awayScoreSpan = awayScoreSpan;
    card.awayCardsSpan = awayCardsSpan;
    card.scoreSep      = scoreSep;
    card.statusSpan    = statusSpan;
    card.bttsSpan      = bttsSpan;
    card.pointsBadge   = pointsBadge;
    card.scoreRule     = scoreRule;
    card.friendBttsTick = friendBttsTick;

    if (sixerActive) {
      sixerContainer.appendChild(card);
    } else {
      const grp = groups[name] || 'bottom';
      (grp === 'top' ? topContainer : bottomContainer).appendChild(card);
    }
  });
}

/**
 * friendlyDate(isoUtc) — smart relative date label for a match kickoff.
 */
function friendlyDate(isoUtc) {
  if (!isoUtc) return '';
  const tz = 'Europe/London';
  const matchUtc = new Date(isoUtc);
  const now = new Date();
  const toMidnight = (d) => {
    const parts = d.toLocaleDateString('en-GB', { timeZone: tz }).split('/');
    return new Date(parts[2] + '-' + parts[1] + '-' + parts[0] + 'T00:00:00');
  };
  const diffDays = Math.round((toMidnight(matchUtc) - toMidnight(now)) / 86400000);
  const timeStr = matchUtc.toLocaleTimeString('en-GB', {
    timeZone: tz, hour: 'numeric', minute: '2-digit', hour12: true
  }).replace(':00', '').toUpperCase();
  const hour = parseInt(matchUtc.toLocaleString('en-GB', {
    timeZone: tz, hour: 'numeric', hour12: false
  }), 10);
  if (diffDays === 0) {
    if (matchUtc > now) {
      if (hour >= 18) return 'Tonight, ' + timeStr;
      if (hour >= 12) return 'This Afternoon, ' + timeStr;
      return 'This Morning, ' + timeStr;
    }
    if (hour >= 18) return 'Earlier This Evening';
    if (hour >= 12) return 'Earlier This Afternoon';
    return 'Earlier This Morning';
  }
  if (diffDays === -1) return 'Yesterday';
  if (diffDays === -2) return '2 days ago';
  if (diffDays === -3) return '3 days ago';
  if (diffDays === 1) return 'Tomorrow, ' + timeStr;
  return matchUtc.toLocaleDateString('en-GB', {
    timeZone: tz, weekday: 'short', day: 'numeric', month: 'short'
  });
}

// ── Polling ─────────────────────────────────────────────────────────────────
function startPolling() {
  pollAll();
  setInterval(pollAll, 30000);
}

function pollAll() {
  Object.keys(assignments).forEach((name) => {
    const eventId = assignments[name];
    if (!eventId) return;
    fetch(`/api/match/${eventId}`)
      .then(r => r.json())
      .then(d => {
        matchDataCache[name] = d;
        updateCard(name, d);
        applyGroupClincher();
        renderLeaderboard();
      })
      .catch(() => {});
  });
}

// ── Update a single card ────────────────────────────────────────────────────
function updateCard(name, data) {
  const card = document.getElementById(`card-${name}`);
  if (!card) return;
  const state = data.state || 'pre';
  const hs  = data.homeScore ?? (state === 'pre' ? null : 0);
  const as_ = data.awayScore ?? (state === 'pre' ? null : 0);

  card.homeNameSpan.textContent  = data.homeTeam  || '—';
  card.awayNameSpan.textContent  = data.awayTeam  || '—';
  card.homeCardsSpan.textContent = '🟥'.repeat(Math.min(data.homeReds || 0, 3));
  card.awayCardsSpan.textContent = '🟥'.repeat(Math.min(data.awayReds || 0, 3));

  if (state === 'pre') {
    card.homeScoreSpan.textContent = '';
    card.awayScoreSpan.textContent = '';
    card.scoreSep.textContent = 'vs';
  } else {
    card.homeScoreSpan.textContent = hs ?? '0';
    card.awayScoreSpan.textContent = as_ ?? '0';
    card.scoreSep.textContent = '–';
  }

  // Status line
  const dateLabel = friendlyDate(data.sortDate || data.kickoffUtc || data.kickoffISO || data.kickoff_iso || data.date || data.utcDate || '');
  if (state === 'in') {
    const clock = data.clock ? `${data.clock}'` : 'Live';
    card.statusSpan.textContent = clock;
    card.statusSpan.className = 'status status-live';
  } else if (state === 'post') {
    card.statusSpan.textContent = dateLabel ? `FT · ${dateLabel}` : 'FT';
    card.statusSpan.className = 'status';
  } else {
    card.statusSpan.textContent = dateLabel || data.kickoff || 'KO TBC';
    card.statusSpan.className = 'status';
  }

  // Card colour state
  card.classList.remove('btts-hit','btts-miss','in-progress','btts-just-hit');
  const btts = (hs > 0 && as_ > 0);
  card.dataset.btts = btts ? 'true' : 'false';
  if (state === 'post') {
    card.classList.add(btts ? 'btts-hit' : 'btts-miss');
  } else if (state === 'in') {
    card.classList.add('in-progress');
  }

  // BTTS tick — show whenever both teams have scored, regardless of state
  if (card.bttsTick) {
    card.bttsTick.style.display = btts ? 'block' : 'none';
  }

  // ET flag
  card.dataset.hasET = data.hasET ? 'true' : 'false';
}

// ── Points badge ─────────────────────────────────────────────────────────────
function updatePointsBadge(name, data, extraClincher, socialPenalty) {
  const card = document.getElementById(`card-${name}`);
  if (!card) return;
  const state = data.state;
  let pts = (typeof data.points === 'number') ? data.points : null;
  let mods = (data.modifiers || []).slice();

  if (extraClincher) { pts = (pts || 0) + 1; mods = mods.concat([['Clincher', 1]]); }
  if (socialPenalty) { pts = (pts || 0) - 1; mods = mods.concat([['Coster', -1]]); }

  const carry = seasonPoints[name] || 0;
  const todayPts = (pts !== null && state !== 'pre') ? pts : 0;

  if (pts !== null && state !== 'pre') {
    const prefix = state === 'in' ? '' : '';
    const sign   = pts >= 0 ? '+' : '';
    card.pointsBadge.textContent = (state === 'in' ? '~' : '') + sign + pts + ' pts';
    card.pointsBadge.className = 'points-badge ' + (
      state === 'in' ? 'pts-live'     :
      pts > 0        ? 'pts-positive' : 'pts-zero'
    );
  } else {
    card.pointsBadge.textContent = '';
    card.pointsBadge.className = 'points-badge pts-zero';
  }

  if (!data.hasET) {
    if (state !== 'pre' && data.baseRule) {
      const modStr   = mods.map(m => m[0] + ' (' + (m[1] >= 0 ? '+' : '') + m[1] + ')').join(' · ');
      const rulePrefix = state === 'in' ? 'Currently: ' : '';
      const ruleText = rulePrefix + data.baseRule + (modStr ? ' · ' + modStr : '');
      card.scoreRule.textContent = ruleText;
      card.scoreRule.className   = state === 'in' ? 'score-rule rule-live' : 'score-rule';
    } else {
      card.scoreRule.textContent = '';
      card.scoreRule.className   = 'score-rule';
    }
  }
}

// ── Group clincher / coster ──────────────────────────────────────────────────
function applyGroupClincher() {
  const groupMembers = {};
  Object.keys(assignments).forEach((name) => {
    const grp = groups[name] || 'bottom';
    if (!groupMembers[grp]) groupMembers[grp] = [];
    groupMembers[grp].push(name);
  });

  Object.keys(groupMembers).forEach((grp) => {
    const members = groupMembers[grp];
    if (members.length < 2) return;

    const bttsMap = {}, clinMap = {};
    members.forEach((name) => {
      const d = matchDataCache[name];
      if (!d) return;
      bttsMap[name] = d.btts === true;
      clinMap[name] = d.btts90plus === true;
    });

    members.forEach((name) => {
      const d = matchDataCache[name];
      if (!d) return;
      const myBtts       = bttsMap[name];
      const myClin       = clinMap[name];
      const othersAllBtts = members.filter(n => n !== name).every(n => bttsMap[n]);
      const hasClincher   = myClin && othersAllBtts;
      const isButler      = !myBtts && d.state === 'post' && !d.isDoughnut;
      const hasPenalty    = isButler && othersAllBtts;
      updatePointsBadge(name, d, hasClincher, hasPenalty);
    });
  });
}

// ── Leaderboard ──────────────────────────────────────────────────────────────
function renderLeaderboard() {
  const el = document.getElementById('leaderboard');
  if (!el) return;

  const todayPts = {};
  Object.keys(assignments).forEach((name) => {
    const d = matchDataCache[name];
    todayPts[name] = (!d || d.state === 'pre') ? 0 : (typeof d.points === 'number' ? d.points : 0);
  });

  const rows = Object.keys(assignments).map((name) => ({
    name,
    carry : seasonPoints[name] || 0,
    today : todayPts[name] || 0,
    total : (seasonPoints[name] || 0) + (todayPts[name] || 0),
  })).sort((a, b) => b.total - a.total || a.name.localeCompare(b.name));

  const posClasses = ['first','second','third'];
  el.innerHTML = '';
  const wrap = document.createElement('div');
  wrap.className = 'leaderboard';

  const header = document.createElement('div');
  header.className = 'leaderboard-header';
  header.textContent = 'Season Leaderboard';
  wrap.appendChild(header);

  rows.forEach((row, i) => {
    const r = document.createElement('div');
    r.className = 'leaderboard-row';

    const pos = document.createElement('span');
    pos.className = 'lb-pos' + (i < 3 ? ' ' + posClasses[i] : '');
    pos.textContent = (i + 1) + '.';

    const name = document.createElement('span');
    name.className = 'lb-name';
    name.textContent = row.name;

    const today = document.createElement('span');
    today.className = 'lb-today';
    today.textContent = (row.today >= 0 ? '+' : '') + row.today + ' today';

    const total = document.createElement('span');
    total.className = 'lb-total';
    total.textContent = row.total + ' pts';

    r.append(pos, name, today, total);
    wrap.appendChild(r);
  });

  el.appendChild(wrap);
}
