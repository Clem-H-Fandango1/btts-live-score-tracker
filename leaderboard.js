/*
 * leaderboard.js — public season standings + stats page
 */

const STAT_COLS = [
  { key: 'btts',         label: '✅' },
  { key: 'fives',        label: "5's" },
  { key: 'fours',        label: "4's" },
  { key: 'threes',       label: "3's" },
  { key: 'butlers',      label: 'Butlers' },
  { key: 'clinchers',    label: 'Clinchers' },
  { key: 'costers',      label: 'Costers' },
  { key: 'donuts',       label: 'Donuts' },
  { key: 'superButlers', label: 'Super But' },
  { key: 'threethrees',  label: '3-3' },
  { key: 'twoReds',      label: '2 Reds' },
  { key: 'threeReds',    label: '3 Reds' },
  { key: 'noPicks',      label: 'No Picks' },
];

async function loadLeaderboard() {
  const wrap      = document.getElementById('leaderboard-wrap');
  const updatedEl = document.getElementById('lb-updated');
  if (!wrap) return;

  try {
    const [spRes, statsRes] = await Promise.all([
      fetch('/api/season_points'),
      fetch('/api/season_stats'),
    ]);
    const sp    = await spRes.json();
    const stats = await statsRes.json();

    const updated = sp['_lastUpdated'] || '';

    function formatDate(str) {
      if (!str) return '';
      const d = new Date(str);
      if (isNaN(d)) return str;
      const days   = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
      const months = ['January','February','March','April','May','June','July','August','September','October','November','December'];
      const day    = d.getDate();
      const suf    = (day===1||day===21||day===31)?'st':(day===2||day===22)?'nd':(day===3||day===23)?'rd':'th';
      return days[d.getDay()] + ' ' + day + suf + ' ' + months[d.getMonth()] + ' ' + d.getFullYear();
    }

    if (updatedEl) updatedEl.style.display = 'none';

    // Build ranked rows — sort: points desc, then BTTS count desc, then alpha
    const names = Object.keys(sp).filter(k => !k.startsWith('_'));
    const rows  = names.map(n => ({ name: n, pts: sp[n] || 0, btts: (stats[n] && stats[n].btts) || 0 }));
    rows.sort((a, b) => b.pts - a.pts || b.btts - a.btts || a.name.localeCompare(b.name));

    const posClasses = ['first','second','third'];

    // ── Main standings table ───────────────────────────────────────
    const lb = document.createElement('div');
    lb.className = 'leaderboard';

    const header = document.createElement('div');
    header.className = 'leaderboard-header';
    const dateStr = updated ? ' \u2014 As of ' + formatDate(updated) : '';
    header.textContent = 'Season Standings' + dateStr;
    lb.appendChild(header);

    rows.forEach((row, i) => {
      const r = document.createElement('div');
      r.className = 'leaderboard-row';

      const pos   = document.createElement('span');
      pos.className = 'lb-pos' + (i < 3 ? ' ' + posClasses[i] : '');
      pos.textContent = (i + 1) + '.';

      const name  = document.createElement('span');
      name.className = 'lb-name';
      name.textContent = row.name;

      const total = document.createElement('span');
      total.className = 'lb-total';
      total.textContent = row.pts + ' pts';

      r.appendChild(pos); r.appendChild(name); r.appendChild(total);
      lb.appendChild(r);
    });

    wrap.appendChild(lb);

    // ── OTHER STATS heading ────────────────────────────────────────
    const statsHeading = document.createElement('div');
    statsHeading.textContent = 'OTHER STATS';
    statsHeading.style.cssText = [
      'color:#a0c8a8', 'font-weight:700', 'font-size:0.78em',
      'text-align:center', 'letter-spacing:1px',
      'padding:10px 14px 4px', 'margin-top:24px'
    ].join(';');
    wrap.appendChild(statsHeading);

    // ── Stats table (always visible) ──────────────────────────────
    const statsWrap = document.createElement('div');
    statsWrap.style.marginTop = '0';
    statsWrap.style.overflowX = 'auto';

    const table = document.createElement('table');
    table.style.cssText = 'width:100%;border-collapse:collapse;font-size:0.82em;';

    // Header row
    const thead = document.createElement('thead');
    const hrow  = document.createElement('tr');
    hrow.style.background = '#027B5B';
    ['Player', ...STAT_COLS.map(c => c.label)].forEach((h, i) => {
      const th = document.createElement('th');
      th.textContent = h;
      th.style.cssText = 'padding:7px 10px;color:#F9DC1C;font-weight:800;text-align:' + (i===0?'left':'center') + ';white-space:nowrap;border-bottom:2px solid #014d38;font-size:' + (i===1?'1.3em':'1em') + ';';
      hrow.appendChild(th);
    });
    thead.appendChild(hrow);
    table.appendChild(thead);

    // Data rows (sorted by season points)
    const tbody = document.createElement('tbody');
    rows.forEach((row, i) => {
      const tr = document.createElement('tr');
      tr.style.background = i % 2 === 0 ? '#023f2b' : '#013e2e';

      const nameTd = document.createElement('td');
      nameTd.textContent = row.name;
      nameTd.style.cssText = 'padding:6px 10px;color:#F9DC1C;font-weight:700;border-bottom:1px solid #014d38;';
      tr.appendChild(nameTd);

      const s = stats[row.name] || {};
      STAT_COLS.forEach(col => {
        const td = document.createElement('td');
        const val = s[col.key] || 0;
        td.textContent = val > 0 ? val : '';
        td.style.cssText = 'padding:6px 10px;text-align:center;color:#e0e0e0;border-bottom:1px solid #014d38;';
        // Highlight non-zero cells
        if (val > 0) {
          if (['donuts','costers','superButlers','threethrees','twoReds','threeReds'].includes(col.key)) {
            td.style.color = '#f87171'; // red-ish for negative events
          } else if (['fives','clinchers'].includes(col.key)) {
            td.style.color = '#4ade80'; // green for best outcomes
          } else {
            td.style.color = '#F9DC1C'; // yellow for general good
          }
        }
        tr.appendChild(td);
      });

      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    statsWrap.appendChild(table);
    wrap.appendChild(statsWrap);



  } catch (e) {
    wrap.textContent = 'Could not load standings.';
    console.error(e);
  }
}

document.addEventListener('DOMContentLoaded', loadLeaderboard);
