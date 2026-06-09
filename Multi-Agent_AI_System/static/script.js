let selectedAgent = "research";

const cards = document.querySelectorAll(".agent-card");

cards.forEach((card) => {
  card.addEventListener("click", () => {
    cards.forEach((c) => c.classList.remove("active"));

    card.classList.add("active");

    selectedAgent = card.dataset.agent;
  });
});

document.getElementById("query").addEventListener("keydown", function (e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();

    runAgent();
  }
});

async function runAgent() {
  const query = document.getElementById("query").value.trim();

  const output = document.getElementById("output");

  const btn = document.getElementById("generateBtn");

  if (!query) {
    output.innerHTML = `
        <div class="error-message">
            ⚠️ Please enter a prompt before generating a response.
        </div>
        `;

    return;
  }

  btn.disabled = true;
  btn.innerText = "Generating...";

  output.innerHTML = `
    <div class="thinking">
        ⚡ Thinking...
    </div>
    `;

  try {
    const response = await fetch("/run_agent", {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify({
        agent: selectedAgent,
        query: query,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      output.innerHTML = `
            <div class="error-message">
                ${data.error}
            </div>
            `;

      return;
    }

    output.innerHTML = `
        <div class="response">
            ${marked.parse(data.result.trim())}
        </div>
        `;
  } catch (error) {
    console.error(error);

    output.innerHTML = `
        <div class="error-message">
            Server Error. Please try again.
        </div>
        `;
  } finally {
    btn.disabled = false;

    btn.innerText = "Generate Response";
  }
}
