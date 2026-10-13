/*!
 * NFSU Library Assistant — reference floating chat widget.
 *
 * This is a REFERENCE integration for the frontend team. It is deliberately
 * dependency-free and non-intrusive: it mounts nothing into the OPAC DOM except
 * a single fixed-position container, so it cannot affect KOHA's search UI.
 *
 * Usage:
 *   <script src="widget.js"
 *           data-api-base="http://localhost:5000"
 *           defer></script>
 */
(function () {
  "use strict";

  var script = document.currentScript;
  var API_BASE =
    (script && script.getAttribute("data-api-base")) ||
    window.NFSU_CHATBOT_API ||
    "http://localhost:5000";

  var CSS = `
  #nfsu-chat-root{position:fixed;right:20px;bottom:20px;z-index:2147483000;
    font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;font-size:14px}
  #nfsu-chat-btn{width:56px;height:56px;border-radius:50%;border:none;cursor:pointer;
    background:#0b6b3a;color:#fff;box-shadow:0 6px 18px rgba(0,0,0,.25);font-size:24px;
    display:flex;align-items:center;justify-content:center;transition:transform .15s}
  #nfsu-chat-btn:hover{transform:scale(1.06)}
  #nfsu-chat-panel{display:none;position:fixed;right:20px;bottom:88px;width:380px;
    max-width:calc(100vw - 32px);height:520px;max-height:calc(100vh - 120px);
    background:#fff;border-radius:14px;box-shadow:0 12px 40px rgba(0,0,0,.28);
    flex-direction:column;overflow:hidden}
  #nfsu-chat-panel.open{display:flex}
  .nfsu-head{background:#0b6b3a;color:#fff;padding:12px 14px;font-weight:600;
    display:flex;justify-content:space-between;align-items:center}
  .nfsu-head button{background:none;border:none;color:#fff;font-size:18px;cursor:pointer}
  .nfsu-log{flex:1;overflow-y:auto;padding:12px;background:#f6f7f9}
  .nfsu-msg{margin-bottom:10px;display:flex}
  .nfsu-msg.user{justify-content:flex-end}
  .nfsu-bubble{max-width:85%;padding:8px 11px;border-radius:12px;line-height:1.4;
    white-space:pre-wrap;word-wrap:break-word}
  .nfsu-msg.bot .nfsu-bubble{background:#fff;border:1px solid #e3e6ea}
  .nfsu-msg.user .nfsu-bubble{background:#0b6b3a;color:#fff}
  .nfsu-links{margin-top:8px;display:flex;flex-direction:column;gap:6px}
  .nfsu-links a{color:#0b6b3a;text-decoration:none;font-weight:600}
  .nfsu-links a:hover{text-decoration:underline}
  .nfsu-links .desc{color:#555;font-size:12px}
  .nfsu-chips{display:flex;flex-wrap:wrap;gap:6px;padding:8px 12px;background:#fff;
    border-top:1px solid #eee}
  .nfsu-chip{border:1px solid #cfd6dd;background:#fff;border-radius:999px;
    padding:4px 10px;font-size:12px;cursor:pointer;color:#0b6b3a}
  .nfsu-chip:hover{background:#eef6f1}
  .nfsu-input{display:flex;border-top:1px solid #eee;background:#fff}
  .nfsu-input input{flex:1;border:none;padding:12px;font-size:14px;outline:none}
  .nfsu-input button{border:none;background:#0b6b3a;color:#fff;padding:0 18px;cursor:pointer}
  .nfsu-typing{color:#888;font-style:italic}
  @media (max-width:480px){
    #nfsu-chat-panel{right:8px;left:8px;bottom:80px;width:auto;height:70vh}
  }`;

  function h(tag, attrs, text) {
    var el = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) { el.setAttribute(k, attrs[k]); });
    if (text != null) el.textContent = text;
    return el;
  }

  function inject() {
    var style = document.createElement("style");
    style.textContent = CSS;
    document.head.appendChild(style);

    var root = h("div", { id: "nfsu-chat-root" });
    var btn = h("button", { id: "nfsu-chat-btn", title: "Library assistant", "aria-label": "Open library assistant" }, "\uD83D\uDCAC");
    var panel = h("div", { id: "nfsu-chat-panel", role: "dialog", "aria-label": "Library assistant" });
    var head = h("div", { class: "nfsu-head" });
    head.appendChild(h("span", null, "NFSU Library Assistant"));
    var close = h("button", { "aria-label": "Close" }, "\u00D7");
    head.appendChild(close);
    var log = h("div", { class: "nfsu-log" });
    var chips = h("div", { class: "nfsu-chips" });
    var inputRow = h("div", { class: "nfsu-input" });
    var input = h("input", { type: "text", placeholder: "Ask about books, journals, services\u2026", "aria-label": "Your question" });
    var send = h("button", null, "Send");
    inputRow.appendChild(input); inputRow.appendChild(send);
    panel.appendChild(head); panel.appendChild(log); panel.appendChild(chips); panel.appendChild(inputRow);
    root.appendChild(btn); root.appendChild(panel);
    document.body.appendChild(root);

    btn.onclick = function () { panel.classList.toggle("open"); if (panel.classList.contains("open")) input.focus(); };
    close.onclick = function () { panel.classList.remove("open"); };

    function addMessage(kind, text) {
      var m = h("div", { class: "nfsu-msg " + kind });
      m.appendChild(h("div", { class: "nfsu-bubble" }, text));
      log.appendChild(m);
      log.scrollTop = log.scrollHeight;
      return m;
    }

    function addResponse(resp) {
      var m = h("div", { class: "nfsu-msg bot" });
      var bubble = h("div", { class: "nfsu-bubble" });
      bubble.appendChild(document.createTextNode(resp.summary || ""));
      if (resp.links && resp.links.length) {
        var wrap = h("div", { class: "nfsu-links" });
        resp.links.forEach(function (l) {
          var item = h("div");
          item.appendChild(h("a", { href: l.url, target: "_blank", rel: "noopener" }, l.title));
          if (l.description) item.appendChild(h("div", { class: "desc" }, l.description));
          wrap.appendChild(item);
        });
        bubble.appendChild(wrap);
      }
      m.appendChild(bubble);
      log.appendChild(m);
      log.scrollTop = log.scrollHeight;

      chips.innerHTML = "";
      (resp.suggestions || []).forEach(function (s) {
        var c = h("button", { class: "nfsu-chip" }, s);
        c.onclick = function () { ask(s); };
        chips.appendChild(c);
      });
    }

    var busy = false;
    function ask(q) {
      q = (q || input.value || "").trim();
      if (!q || busy) return;
      input.value = "";
      addMessage("user", q);
      busy = true;
      var typing = addMessage("bot", "");
      typing.querySelector(".nfsu-bubble").innerHTML = '<span class="nfsu-typing">Searching the catalogue\u2026</span>';
      fetch(API_BASE + "/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q })
      })
        .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
        .then(function (data) { typing.remove(); addResponse(data); })
        .catch(function (err) {
          typing.remove();
          addMessage("bot", "Sorry, I couldn't reach the library service. Please try again. (" + err.message + ")");
        })
        .finally(function () { busy = false; });
    }

    send.onclick = function () { ask(); };
    input.addEventListener("keydown", function (e) { if (e.key === "Enter") ask(); });

    // Optional: respect a server-side enable/disable flag.
    fetch(API_BASE + "/api/config")
      .then(function (r) { return r.json(); })
      .then(function (cfg) {
        if (cfg && cfg.enabled === false) { root.style.display = "none"; return; }
        addMessage("bot", cfg.welcome_message || "Hello! How can I help you find library resources?");
        (cfg.suggested_questions || []).forEach(function (s) {
          var c = h("button", { class: "nfsu-chip" }, s);
          c.onclick = function () { ask(s); };
          chips.appendChild(c);
        });
      })
      .catch(function () { addMessage("bot", "Hello! Ask me to find books, journals or library information."); });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", inject);
  } else {
    inject();
  }
})();
