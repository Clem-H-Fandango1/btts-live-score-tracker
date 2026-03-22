

async function saveSeasonPoints() {
  const data = {};
  FRIEND_NAMES.forEach((name) => {
    const el = document.getElementById('season-' + name);
    data[name] = el ? parseInt(el.value, 10) || 0 : 0;
  });
  try {
    const res = await fetch('/api/season_points', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (res.ok) {
      window._seasonPoints = data;
      const msg = document.getElementById('season-save-message');
      if (msg) { msg.style.display = 'block'; setTimeout(() => msg.style.display = 'none', 3000); }
    }
  } catch (e) { alert('Error saving season points'); }
}
/*
 * Front-end logic for the BTTS admin interface.  This script
 * handles authentication, searching for upcoming fixtures and
 * assigning matches to participants.  It communicates with
 * the Flask backend via JSON APIs for login, assignment
 * storage and match search.
 */

// Names of the participants.  These must match the order
// defined on the server side (FRIEND_NAMES in app.py).
const FRIEND_NAMES = ["Kenz", "Tartz", "Coypoo", "Ginger", "Kooks", "Doxy"];

// In‑memory state for available matches and current assignments
let availableMatches = [];
let currentAssignments = {};
// In‑memory state for group assignments (top/bottom) per participant
let currentGroups = {};

// In‑memory state for global settings (title and message)
let currentSettings = {};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  // Check if admin is already logged in
  checkAdminStatus();
  // Setup login handler
  const loginForm = document.getElementById('login-form');
  if (loginForm) {
    loginForm.addEventListener('submit', handleLogin);
  }
  // Search button handler
  const searchButton = document.getElementById('search-button');
  if (searchButton) {
    searchButton.addEventListener('click', (e) => {
      e.preventDefault();
      handleSearch();
    });
  }
  // Save buttons
  const saveButton = document.getElementById('save-button');
  if (saveButton) {
    saveButton.addEventListener('click', (e) => { e.preventDefault(); handleSave(false); });
  }
  const saveGoButton = document.getElementById('save-go-button');
  if (saveGoButton) {
    saveGoButton.addEventListener('click', (e) => { e.preventDefault(); handleSave(true); });
  }

  const saveSeasonBtn = document.getElementById('save-season-button');
  if (saveSeasonBtn) saveSeasonBtn.addEventListener('click', (e) => { e.preventDefault(); saveSeasonPoints(); });
});

/**
 * Load the current site settings (title and message) from the server.
 * The loaded values are stored in currentSettings and then used to
 * populate the corresponding input fields in the admin page.
 */
async function loadSettings() {
  try {
    const res = await fetch('/api/settings');
    currentSettings = await res.json();
  } catch (err) {
    console.error('Failed to load settings', err);
    currentSettings = {};
  }
}

/**
 * Populate the site title and message input fields based on currentSettings.
 * If the settings values are empty or undefined, the fields are left blank.
 */
function populateSettingsForm() {
  const titleInput = document.getElementById('site-title');
  const msgTextarea = document.getElementById('other-message');
  if (titleInput) {
    titleInput.value = (currentSettings && currentSettings.title) ? currentSettings.title : '';
  }
  if (msgTextarea) {
    msgTextarea.value = (currentSettings && currentSettings.message) ? currentSettings.message : '';
  }
}

/**
 * Check whether the user is logged in as admin.  If so, hide
 * the login form and show the assignment UI.  Otherwise, show
 * the login form.
 */
async function checkAdminStatus() {
  try {
    const res = await fetch('/api/admin_status');

    const data = await res.json();
    if (data.admin) {
      // Fetch existing assignments and group assignments and show admin UI
      await loadAssignments();
      await loadGroups();
      // Load current site settings
      await loadSettings();
      showAdminSection();
      // Populate settings fields after showing admin section
      populateSettingsForm();
    } else {
      showLoginSection();
    }
  } catch (err) {
    console.error('Failed to check admin status', err);
  }
}

/**
 * Display only the login section.
 */
function showLoginSection() {
  const loginSec = document.getElementById('login-section');
  const adminSec = document.getElementById('admin-section');
  if (loginSec) loginSec.style.display = 'block';
  if (adminSec) adminSec.style.display = 'none';
}

/**
 * Display only the admin section.  Fetch assignments if not already
 * loaded, and render the assignment selectors when matches have
 * been searched.
 */
function showAdminSection() {
  const loginSec = document.getElementById('login-section');
  const adminSec = document.getElementById('admin-section');
  if (loginSec) loginSec.style.display = 'none';
  if (adminSec) adminSec.style.display = 'block';
  // Preload assignments if not present
  if (!currentAssignments || Object.keys(currentAssignments).length === 0) {
    loadAssignments();
  }
}

