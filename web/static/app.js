(function () {
  const LOADING_DEFAULT = "Working…";

  const LOADING_LABELS = {
    "Try combination": "Trying combination…",
    "Interpret idea": "Interpreting…",
    "Build it": "Building…",
    "Learn this method": "Learning…",
    "Try building anyway": "Building…",
    "Keep object": "Saving…",
    "Keep component": "Saving…",
    "Advance turn": "Advancing turn…",
    "Survey the cave": "Surveying…",
    "Enter the cave": "Entering…",
    Search: "Searching…",
    Rename: "Saving…",
    Continue: "Loading…",
  };

  const statusBar = document.getElementById("status-bar");

  function loadingLabel(button) {
    if (button.dataset.loadingText) {
      return button.dataset.loadingText;
    }
    const text = (button.textContent || "").trim();
    return LOADING_LABELS[text] || LOADING_DEFAULT;
  }

  function setStatus(message) {
    if (!statusBar) return;
    if (message) {
      statusBar.textContent = message;
      statusBar.classList.add("is-visible");
      document.body.classList.add("has-status-bar");
    } else {
      statusBar.classList.remove("is-visible");
      document.body.classList.remove("has-status-bar");
    }
  }

  function markFeedbackFresh() {
    document.querySelectorAll(".feedback-recent").forEach((el) => {
      el.classList.add("feedback-flash");
      if (el.querySelector(".feedback-time")) return;
      const time = document.createElement("p");
      time.className = "feedback-time muted";
      time.textContent = "Just now";
      el.insertBefore(time, el.firstChild);
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    markFeedbackFresh();
    if (document.querySelector(".feedback-recent")) {
      setStatus("Updated");
      window.setTimeout(() => setStatus(""), 2500);
    }
  });

  document.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", () => {
      const btn = form.querySelector(
        'button[type="submit"]:not([disabled]), input[type="submit"]:not([disabled])'
      );
      const label = btn ? loadingLabel(btn) : LOADING_DEFAULT;

      if (btn) {
        btn.dataset.originalText = btn.textContent;
        btn.textContent = label;
        btn.disabled = true;
        btn.classList.add("is-loading");
      }

      document.querySelectorAll(".feedback-recent").forEach((el) => {
        el.classList.add("is-stale");
      });

      document.body.classList.add("is-waiting");
      setStatus(label);
    });
  });
})();
