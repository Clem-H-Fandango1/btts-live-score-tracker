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