/**
 * Handle admin login submission.  Sends a POST request with the
 * password to the backend.  On success, loads assignments and
 * displays the admin UI.  On failure, shows an error message.
 */
async function handleLogin(event) {
  event.preventDefault();
  const passwordInput = document.getElementById('password');
  const errMsg = document.getElementById('login-error');
  if (!passwordInput) return;
  const password = passwordInput.value;
  try {
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password })
    });
    if (res.ok) {
      const data = await res.json();
      if (data.success) {
        // Clear password field
        passwordInput.value = '';
        // Hide error
        if (errMsg) errMsg.style.display = 'none';
        // Load assignments and groups and show admin UI
        await loadAssignments();
        await loadGroups();
          await loadSettings();
        showAdminSection();
          populateSettingsForm();
      } else {
        if (errMsg) errMsg.style.display = 'block';
      }
    } else {
      if (errMsg) errMsg.style.display = 'block';
    }
  } catch (err) {
    console.error('Login failed', err);
    if (errMsg) errMsg.style.display = 'block';
  }
}

/**
 * Load current assignments from the server.  Stores the
 * result in currentAssignments.
 */
async function loadAssignments() {
  try {
    const res = await fetch('/api/assignments');
    currentAssignments = await res.json();
  } catch (err) {
    console.error('Failed to load assignments', err);
    currentAssignments = {};
  }
}

/**
 * Load the current group assignments from the server.  The
 * backend returns a mapping of friend names to "top" or "bottom".
 */
async function loadGroups() {
  try {
    // Load next_groups (projected for next round) for admin dropdown defaults.
    // groups.json reflects the round just played; next_groups.json is the projected new order.
    const res = await fetch('/api/next_groups');
    currentGroups = await res.json();
  } catch (err) {
    console.error('Failed to load group assignments', err);
    currentGroups = {};
  }
}

/**
 * Handle searching for matches in the selected date range.  Uses
 * the start and end dates from the form inputs.  If a field is
 * empty, it defaults to today.  The backend returns matches
 * sorted alphabetically.  Once matches are loaded, we build the
 * assignment selectors.
 */

/**
 * Returns true if a match from the upcoming_matches API is a past/completed game.
 * ESPN uses status strings like 'FT', 'Final', or a plain score line for finished matches.
 * We detect past games by checking if the status does NOT look like a scheduled time.
 */
function isPastGame(match) {
  const s = (match.status || '').toLowerCase();
  // Scheduled games have status like 'Wed, March 18 at 8:00 PM UK'
  if (s.includes(' at ') && s.includes('uk')) return false;
  // Live games show minute strings like "45'" or 'Half Time'
  if (s.includes("'") || s === 'half time' || s === 'ht') return false;
  // Postponed / TBD — not past
  if (s.includes('postponed') || s.includes('tbd') || s === '') return false;
  // Anything else (FT, Final, score lines) treat as past
  return true;
}
async function handleSearch() {
  try {
    const res = await fetch('/api/upcoming_matches');
    if (res.ok) {
      availableMatches = await res.json();
      buildAssignmentSelectors();
    } else {
      console.error('Failed to load upcoming matches');
    }
  } catch (err) {
    console.error('Error loading upcoming matches', err);
  }
}

/**
 * Build the assignment selectors for each participant.  Uses the
 * availableMatches array to populate the dropdown options.  The
 * selectors are placed inside the #assign-rows container.  The
 * assignments container is shown once matches are available.
 */
