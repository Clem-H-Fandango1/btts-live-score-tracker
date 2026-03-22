// odds.js
// Client-side logic for the BTTS odds page.  Handles authentication,
// refreshing historical results, and displaying BTTS predictions.

/**
 * Perform an odds login using the password provided by the user.  If
 * successful, hides the login section and reveals the odds section.
 */
function handleOddsLogin(event) {
  event.preventDefault();
  const passwordInput = document.getElementById('odds-password');
  const pw = passwordInput.value;
  fetch('/api/odds_login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password: pw })
  })
    .then(async resp => {
      if (resp.ok) {
        // Successful login
        document.getElementById('odds-login-section').style.display = 'none';
        document.getElementById('odds-section').style.display = 'block';
        // Clear error message
        document.getElementById('odds-login-error').style.display = 'none';
        // Load predictions on initial login
        loadPredictions();
      } else {
        // Invalid password
        document.getElementById('odds-login-error').style.display = 'block';
      }
    })
    .catch(() => {
      document.getElementById('odds-login-error').style.display = 'block';
    });
}

/**
 * Trigger a server-side update of the historical results database.
 * Upon completion, reloads the predictions table.
 */
function updateResults() {
  fetch('/api/update_results', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ days: 7 })
  })
    .then(async resp => {
      if (!resp.ok) {
        console.error('Failed to update results');
      }
      // Whether successful or not, refresh predictions
      loadPredictions();
    })
    .catch(() => {
      console.error('Error updating results');
      loadPredictions();
    });
}

/**
 * Load the BTTS predictions from the server and render them into the
 * predictions table.
 */
function loadPredictions() {
  fetch('/api/btts_predictions?limit=5')
    .then(resp => resp.json())
    .then(data => {
      const tbody = document.querySelector('#predictions-table tbody');
      // Clear existing rows
      tbody.innerHTML = '';
      if (!Array.isArray(data) || data.length === 0) {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = 3;
        cell.textContent = 'No predictions available.';
        row.appendChild(cell);
        tbody.appendChild(row);
        return;
      }
      data.forEach(item => {
        const row = document.createElement('tr');
        const matchCell = document.createElement('td');
        matchCell.textContent = `${item.homeTeam} vs ${item.awayTeam}`;
        const leagueCell = document.createElement('td');
        leagueCell.textContent = item.league;
        const probCell = document.createElement('td');
        probCell.textContent = `${(item.probability * 100).toFixed(0)}%`;
        row.appendChild(matchCell);
        row.appendChild(leagueCell);
        row.appendChild(probCell);
        tbody.appendChild(row);
      });
    })
    .catch(() => {
      console.error('Failed to load predictions');
    });
}

// Attach event listeners once the DOM is fully loaded
document.addEventListener('DOMContentLoaded', () => {
  const loginForm = document.getElementById('odds-login-form');
  if (loginForm) {
    loginForm.addEventListener('submit', handleOddsLogin);
  }
  const updateBtn = document.getElementById('update-results-button');
  if (updateBtn) {
    updateBtn.addEventListener('click', updateResults);
  }
});