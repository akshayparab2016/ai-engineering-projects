function setLoading(isLoading) {
  const btn = document.getElementById("startBtn");
  const input = document.getElementById("topic");
  btn.disabled = isLoading;
  input.disabled = isLoading;
  btn.innerText = isLoading ? "Debating..." : "Start Debate";
}

function startDebate() {
  const topic = document.getElementById("topic").value.trim();
  if (!topic) return;

  const boxes = {
    pro: document.getElementById("pro"),
    opp: document.getElementById("opp"),
    judge: document.getElementById("judge"),
  };

  // Clear previous data and remove any active states
  Object.keys(boxes).forEach((key) => {
    boxes[key].innerHTML = "";
    boxes[key].parentElement.classList.remove("active"); // Remove active glow
  });

  const buffers = { pro: "", opp: "", judge: "" };
  const bubbles = { pro: null, opp: null, judge: null };

  // Helper to create or get the indicator container
  function toggleIndicator(role, show) {
    const panel = boxes[role];
    let indicator = panel.querySelector(".typing-indicator");

    if (show && !indicator) {
      indicator = document.createElement("div");
      indicator.className = `typing-indicator ${role}-bubble`;
      indicator.innerHTML = "<span></span><span></span><span></span>";
      panel.appendChild(indicator);
    } else if (!show && indicator) {
      indicator.remove();
    }
  }

  function getBubble(role) {
    if (!bubbles[role]) {
      // Highlight the active generating panel card visually
      Object.keys(boxes).forEach((k) =>
        boxes[k].parentElement.classList.remove("active"),
      );
      boxes[role].parentElement.classList.add("active");

      const div = document.createElement("div");
      div.className = `bubble ${role}-bubble`;
      boxes[role].appendChild(div);
      bubbles[role] = div;
    }
    return bubbles[role];
  }

  function renderRole(role) {
    // Hide loading indicator as soon as content begins painting down the DOM
    toggleIndicator(role, false);

    const bubble = getBubble(role);
    bubble.innerHTML = marked.parse(buffers[role]);
    boxes[role].scrollTop = boxes[role].scrollHeight;
  }

  setLoading(true);

  // Put a waiting state indicator on the primary starting panels immediately
  toggleIndicator("pro", true);
  boxes["pro"].parentElement.classList.add("active");

  const es = new EventSource(`/stream?topic=${encodeURIComponent(topic)}`);

  es.onmessage = (event) => {
    if (event.data === "[DONE]") {
      es.close();
      setLoading(false);
      // Strip remaining glows when debate ends completely
      Object.keys(boxes).forEach((k) =>
        boxes[k].parentElement.classList.remove("active"),
      );
      return;
    }

    let data;
    try {
      data = JSON.parse(event.data);
    } catch (e) {
      return;
    }

    const { role, text } = data;
    if (!role || !(role in buffers)) return;

    // Show indicator on targeted box if it transitions to a new agent
    if (buffers[role] === "") {
      Object.keys(boxes).forEach((k) => {
        boxes[k].parentElement.classList.remove("active");
        toggleIndicator(k, false);
      });
      toggleIndicator(role, true);
      boxes[role].parentElement.classList.add("active");
    }

    buffers[role] += text || "";
    renderRole(role);
  };

  es.onerror = () => {
    es.close();
    setLoading(false);
    Object.keys(boxes).forEach((k) =>
      boxes[k].parentElement.classList.remove("active"),
    );
  };
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("startBtn").addEventListener("click", startDebate);
  document.getElementById("topic").addEventListener("keydown", (e) => {
    if (e.key === "Enter") startDebate();
  });
});