function buildAssignmentSelectors() {
  const rowsContainer = document.getElementById('assign-rows');
  const container = document.getElementById('assignments-container');
  if (!rowsContainer || !container) return;
  rowsContainer.innerHTML = '';
  FRIEND_NAMES.forEach((name) => {
    const row = document.createElement('div');
    row.className = 'assign-row';
    // Label for the participant
    const label = document.createElement('label');
    label.textContent = name;
    row.appendChild(label);
    // Group selector to choose top, bottom or sixer bet.  Capitalise the
    // options for display.  When 'sixer' is selected for any friend, all
    // participants will be placed into the Sixer bet when saved.
    const groupSelect = document.createElement('select');
    groupSelect.id = `group-${name}`;
    ['top', 'bottom', 'sixer'].forEach((grp) => {
      const opt = document.createElement('option');
      opt.value = grp;
      // Display friendly text (Top, Bottom, Sixer)
      opt.textContent = grp.charAt(0).toUpperCase() + grp.slice(1);
      groupSelect.appendChild(opt);
    });
    // Set current group selection if loaded; default to 'top'
    if (currentGroups && currentGroups[name]) {
      groupSelect.value = currentGroups[name];
    } else {
      groupSelect.value = 'top';
    }
    row.appendChild(groupSelect);
    // Match selector
    const select = document.createElement('select');
    select.id = `select-${name}`;
    // Default option for no assignment
    const noneOption = document.createElement('option');
    noneOption.value = '';
    noneOption.textContent = '-- None --';
    select.appendChild(noneOption);
    // Add each available match as an option.
    // Past games (FT / completed) are grouped at the bottom with a [FT] prefix
    // so they're easy to spot but still selectable for staggered sweepstakes.
    const liveOrFuture = availableMatches.filter(m => !isPastGame(m));
    const past         = availableMatches.filter(m => isPastGame(m));

    if (liveOrFuture.length > 0 && past.length > 0) {
      const futureGroup = document.createElement('optgroup');
      futureGroup.label = '— Today / Upcoming —';
      liveOrFuture.forEach((match) => {
        const opt = document.createElement('option');
        opt.value = match.eventId;
        opt.textContent = `${match.title} (${match.status || ''})`;
        futureGroup.appendChild(opt);
      });
      select.appendChild(futureGroup);

      const pastGroup = document.createElement('optgroup');
      pastGroup.label = '— Recent Results —';
      past.forEach((match) => {
        const opt = document.createElement('option');
        opt.value = match.eventId;
        opt.textContent = `[FT] ${match.title} (${match.status || ''})`;
        pastGroup.appendChild(opt);
      });
      select.appendChild(pastGroup);
    } else {
      availableMatches.forEach((match) => {
        const opt = document.createElement('option');
        opt.value = match.eventId;
        const prefix = isPastGame(match) ? '[FT] ' : '';
        opt.textContent = `${prefix}${match.title} (${match.status || ''})`;
        select.appendChild(opt);
      });
    }
    // Preselect current assignment if present
    const assigned = (currentAssignments && currentAssignments[name]) ? currentAssignments[name] : '';
    select.value = assigned || '';
    row.appendChild(select);
    rowsContainer.appendChild(row);
  });
  // Show the assignments section
  container.style.display = 'block';
}

/**
 * Gather the selected matches and save assignments to the server.
 * Sends a POST request to /api/assignments with the mapping
 * friendName -> eventId.  Shows a success message if saved.
 */
async function handleSave(redirect = false) {
  // Build the new assignments and group objects
  const newAssignments = {};
  const newGroups = {};
  let sixerSelected = false;
  FRIEND_NAMES.forEach((name) => {
    // Match assignment
    const sel = document.getElementById(`select-${name}`);
    newAssignments[name] = sel && sel.value ? sel.value : null;
    // Group assignment
    const gsel = document.getElementById(`group-${name}`);
    const val = gsel && gsel.value ? gsel.value : 'top';
    newGroups[name] = val;
    if (val === 'sixer') {
      sixerSelected = true;
    }
  });
  // If any participant has selected 'sixer', force all groups to 'sixer'
  if (sixerSelected) {
    FRIEND_NAMES.forEach((name) => {
      newGroups[name] = 'sixer';
    });
  }
  // Gather settings from input fields
  const titleInput = document.getElementById('site-title');
  const msgTextarea = document.getElementById('other-message');
  const newTitle = titleInput && titleInput.value ? titleInput.value.trim() : '';
  const newMessage = msgTextarea && msgTextarea.value ? msgTextarea.value.trim() : '';
  try {
    // Save assignments
    const assignRes = await fetch('/api/assignments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newAssignments)
    });
    const assignData = await assignRes.json();
    if (!assignRes.ok || !assignData.success) {
      if (assignData && assignData.error) {
        alert(`Error saving assignments: ${assignData.error}`);
      } else {
        alert('Unknown error saving assignments');
      }
      return;
    }
    // Save group assignments
    const groupRes = await fetch('/api/groups', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newGroups)
    });
    const groupData = await groupRes.json();
    if (!groupRes.ok || !groupData.success) {
      alert('Error saving group assignments');
      return;
    }
    // Save settings
    const settingsRes = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: newTitle, message: newMessage })
    });
    const settingsData = await settingsRes.json();
    if (!settingsRes.ok || !settingsData.success) {
      alert('Error saving settings');
      return;
    }
    // Update local state and show success message
    currentAssignments = newAssignments;
    currentGroups = newGroups;
    currentSettings = { title: newTitle || 'BTTS Tracker', message: newMessage || '' };
    if (redirect) {
      window.location.href = '/';
      return;
    }
    const msg = document.getElementById('save-message');
    if (msg) {
      msg.style.display = 'block';
      setTimeout(() => { msg.style.display = 'none'; }, 3000);
    }
  } catch (err) {
    console.error('Error saving assignments/groups', err);
    alert('Network error saving changes');
  }
}