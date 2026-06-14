const messages = document.getElementById("messages");

function addMessage(content, cls) {
  const div = document.createElement("div");
  div.className = cls;
  div.innerHTML = content;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
}

async function sendMessage() {
  const name = document.getElementById("customerName").value.trim();
  const message = document.getElementById("message").value.trim();

  if (!name) return showToast("Please enter your name");
  if (!message) return showToast("Please enter a message");

  addMessage(message, "user");

  document.getElementById("message").value = "";

  // loading
  addMessage(
    `
    <div class="typing">🤖 Agents are processing your request...</div>
  `,
    "bot",
  );

  const res = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, message }),
  });

  const data = await res.json();

  document.querySelector(".typing")?.parentElement?.remove();

  const agentBlock = `
    <div class="meta">

      🎫 <b>${data.ticket_id}</b><br>

      🧠 <span class="${data.department?.toLowerCase()}">
        ${data.department}
      </span>

      |

      ⚡ <span class="${data.priority}">
        ${data.priority}
      </span>

      |

      😊 ${data.sentiment}

      ${data.escalation ? `<br><span class="High">🚨 Escalated</span>` : ""}

    </div>

    <details>
      <summary>🧠 View Agent Analysis</summary>

      <pre style="white-space:pre-wrap;color:#cbd5e1;font-size:12px;">
TECH:
${data.tech_response || ""}

BILLING:
${data.billing_response || ""}

SALES:
${data.sales_response || ""}

REVIEWER:
${data.reviewer_response || ""}
      </pre>
    </details>

    <hr style="margin:10px 0;border:0;border-top:1px solid rgba(255,255,255,0.1)"/>

    <div>${data.response.replace(/\n/g, "<br>")}</div>
  `;

  addMessage(agentBlock, "bot");
}

document.getElementById("message").addEventListener("keypress", (e) => {
  if (e.key === "Enter") sendMessage();
});

function showToast(msg) {
  const toast = document.getElementById("toast");
  toast.textContent = msg;
  toast.classList.add("show");

  setTimeout(() => toast.classList.remove("show"), 3000);
}
