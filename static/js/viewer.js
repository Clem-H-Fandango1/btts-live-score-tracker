/*
 * viewer.js v11 — BTTS Match Tracker front-end
 * Refreshes scores every 30s. Uses bet365-style strip layout.
 */

const REFRESH_INTERVAL_MS = 30000;

let assignments = {};
let groups      = {};
let settings    = { title: '', message: '' };
let sixerActive = false;
// Maps eventId -> sortDate (ISO UTC string) from upcoming_matches
let sortDates   = {};
// Tracks last known scores per eventId to detect goals
const prevScores = {}; // { eventId: { home: n, away: n } }
const matchDataCache = {}; // { name: last api/match response }
let seasonPoints = {}; // { name: carry-forward season total }
// Flag: suppress announcements on the very first load (don't read out existing scores)


document.addEventListener('DOMContentLoaded', () => {
  fetchData();
  setInterval(updateAllScores, REFRESH_INTERVAL_MS);
});

async function fetchData() {
  try {
    const [assignRes, groupRes, settingsRes] = await Promise.all([
      fetch('/api/assignments'),
      fetch('/api/groups'),
      fetch('/api/settings'),
    ]);
    assignments = await assignRes.json();
    groups      = await groupRes.json();
    settings    = await settingsRes.json();
    // sortDates loaded separately in background — see loadSortDates()
    // Season points loaded in background
    fetch('/api/season_points').then(r => r.json()).then(d => { seasonPoints = d; applyGroupClincher(); }).catch(() => {});

    // Browser tab title only — header logo is static HTML
    document.title = (settings && settings.title && settings.title.trim()) ? settings.title : 'BTTS Match Tracker';

    // Message bar
    const msgBar = document.getElementById('message-hero');
    if (msgBar) {
      const msg = (settings && settings.message && settings.message.trim()) ? settings.message : '';
      msgBar.textContent = msg;
      msgBar.style.display = msg ? 'block' : 'none';
    }

    // Sixer check
    sixerActive = groups && Object.values(groups).some((g) => g === 'sixer');

    createScoreCards();
    updateAllScores();
    // Load sort dates in background — doesn't block card rendering
    loadSortDates();
  } catch (err) {
    console.error('Failed to load data', err);
  }
}

async function loadSortDates() {
  try {
    const res = await fetch('/api/upcoming_matches');
    if (!res.ok) return;
    const upcoming = await res.json();
    upcoming.forEach((m) => { if (m.eventId && m.sortDate) sortDates[m.eventId] = m.sortDate; });
  } catch (_) {}
}

