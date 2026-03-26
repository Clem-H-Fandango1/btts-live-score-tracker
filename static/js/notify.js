document.getElementById("save-telegram").addEventListener("click", async function () {
  const token = document.getElementById("token").value.trim();
  const chatId = document.getElementById("chat_id").value.trim();
  const statusElem = document.getElementById("save-status");

  if (!token || !chatId) {
    statusElem.textContent = "Both fields are required.";
    statusElem.style.color = "red";
    statusElem.style.display = "block";
    return;
  }

  try {
    const resp = await fetch("/update_telegram", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: token, chat_id: chatId })
    });
    const data = await resp.json();
    statusElem.textContent = data.message || (data.success ? "Saved." : "Failed.");
    statusElem.style.color = data.success ? "lightgreen" : "red";
    statusElem.style.display = "block";
  } catch (err) {
    statusElem.textContent = "Network or server error while saving.";
    statusElem.style.color = "red";
    statusElem.style.display = "block";
  }
});


// Send test notification
(function(){
  const btn = document.getElementById("send-test");
  if (!btn) return;
  const testStatus = document.getElementById("test-status");
  btn.addEventListener("click", async function(){
    const text = (document.getElementById("test_text")?.value || "BTTS Test Notification ✅").trim();
    testStatus.textContent = "Sending…";
    testStatus.style.color = "";
    testStatus.style.display = "block";
    try {
      const resp = await fetch("/test_telegram", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({ text })
      });
      const data = await resp.json();
      testStatus.textContent = data.message || (data.success ? "Sent." : "Failed.");
      testStatus.style.color = data.success ? "lightgreen" : "red";
    } catch (e) {
      testStatus.textContent = "Network error while sending test.";
      testStatus.style.color = "red";
    }
  });
})();


// Status panel refresh
(function(){
  const btn = document.getElementById("refresh-status");
  const pre = document.getElementById("status-json");
  if (!btn || !pre) return;
  async function refresh(){
    try{
      const resp = await fetch("/telegram_status");
      const data = await resp.json();
      pre.textContent = JSON.stringify(data, null, 2);
    }catch(e){
      pre.textContent = "Error fetching status.";
    }
  }
  btn.addEventListener("click", refresh);
  // auto-load on page open
  refresh();
})();

// ── WhatsApp toggle ──────────────────────────────────────────────────────────
(function () {
  const toggle = document.getElementById('wa_toggle');
  const label = document.getElementById('wa_toggle_label');
  const statusPre = document.getElementById('wa_status_json');
  const msg = document.getElementById('wa_msg');

  async function loadWaStatus() {
    try {
      const r = await fetch('/wa_status');
      const d = await r.json();
      toggle.checked = !!d.wa_enabled;
      label.textContent = d.wa_enabled ? '🟢 Enabled' : '⚫ Disabled';
      label.style.color = d.wa_enabled ? '#25D366' : '#aaa';
      statusPre.textContent = JSON.stringify(d, null, 2);
    } catch (e) {
      label.textContent = 'Error loading status';
    }
  }

  toggle.addEventListener('change', async function () {
    try {
      const r = await fetch('/update_wa', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ wa_enabled: toggle.checked }),
      });
      const d = await r.json();
      if (d.success) {
        label.textContent = toggle.checked ? '🟢 Enabled' : '⚫ Disabled';
        label.style.color = toggle.checked ? '#25D366' : '#aaa';
        showMsg(toggle.checked ? 'WhatsApp alerts enabled ✅' : 'WhatsApp alerts disabled', toggle.checked ? 'lightgreen' : '#aaa');
      } else {
        showMsg(d.message || 'Failed to save.', 'red');
        toggle.checked = !toggle.checked; // revert
      }
    } catch (e) {
      showMsg('Network error.', 'red');
      toggle.checked = !toggle.checked;
    }
  });

  document.getElementById('wa_refresh_btn').addEventListener('click', loadWaStatus);

  document.getElementById('wa_test_btn').addEventListener('click', async function () {
    showMsg('Sending…', '#aaa');
    try {
      const r = await fetch('/update_wa', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ wa_enabled: true, _test: true }),
      });
      // Actually send a test via wa_status check + direct call
      const r2 = await fetch('/wa_status');
      const d2 = await r2.json();
      if (!d2.bridge_connected) {
        showMsg('Bridge not connected — check WA bridge container.', 'red');
        return;
      }
      // Send test message directly
      const r3 = await fetch('http://' + location.hostname + ':8097/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jid: d2.group_jid, message: '🧪 BTTS WA test message — if you see this, it works!' }),
      });
      const d3 = await r3.json();
      showMsg(d3.ok ? '✅ Test sent to WhatsApp group!' : 'Failed: ' + JSON.stringify(d3), d3.ok ? 'lightgreen' : 'red');
    } catch (e) {
      showMsg('Error: ' + e.message, 'red');
    }
  });

  function showMsg(text, color) {
    msg.textContent = text;
    msg.style.color = color || '';
    msg.style.display = 'block';
  }

  loadWaStatus();
})();
