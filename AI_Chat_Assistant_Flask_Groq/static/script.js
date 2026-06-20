document.addEventListener("DOMContentLoaded", function () {
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const chatHistory = document.getElementById("chat-history");
  const clearBtn = document.getElementById("clear-btn");

  marked.setOptions({
    breaks: true,
    gfm: true,
  });

  let messages = JSON.parse(sessionStorage.getItem("chat_history")) || [];

  if (messages.length > 0) {
    chatHistory.innerHTML = "";
    messages.forEach((msg) => appendMessageUI(msg.role, msg.content));
    scrollToBottom();
  }

  // Dynamic Auto-grow textarea handler
  chatInput.addEventListener("input", function () {
    this.style.height = "auto";
    this.style.height = this.scrollHeight - 4 + "px";
  });

  // Handle keystroke routing inside input workspace
  chatInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      chatForm.requestSubmit();
    }
  });

  // User Action: Reset and clear the UI context framework
  clearBtn.addEventListener("click", function () {
    sessionStorage.removeItem("chat_history");
    messages = [];
    chatHistory.innerHTML = `
      <div class="placeholder-container" id="chat-placeholder">
        <p class="fs-3 fw-bold mb-2" style="color: #312e81;">👋 Welcome back!</p>
        <p class="small mb-1 fw-medium">Send a message to start a contextual workspace session.</p>
        <p class="small opacity-75">Note: Closing or resetting the app tab clears transient memory.</p>
      </div>`;
    chatInput.style.height = "auto";
  });

  chatForm.addEventListener("submit", async function (e) {
    e.preventDefault();

    const userText = chatInput.value.trim();
    if (!userText) return;

    chatInput.value = "";
    chatInput.style.height = "auto";

    if (messages.length === 0) {
      chatHistory.innerHTML = "";
    }

    messages.push({ role: "user", content: userText });
    appendMessageUI("user", userText);
    scrollToBottom();

    const typingIndicator = appendMessageUI("assistant", "Thinking... 🤖");
    scrollToBottom();

    try {
      const response = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: messages }),
      });

      const data = await response.json();

      if (typingIndicator) typingIndicator.remove();

      if (data.response) {
        messages.push({ role: "assistant", content: data.response });
        appendMessageUI("assistant", data.response);
        sessionStorage.setItem("chat_history", JSON.stringify(messages));
      } else {
        appendMessageUI(
          "assistant",
          `⚠️ Error: ${data.error || "Unknown operational fault"}`,
        );
      }
    } catch (err) {
      if (typingIndicator) typingIndicator.remove();
      appendMessageUI("assistant", `⚠️ Network error: ${err.message}`);
    }

    scrollToBottom();
  });

  function appendMessageUI(role, content) {
    const wrapper = document.createElement("div");
    wrapper.classList.add("message-wrapper");

    const bubble = document.createElement("div");
    bubble.classList.add("msg-bubble");

    if (role === "user") {
      wrapper.classList.add("user-wrapper");
      bubble.classList.add("msg-user");
      bubble.textContent = content;
    } else {
      wrapper.classList.add("ai-wrapper");
      bubble.classList.add("msg-ai");

      if (content === "Thinking... 🤖") {
        bubble.textContent = content;
      } else {
        bubble.innerHTML = marked.parse(content);
      }
    }

    wrapper.appendChild(bubble);
    chatHistory.appendChild(wrapper);
    return wrapper;
  }

  function scrollToBottom() {
    chatHistory.scrollTop = chatHistory.scrollHeight;
  }
});