function createScoreCards() {
  const topContainer    = document.getElementById('top-cards');
  const bottomContainer = document.getElementById('bottom-cards');
  const sixerContainer  = document.getElementById('sixer-cards');
  const topSection      = document.getElementById('top-section');
  const bottomSection   = document.getElementById('bottom-section');
  const sixerSection    = document.getElementById('sixer-section');

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

    // ── Top row: name | points badge | tick ────────────────
    const cardTop = document.createElement('div');
    cardTop.className = 'card-top';

    const friendBox = document.createElement('div');
    friendBox.className = 'friend-box';
    friendBox.textContent = name;
    cardTop.appendChild(friendBox);

    card.appendChild(cardTop);

    // ── Match info: home row / divider / away row ──────────
    const matchInfo = document.createElement('div');
    matchInfo.className = 'match-info';

    // Home row
    const homeRow = document.createElement('div');
    homeRow.className = 'match-row';
    const homeNameSpan  = document.createElement('span');
    homeNameSpan.className = 'team-name';
    const homeCardsSpan = document.createElement('span');
    homeCardsSpan.className = 'red-cards';
    const homeScoreSpan = document.createElement('span');
    homeScoreSpan.className = 'team-score';
    homeRow.appendChild(homeNameSpan);
    homeRow.appendChild(homeCardsSpan);
    homeRow.appendChild(homeScoreSpan);

    // Thin divider
    const divider = document.createElement('div');
    divider.className = 'match-divider';

    // Away row
    const awayRow = document.createElement('div');
    awayRow.className = 'match-row';
    const awayNameSpan  = document.createElement('span');
    awayNameSpan.className = 'team-name';
    const awayCardsSpan = document.createElement('span');
    awayCardsSpan.className = 'red-cards';
    const awayScoreSpan = document.createElement('span');
    awayScoreSpan.className = 'team-score';
    awayRow.appendChild(awayNameSpan);
    awayRow.appendChild(awayCardsSpan);
    awayRow.appendChild(awayScoreSpan);

    matchInfo.appendChild(homeRow);
    matchInfo.appendChild(divider);
    matchInfo.appendChild(awayRow);
    card.appendChild(matchInfo);

    // ── Bottom section: status + rule, centred ──────────────
    const cardBottom = document.createElement('div');
    cardBottom.className = 'card-bottom';
    const statusSpan = document.createElement('span');
    statusSpan.className = 'status';
    const bttsSpan   = document.createElement('span'); // kept for compat, hidden
    bttsSpan.style.display = 'none';
    cardBottom.appendChild(statusSpan);
    cardBottom.appendChild(bttsSpan);
    card.appendChild(cardBottom);

    // Rule line lives inside cardBottom so it centres below status
    const scoreRule = document.createElement('div');
    scoreRule.className = 'score-rule';
    cardBottom.appendChild(scoreRule);

    // ── Points badge (middle of top row) ──────────────────────────────
    const pointsBadge = document.createElement('span');
    pointsBadge.className = 'points-badge pts-zero';
    pointsBadge.textContent = '0 pts';
    cardTop.appendChild(pointsBadge);

    // ── BTTS tick (end of top row) ─────────────────────────────────
    const friendBttsTick = document.createElement('span');
    friendBttsTick.className = 'friend-btts-tick';
    friendBttsTick.textContent = '';
    cardTop.appendChild(friendBttsTick);
    card.friendBttsTick = friendBttsTick;

    // Store refs
    card.homeNameSpan  = homeNameSpan;
    card.homeScoreSpan = homeScoreSpan;
    card.homeCardsSpan = homeCardsSpan;
    card.awayNameSpan  = awayNameSpan;
    card.awayScoreSpan = awayScoreSpan;
    card.awayCardsSpan = awayCardsSpan;
    card.statusSpan    = statusSpan;
    card.bttsSpan      = bttsSpan;
    card.pointsBadge   = pointsBadge;
    card.scoreRule     = scoreRule;

    // Append to right container
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
 *
 * Returns strings like:
 *   "Tonight, 8:00 PM"   "This Afternoon, 3:00 PM"   "Earlier Today"
 *   "Yesterday"          "2 days ago"                 "Tomorrow, 8:00 PM"
 *   "Sat, 21 Mar"        (for anything further away)
 */
function friendlyDate(isoUtc) {
  if (!isoUtc) return '';
  const tz = 'Europe/London';
  const matchUtc = new Date(isoUtc);
  const now      = new Date();

  // Calendar-day midnight in London for diff calculation
  const toMidnight = (d) => {
    const parts = d.toLocaleDateString('en-GB', { timeZone: tz }).split('/');
    // parts = [dd, mm, yyyy]
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
  if (diffDays === 1)  return 'Tomorrow, ' + timeStr;

  return matchUtc.toLocaleDateString('en-GB', {
    timeZone: tz, weekday: 'short', day: 'numeric', month: 'short'
  });
}

/**
 * Announce a goal via the Web Speech API.
 /**
 * Update the points badge and rule line for a named card.
 * extraClincher: boolean — add +1 Cash Clincher modifier on top.
 */
function updatePointsBadge(name, data, extraClincher, socialPenalty) {
  const card = document.getElementById('card-' + name);
  if (!card) return;
  const state = data.state;
  let pts = (typeof data.points === 'number') ? data.points : null;
  let mods = (data.modifiers || []).slice(); // copy

  if (extraClincher) {
    pts = (pts || 0) + 1;
    mods = mods.concat([['Clincher', 1]]);
  }
  if (socialPenalty) {
    pts = (pts || 0) - 1;
    mods = mods.concat([['Coster', -1]]);
  }

  const carry = seasonPoints[name] || 0;
  const todayPts = (pts !== null && state !== 'pre') ? pts : 0;
  const seasonTotal = carry + todayPts;

  if (pts !== null && state !== 'pre') {
    const prefix = state === 'in' ? 'Currently ' : '';
    card.pointsBadge.textContent = prefix + (pts >= 0 ? '+' : '') + pts + ' pts';
    card.pointsBadge.className = state === 'in'
      ? 'points-badge pts-live'
      : 'points-badge ' + (pts > 0 ? 'pts-positive' : pts < 0 ? 'pts-negative' : 'pts-zero');
  } else {
    card.pointsBadge.textContent = '0 pts';
    card.pointsBadge.className = 'points-badge pts-zero';
  }

  // Season total shown on admin only — friend box stays as just the name

  // ET games have their own rule line set elsewhere — don't overwrite
  if (!data.hasET) {
    if (state !== 'pre' && data.baseRule) {
      const modStr = mods.map(m => m[0] + ' (' + (m[1] >= 0 ? '+' : '') + m[1] + ')').join(', ');
      const rulePrefix = state === 'in' ? 'Currently: ' : '';
      card.scoreRule.textContent = rulePrefix + data.baseRule + (modStr ? ' | ' + modStr : '');
      card.scoreRule.className = state === 'in' ? 'score-rule rule-live' : 'score-rule';
    } else {
      card.scoreRule.textContent = '';
      card.scoreRule.className = 'score-rule';
    }
  }
}

/**
 * After all match data is cached, check each group (top/bottom/sixer).
 * If 2 games in the group have BTTS and the 3rd has btts90plus,
 * that 3rd game gets the +1 Cash Clincher.
 */
function applyGroupClincher() {
  // Build group membership from assignments + groups
  const groupMembers = {}; // { 'top': [names], 'bottom': [names], 'sixer': [names] }
  Object.keys(assignments).forEach((name) => {
    const grp = groups[name] || 'bottom';
    if (!groupMembers[grp]) groupMembers[grp] = [];
    groupMembers[grp].push(name);
  });

  Object.keys(groupMembers).forEach((grp) => {
    const members = groupMembers[grp];
    if (members.length < 2) return;

    // Collect BTTS status for each member
    const bttsMap = {};
    const clinMap = {};
    members.forEach((name) => {
      const d = matchDataCache[name];
      if (!d) return;
      bttsMap[name] = d.btts === true;
      clinMap[name] = d.btts90plus === true;
    });

    // How many members have BTTS in this group?
    const bttsCount = members.filter(n => bttsMap[n]).length;
    const otherTwoAllBtts = (bttsCount >= members.length - 1);

    members.forEach((name) => {
      const d = matchDataCache[name];
      if (!d) return;
      const myBtts  = bttsMap[name];
      const myClin  = clinMap[name];
      const othersAllBtts = members.filter(n => n !== name).every(n => bttsMap[n]);

      // Cash Clincher: I completed BTTS at 90+ AND the other two already had BTTS
      const hasClincher = myClin && othersAllBtts;

      // Social Penalty: other two have BTTS, I don't (game finished)
      // Coster: one team didn't score (Butler/1-0 type) AND both group-mates had BTTS
      // 0-0 (Double Doughnut) does NOT trigger a Coster — both teams cost the money, different rule
      const isButler = !myBtts && d.state === 'post' && !d.isDoughnut;
      const hasPenalty = isButler && othersAllBtts;

      updatePointsBadge(name, d, hasClincher, hasPenalty);
    });
  });
}

/**
 * Render the leaderboard from current matchDataCache + seasonPoints.
 * Called after every score update.
 */
function renderLeaderboard() {
  const el = document.getElementById('leaderboard');
  if (!el) return;

  // Collect today's points per person from matchDataCache
  const todayPts = {};
  Object.keys(assignments).forEach((name) => {
    const d = matchDataCache[name];
    if (!d || d.state === 'pre') {
      todayPts[name] = 0;
    } else {
      todayPts[name] = (typeof d.points === 'number') ? d.points : 0;
    }
  });

  // Build combined totals
  const rows = Object.keys(assignments).map((name) => {
    const carry  = seasonPoints[name] || 0;
    const today  = todayPts[name] || 0;
    return { name, carry, today, total: carry + today };
  });

  // Sort by total desc, then name
  rows.sort((a, b) => b.total - a.total || a.name.localeCompare(b.name));

  const posClasses = ['first', 'second', 'third'];

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

    r.appendChild(pos);
    r.appendChild(name);
    r.appendChild(today);
    r.appendChild(total);
    wrap.appendChild(r);
  });

  el.appendChild(wrap);
}
function updateAllScores() {
  Object.keys(assignments).forEach((name) => updateScoreCard(name, assignments[name]));
}

