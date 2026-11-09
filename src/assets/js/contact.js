/*
 * Contact page mail composer.
 * - Without JavaScript the compose link already opens a general inquiry mail.
 * - ?topic= and ?intent= from other pages are read against a whitelist only; unknown
 *   values are ignored and never written into the page or the mail.
 * - Changing the topic clears the intent that came with the link.
 * - Nothing is stored or sent anywhere; the visitor's own mail app opens.
 */
(() => {
  const form = document.getElementById("ct-form");
  const cfgEl = document.getElementById("ct-config");
  if (!form || !cfgEl) return;
  const cfg = JSON.parse(cfgEl.textContent);
  const compose = document.getElementById("ct-compose");
  const subjectOut = document.querySelector("#ct-subject span");
  const email = document.getElementById("ct-email").textContent.trim();
  const has = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);

  let intent = null;
  const params = new URLSearchParams(location.search);
  const qTopic = params.get("topic");
  if (qTopic && has(cfg.topics, qTopic)) {
    form.querySelector(`input[name="topic"][value="${qTopic}"]`).checked = true;
    const qIntent = params.get("intent");
    if (qIntent && has(cfg.intents, qIntent)) intent = qIntent;
  }

  function selectedTopic() {
    const el = form.querySelector('input[name="topic"]:checked');
    return el && has(cfg.topics, el.value) ? el.value : null;
  }

  function update() {
    const topic = selectedTopic();
    let label = topic ? cfg.topics[topic] : "";
    if (topic && intent) label += " · " + cfg.intents[intent];
    const subject = `${cfg.prefix} ${topic ? label : cfg.general}`;
    const lines = [...cfg.before, topic ? `${cfg.topic_line} ${label}` : cfg.topic_line, ...cfg.after];
    const body = lines.join("\r\n") + "\r\n";
    compose.href = `mailto:${email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    subjectOut.textContent = subject;
    subjectOut.parentElement.hidden = false;
  }

  form.addEventListener("change", (e) => {
    if (e.target.name === "topic") intent = null;   // a new topic drops the intent from the previous page
    update();
  });
  form.addEventListener("submit", (e) => e.preventDefault());
  update();

  // Copy email address
  const copyBtn = document.getElementById("ct-copy");
  const status = document.getElementById("ct-status");
  const emailEl = document.getElementById("ct-email");
  copyBtn.hidden = false;
  copyBtn.addEventListener("click", async () => {
    status.textContent = "";
    try {
      if (!navigator.clipboard || !window.isSecureContext) throw new Error("clipboard unavailable");
      await navigator.clipboard.writeText(email);
      status.textContent = cfg.copied;
      status.dataset.state = "ok";
    } catch (err) {
      const range = document.createRange();          // select the text so it can be copied by hand
      range.selectNodeContents(emailEl);
      const sel = getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
      status.textContent = cfg.copy_failed;
      status.dataset.state = "error";
    }
  });
})();
