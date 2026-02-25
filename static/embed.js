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

  // Inject keyframe animations
  var styleSheet = document.createElement("style");
  styleSheet.textContent =
    "@keyframes ff-glow-pulse{0%,100%{box-shadow:0 0 8px 2px rgba(149,128,214,0.4),0 4px 16px rgba(149,128,214,0.3)}50%{box-shadow:0 0 20px 8px rgba(149,128,214,0.6),0 4px 24px rgba(149,128,214,0.4)}}" +
    "@keyframes ff-bounce-in{0%{transform:scale(0.3);opacity:0}50%{transform:scale(1.08)}100%{transform:scale(1);opacity:1}}";
  document.head.appendChild(styleSheet);

  // Chat bubble SVG icon
  var chatIcon = '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">' +
    '<path d="M12 2C6.48 2 2 5.92 2 10.67c0 2.73 1.53 5.15 3.92 6.7L4.5 21.5l4.58-2.29C10 19.73 10.98 20 12 20c5.52 0 10-3.58 10-8s-4.48-8-10-8z" fill="white"/>' +
    '<circle cx="8.5" cy="11" r="1.2" fill="#9580D6"/><circle cx="12" cy="11" r="1.2" fill="#9580D6"/><circle cx="15.5" cy="11" r="1.2" fill="#9580D6"/>' +
    '</svg>';
  var closeIcon = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">' +
    '<path d="M18 6L6 18M6 6l12 12" stroke="white" stroke-width="2.5" stroke-linecap="round"/>' +
    '</svg>';

  // Create toggle button
  var btn = document.createElement("div");
  btn.id = "ff-chat-toggle";
  btn.innerHTML = chatIcon;
  btn.title = "Chat with us";
  btn.style.cssText =
    "position:fixed;bottom:24px;right:24px;width:60px;height:60px;border-radius:50%;" +
    "background:linear-gradient(135deg,#9580D6 0%,#7A68B8 100%);color:#fff;display:flex;align-items:center;" +
    "justify-content:center;cursor:pointer;z-index:99999;transition:transform 0.2s;" +
    "animation:ff-glow-pulse 2.5s ease-in-out infinite,ff-bounce-in 0.5s ease-out;" +
    "border:2px solid rgba(255,255,255,0.25);";
  btn.onmouseover = function() { btn.style.transform = "scale(1.12)"; };
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
      btn.innerHTML = closeIcon;
      btn.style.animation = "none";
    } else {
      container.style.opacity = "0";
      container.style.transform = "translateY(16px)";
      setTimeout(function() { container.style.display = "none"; }, 200);
      btn.innerHTML = chatIcon;
      btn.style.animation = "ff-glow-pulse 2.5s ease-in-out infinite";
    }
  };

  // Mobile responsive: full screen on small screens
  if (window.innerWidth <= 480) {
    container.style.cssText =
      "position:fixed;top:0;left:0;width:100vw;height:100vh;border-radius:0;" +
      "z-index:99998;display:none;opacity:0;transition:opacity 0.2s;";
  }
})();