async function updateScoreCard(name, eventId) {
  const card = document.getElementById(`card-${name}`);
  if (!card) return;

  if (!eventId) {
    card.homeNameSpan.textContent  = '';
    card.homeScoreSpan.textContent = '';
    card.awayNameSpan.textContent  = '';
    card.awayScoreSpan.textContent = '';
    card.statusSpan.textContent    = 'No match assigned';
    card.bttsSpan.textContent      = '';
    if (card.friendBttsTick) card.friendBttsTick.textContent = '';
    card.pointsBadge.textContent   = '0 pts';
    card.pointsBadge.className     = 'points-badge pts-zero';
    card.scoreRule.textContent     = '';
    if (card.dataset.btts === 'true') {
      card.classList.remove('btts-hit');
      card.dataset.btts = 'false';
    }
    return;
  }

  try {
    const res  = await fetch(`/api/match/${eventId}`);
    const data = await res.json();

    if (data.error) {
      card.homeNameSpan.textContent  = '';
      card.homeScoreSpan.textContent = '';
      card.awayNameSpan.textContent  = '';
      card.awayScoreSpan.textContent = '';
      card.statusSpan.textContent    = 'Match data unavailable';
      card.bttsSpan.textContent      = '';
      if (card.dataset.btts === 'true') {
        card.classList.remove('btts-hit');
        card.dataset.btts = 'false';
      }
      return;
    }

    const {
      homeTeam, awayTeam, homeScore, awayScore,
      status, kickoffTime, state, btts,
      homeRedCards = 0, awayRedCards = 0,
    } = data;

    // BTTS class transition
    const prevBtts = card.dataset.btts === 'true';
    if (btts && !prevBtts) {
      card.classList.add('btts-just-hit');
      setTimeout(() => card.classList.remove('btts-just-hit'), 900);
      card.classList.add('btts-hit');
      card.classList.remove('btts-miss');
      card.dataset.btts = 'true';
    } else if (!btts && prevBtts) {
      card.classList.remove('btts-hit');
      card.dataset.btts = 'false';
    }
    // Red background for finished games with no BTTS
    if (state === 'post' && !btts) {
      card.classList.add('btts-miss');
    } else {
      card.classList.remove('btts-miss');
    }
    // Yellowy-green tint for in-progress only (never on post, never if BTTS already hit)
    if (state === 'in' && !btts) {
      card.classList.add('in-progress');
    } else {
      card.classList.remove('in-progress');
    }
    // Belt-and-braces: ensure post games never carry in-progress styling
    if (state === 'post') {
      card.classList.remove('in-progress');
    }

    prevScores[eventId] = { home: homeScore, away: awayScore };

    card.homeNameSpan.textContent  = homeTeam;
    card.homeScoreSpan.textContent = homeScore;
    card.awayNameSpan.textContent  = awayTeam;
    card.awayScoreSpan.textContent = awayScore;

    const rcIcon = '🟥';
    const fmt    = (n) => (!n || n <= 0) ? '' : (n === 1 ? rcIcon : `${rcIcon} ×${n}`);
    card.homeCardsSpan.textContent = fmt(homeRedCards);
    card.awayCardsSpan.textContent = fmt(awayRedCards);

    if (state === 'post') {
      const label = friendlyDate(data.sortDate || sortDates[eventId]);
      const baseStatus = label ? (status + ' · ' + label) : status;
      card.statusSpan.textContent = baseStatus;
      card.statusSpan.className = 'status';
      // Always clear live styling on completion
      card.scoreRule.className = 'score-rule';
      // For ET games, override the rule line with a clear explanation
      if (data.hasET) {
        const et90Rule = data.baseRule ? data.baseRule.split(' —')[0] : 'FT';
        card.scoreRule.textContent = 'Final score ' + homeScore + '-' + awayScore + ' (AET). UGSS points based on ' + data.score90h + '-' + data.score90a + ' at 90 mins: ' + et90Rule + '.';
      } else if (data.baseRule) {
        const mods = (data.modifiers || []).map(m => m[0] + ' (' + (m[1] >= 0 ? '+' : '') + m[1] + ')').join(', ');
        card.scoreRule.textContent = data.baseRule + (mods ? ' | ' + mods : '');
      } else {
        card.scoreRule.textContent = '';
      }
    } else if (state === 'in') {
      card.statusSpan.textContent = status;
      card.statusSpan.className = 'status status-live';
      if (!data.hasET && data.baseRule) {
        const mods = (data.modifiers || []).map(m => m[0] + ' (' + (m[1] >= 0 ? '+' : '') + m[1] + ')').join(', ');
        card.scoreRule.textContent = 'Currently: ' + data.baseRule + (mods ? ' | ' + mods : '');
        card.scoreRule.className = 'score-rule rule-live';
      }
    } else if (state === 'pre') {
      const label = friendlyDate(data.sortDate || sortDates[eventId]);
      card.statusSpan.textContent = label || kickoffTime;
    } else {
      card.statusSpan.textContent = status;
    }
    if (card.friendBttsTick) card.friendBttsTick.textContent = btts ? '✅' : '';
    card.bttsSpan.textContent = '';

    // ── Cache match data + sortDate immediately from match response ───
    matchDataCache[name] = data;
    if (data.sortDate) sortDates[eventId] = data.sortDate;
    applyGroupClincher();
    renderLeaderboard();

  } catch (err) {
    console.error('Score fetch error', err);
    card.statusSpan.textContent = 'Error fetching data';
  }
}
