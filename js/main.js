/*
 * Client-side logic for the BTTS Match Tracker.  This script
 * populates match selectors, updates live scores periodically and
 * handles user interaction when matches are selected.
 */

// Number of matches allowed for selection
const MATCH_COUNT = 6;
// Names of the participants for each match selector.  These will be
// displayed next to the corresponding dropdown so that each friend
// knows which selector belongs to them.
const SELECTOR_NAMES = ["Kenz", "Tartz", "Coypoo", "Ginger", "Kooks", "Doxy"];

// Store currently selected event IDs so we know what to update
const selectedMatches = new Array(MATCH_COUNT).fill(null);

// Initialize the application once the DOM has loaded
document.addEventListener('DOMContentLoaded', () => {
  populateMatchSelectors();
  // Update all scores periodically (every 30 seconds)
  setInterval(updateAllScores, 30000);
});

/**
 * Fetch the list of matches from the server and create the dropdowns.
 */
async function populateMatchSelectors() {
  try {
    const response = await fetch('/api/matches');
    const matches = await response.json();
    createSelectors(matches);
  } catch (err) {
    console.error('Failed to fetch match list:', err);
  }
}

/**
 * Create match selection dropdowns and scorecards.
 *
 * @param {Array} matches List of match objects returned from the server.
 */
function createSelectors(matches) {
  const selectorsContainer = document.getElementById('match-selectors');
  const scoreCardsContainer = document.getElementById('score-cards');
  selectorsContainer.innerHTML = '';
  scoreCardsContainer.innerHTML = '';
  // Prepare option list for each dropdown
  const defaultOption = document.createElement('option');
  defaultOption.value = '';
  defaultOption.textContent = 'Select a match';

  for (let i = 0; i < MATCH_COUNT; i++) {
    // Create a wrapper for each match selector
    const wrapper = document.createElement('div');
    wrapper.className = 'match-selector';
    // Label shows the participant's name
    const label = document.createElement('label');
    const name = SELECTOR_NAMES[i] || `Match ${i + 1}`;
    label.textContent = name;
    label.setAttribute('for', `match-select-${i}`);
    wrapper.appendChild(label);
    // Create the select element
    const select = document.createElement('select');
    select.id = `match-select-${i}`;
    select.dataset.index = i;
    // Append default option clone so each select has its own
    select.appendChild(defaultOption.cloneNode(true));
    // Append match options
    matches.forEach(match => {
      const opt = document.createElement('option');
      opt.value = match.eventId;
      // Show status so users know if the game is finished or scheduled (UK time)
      const statusPart = match.status ? ` (${match.status})` : '';
      opt.textContent = `${match.title}${statusPart}`;
      select.appendChild(opt);
    });
    // When a match is selected, update the associated scorecard
    select.addEventListener('change', onMatchSelected);
    wrapper.appendChild(select);
    selectorsContainer.appendChild(wrapper);
    // Create the corresponding score card container
    const card = document.createElement('div');
    card.className = 'score-card';
    card.id = `score-card-${i}`;
    card.textContent = 'No match selected';
    scoreCardsContainer.appendChild(card);
  }
}

/**
 * Event handler for when a match is selected from a dropdown.
 *
 * @param {Event} event The change event
 */
function onMatchSelected(event) {
  const select = event.target;
  const index = parseInt(select.dataset.index, 10);
  const eventId = select.value || null;
  selectedMatches[index] = eventId;
  // Immediately update this card when a new selection is made
  updateScoreCard(index);
}

/**
 * Update the score card for the given index if a match is selected.
 * If no match is selected, display a placeholder message.
 *
 * @param {number} index The index of the match/card to update
 */
async function updateScoreCard(index) {
  const eventId = selectedMatches[index];
  const card = document.getElementById(`score-card-${index}`);
  if (!eventId) {
    card.className = 'score-card';
    card.textContent = 'No match selected';
    return;
  }
  try {
    const response = await fetch(`/api/match/${eventId}`);
    const data = await response.json();
    if (data.error) {
      card.className = 'score-card';
      card.textContent = 'Match data unavailable';
      return;
    }
    const { homeTeam, awayTeam, homeScore, awayScore, status, btts } = data;
    // Build the card content
    card.className = btts ? 'score-card btts-hit' : 'score-card';
    card.innerHTML = '';
    const title = document.createElement('h3');
    title.textContent = `${homeTeam} vs ${awayTeam}`;
    card.appendChild(title);
    const scoreLine = document.createElement('span');
    scoreLine.textContent = `${homeScore} - ${awayScore}`;
    card.appendChild(scoreLine);
    const statusLine = document.createElement('span');
    statusLine.textContent = status;
    card.appendChild(statusLine);
    if (btts) {
      // Append a large green tick without the text label
      const tickSpan = document.createElement('span');
      tickSpan.className = 'btts';
      tickSpan.textContent = '✅';
      card.appendChild(tickSpan);
    }
  } catch (err) {
    console.error('Failed to fetch match details:', err);
    card.className = 'score-card';
    card.textContent = 'Error fetching match data';
  }
}

/**
 * Update all score cards for currently selected matches.
 */
function updateAllScores() {
  for (let i = 0; i < MATCH_COUNT; i++) {
    if (selectedMatches[i]) {
      updateScoreCard(i);
    }
  }
}