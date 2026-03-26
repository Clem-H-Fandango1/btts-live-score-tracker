(function () {
  const enabled = document.getElementById('wa_enabled');
  const enabledText = document.getElementById('wa_enabled_text');
  const targetMode = document.getElementById('wa_target_mode');
  const proofEnabled = document.getElementById('proof_enabled');
  const proofTarget = document.getElementById('proof_target');
  const proofBridge = document.getElementById('proof_bridge');
  const saveBtn = document.getElementById('wa_save_btn');
  const refreshBtn = document.getElementById('wa_refresh_btn');
  const testBtn = document.getElementById('wa_test_btn');
  const msg = document.getElementById('wa_msg');

  function showMsg(text, color) {
    msg.textContent = text;
    msg.style.color = color || '';
    msg.style.display = 'block';
  }

  function labelForMode(mode) {
    return ({ group: 'Group', me: 'Martin only', both: 'Both', none: 'Nobody' })[mode] || mode;
  }

  async function loadStatus() {
    const r = await fetch('/wa_status');
    const d = await r.json();

    enabled.checked = d.wa_enabled === true;
    enabledText.textContent = enabled.checked ? 'On' : 'Off';
    enabledText.style.color = enabled.checked ? '#25D366' : '#aaa';

    const mode = d.wa_target_mode || (d.wa_test_mode ? 'me' : 'group');
    targetMode.value = mode;

    proofEnabled.textContent = d.wa_enabled ? 'ON' : 'OFF';
    proofEnabled.style.color = d.wa_enabled ? '#25D366' : '#aaa';

    proofTarget.textContent = labelForMode(mode);
    proofBridge.textContent = d.bridge_connected ? 'Connected' : 'Disconnected';
    proofBridge.style.color = d.bridge_connected ? '#25D366' : 'red';
  }

  saveBtn.addEventListener('click', async function () {
    try {
      const payload = {
        wa_enabled: enabled.checked === true,
        wa_target_mode: targetMode.value,
      };
      const r = await fetch('/update_wa', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const d = await r.json();
      if (!d.success) throw new Error(d.message || 'Save failed');
      await loadStatus();
      showMsg('Saved. Backend proof updated.', 'lightgreen');
    } catch (e) {
      showMsg(e.message || 'Save failed.', 'red');
    }
  });

  refreshBtn.addEventListener('click', async function () {
    try {
      await loadStatus();
      showMsg('Refreshed from backend.', '#aaa');
    } catch (e) {
      showMsg('Refresh failed.', 'red');
    }
  });

  testBtn.addEventListener('click', async function () {
    try {
      const r = await fetch('/wa_test', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
      const d = await r.json();
      showMsg(d.message || (d.success ? 'Test sent.' : 'Test failed.'), d.success ? 'lightgreen' : 'red');
    } catch (e) {
      showMsg('Test failed.', 'red');
    }
  });

  enabled.addEventListener('change', function () {
    enabledText.textContent = enabled.checked ? 'On' : 'Off';
    enabledText.style.color = enabled.checked ? '#25D366' : '#aaa';
  });

  loadStatus().catch(() => showMsg('Could not load WhatsApp status.', 'red'));
})();
