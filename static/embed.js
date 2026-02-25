/**
 * ForeverFurEver Chat Widget - Embeddable Script
 *
 * Usage: Add this to your Shopify theme or any website:
 *   <script src="https://foreverfurever-agent.onrender.com/static/embed.js"></script>
 *
 * Optional: Set FOREVERFUREVER_AGENT_URL before loading the script to use a custom server.
 */
(function() {
  var AGENT_URL = window.FOREVERFUREVER_AGENT_URL || "https://foreverfurever-agent.onrender.com";

  // Prevent double-loading
  if (document.getElementById("ff-chat-widget")) return;

  // Create toggle button
  var btn = document.createElement("div");
  btn.id = "ff-chat-toggle";
  btn.innerHTML = "&#10054;";
  btn.title = "Chat with us";
  btn.style.cssText =
    "position:fixed;bottom:24px;right:24px;width:56px;height:56px;border-radius:50%;" +
    "background:#9580D6;color:#fff;font-size:24px;display:flex;align-items:center;" +
    "justify-content:center;cursor:pointer;box-shadow:0 4px 16px rgba(149,128,214,0.4);" +
    "z-index:99999;transition:transform 0.2s;font-family:sans-serif;";
  btn.onmouseover = function() { btn.style.transform = "scale(1.1)"; };
  btn.onmouseout = function() { btn.style.transform = "scale(1)"; };

  // Create iframe container
  var container = document.createElement("div");
  container.id = "ff-chat-widget";
  container.style.cssText =
    "position:fixed;bottom:92px;right:24px;width:400px;height:600px;max-width:calc(100vw - 32px);" +
    "max-height:calc(100vh - 120px);border-radius:16px;overflow:hidden;" +
    "box-shadow:0 8px 32px rgba(0,0,0,0.15);z-index:99998;display:none;" +
    "transition:opacity 0.2s,transform 0.2s;opacity:0;transform:translateY(16px);";

  var iframe = document.createElement("iframe");
  iframe.style.cssText = "width:100%;height:100%;border:none;";
  iframe.title = "ForeverFurEver Chat";

  container.appendChild(iframe);
  document.body.appendChild(container);
  document.body.appendChild(btn);

  var open = false;

  btn.onclick = function() {
    open = !open;
    if (open) {
      // Lazy load iframe on first open
      if (!iframe.src) {
        iframe.src = AGENT_URL;
      }
      container.style.display = "block";
      // Trigger reflow for transition
      container.offsetHeight;
      container.style.opacity = "1";
      container.style.transform = "translateY(0)";
      btn.innerHTML = "&#10005;";
    } else {
      container.style.opacity = "0";
      container.style.transform = "translateY(16px)";
      setTimeout(function() { container.style.display = "none"; }, 200);
      btn.innerHTML = "&#10054;";
    }
  };

  // Mobile responsive: full screen on small screens
  if (window.innerWidth <= 480) {
    container.style.cssText =
      "position:fixed;top:0;left:0;width:100vw;height:100vh;border-radius:0;" +
      "z-index:99998;display:none;opacity:0;transition:opacity 0.2s;";
  }
})();
