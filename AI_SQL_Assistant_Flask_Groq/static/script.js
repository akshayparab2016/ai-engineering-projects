// ======================================
// ELEMENTS
// ======================================

const chatContainer = document.getElementById("chat-container");

const historyContainer = document.getElementById("history");

const schemaContainer = document.getElementById("schema-container");

const dbFileInput = document.getElementById("db-file");

const uploadBtn = document.getElementById("upload-btn");

const dropZone = document.getElementById("drop-zone");

const refreshBtn = document.getElementById("refresh-schema");

const loadingOverlay = document.getElementById("loading-overlay");

const activeDatabase = document.getElementById("active-database");

const questionInput = document.getElementById("question");

// ======================================
// INIT
// ======================================

window.addEventListener("DOMContentLoaded", async () => {
  await loadDatabaseInfo();
  await loadSchema();
  setupExamplePrompts();
});

// ======================================
// DATABASE INFO
// ======================================

async function loadDatabaseInfo() {
  try {
    const response = await fetch("/database-info");

    const data = await response.json();

    if (data.success) {
      activeDatabase.textContent = data.database;
    } else {
      activeDatabase.textContent = "No Database Uploaded";
    }
  } catch (error) {
    console.error(error);
  }
}

// ======================================
// SCHEMA
// ======================================

async function loadSchema() {
  try {
    const response = await fetch("/schema");

    const data = await response.json();

    if (!data.success) {
      schemaContainer.innerHTML = `
        <div class="empty-state-small">
            Upload a database first
        </div>
      `;
      return;
    }

    renderSchema(data.schema);
  } catch (error) {
    schemaContainer.innerHTML = `
      <div class="empty-state-small">
        No schema available
      </div>
    `;

    console.error(error);
  }
}

function renderSchema(schema) {
  schemaContainer.innerHTML = "";

  const tables = Object.keys(schema);

  if (tables.length === 0) {
    schemaContainer.innerHTML = `
      <div class="empty-state-small">
          No tables found
      </div>
    `;

    return;
  }

  tables.forEach((tableName) => {
    const tableInfo = schema[tableName];

    const card = document.createElement("div");

    card.className = "schema-card";

    let columnsHTML = "";

    tableInfo.columns.forEach((col) => {
      columnsHTML += `
        <div class="column-item">

            <div class="column-name">
                ${col[1]}
            </div>

            <div class="column-type">
                ${col[2]}
            </div>

        </div>
      `;
    });

    card.innerHTML = `
      <div class="table-header">

          <div class="table-name">
              ${tableName}
          </div>

          <div class="table-badge">
              ${tableInfo.rows} rows
          </div>

      </div>

      <div class="columns-container">
          ${columnsHTML}
      </div>
    `;

    schemaContainer.appendChild(card);
  });
}

// ======================================
// FILE UPLOAD
// ======================================

uploadBtn.addEventListener("click", () => {
  dbFileInput.click();
});

dbFileInput.addEventListener("change", async (e) => {
  if (!e.target.files.length) return;

  await uploadDatabase(e.target.files[0]);
});

async function uploadDatabase(file) {
  const formData = new FormData();

  formData.append("file", file);

  loadingOverlay.classList.remove("hidden");

  try {
    const response = await fetch("/upload-db", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();

    if (data.success) {
      activeDatabase.textContent = data.database;

      await loadSchema();

      addSystemMessage(`Database "${data.database}" uploaded successfully`);
    } else {
      alert(data.error);
    }
  } catch (error) {
    console.error(error);

    alert("Upload failed");
  }

  loadingOverlay.classList.add("hidden");
}

// ======================================
// DRAG DROP
// ======================================

dropZone.addEventListener("click", () => {
  dbFileInput.click();
});

dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();

  dropZone.classList.add("dragover");
});

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("dragover");
});

dropZone.addEventListener("drop", async (e) => {
  e.preventDefault();

  dropZone.classList.remove("dragover");

  const file = e.dataTransfer.files[0];

  if (!file) return;

  await uploadDatabase(file);
});

// ======================================
// REFRESH SCHEMA
// ======================================

refreshBtn.addEventListener("click", async () => {
  refreshBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';

  await loadSchema();

  refreshBtn.innerHTML = '<i class="fa-solid fa-rotate"></i>';
});

// ======================================
// CHAT
// ======================================

function showLoading() {
  return `
    <div
      class="ai-message"
      id="loading-message">

      Generating SQL...

    </div>
  `;
}

async function askAI() {
  const question = questionInput.value.trim();

  if (!question) return;

  hideWelcomeCard();

  addUserMessage(question);

  addHistoryItem(question);

  chatContainer.innerHTML += showLoading();

  scrollToBottom();

  questionInput.value = "";

  try {
    const response = await fetch("/ask", {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify({
        question,
      }),
    });

    const data = await response.json();

    document.getElementById("loading-message")?.remove();

    if (data.success) {
      renderAIResponse(data);
    } else {
      addErrorMessage(data.error);
    }
  } catch (error) {
    document.getElementById("loading-message")?.remove();

    addErrorMessage(error.message);
  }

  scrollToBottom();
}

// ======================================
// AI RESPONSE
// ======================================

function renderAIResponse(data) {
  let tableHTML = `
    <table>
      <thead>
        <tr>
  `;

  data.columns.forEach((col) => {
    tableHTML += `
      <th>${col}</th>
    `;
  });

  tableHTML += `
      </tr>
    </thead>
    <tbody>
  `;

  data.data.forEach((row) => {
    tableHTML += "<tr>";

    row.forEach((cell) => {
      tableHTML += `
        <td>${cell}</td>
      `;
    });

    tableHTML += "</tr>";
  });

  tableHTML += `
      </tbody>
    </table>
  `;

  chatContainer.innerHTML += `
    <div class="ai-message">

      <h3>
        Generated SQL
      </h3>

      <div class="sql-code">
        ${escapeHtml(data.sql)}
      </div>

      <div class="result-table">
        ${tableHTML}
      </div>

      <br>

      <small>
        ${data.rows} rows returned
      </small>

    </div>
  `;
}

// ======================================
// CHAT HELPERS
// ======================================

function addUserMessage(text) {
  chatContainer.innerHTML += `
    <div class="user-message">
      ${escapeHtml(text)}
    </div>
  `;
}

function addErrorMessage(text) {
  chatContainer.innerHTML += `
    <div class="ai-message">

      ❌ ${escapeHtml(text)}

    </div>
  `;
}

function addSystemMessage(text) {
  chatContainer.innerHTML += `
    <div class="ai-message">

      ✅ ${escapeHtml(text)}

    </div>
  `;

  scrollToBottom();
}

function hideWelcomeCard() {
  const welcomeCard = document.getElementById("welcome-card");

  if (welcomeCard) {
    welcomeCard.remove();
  }
}

function scrollToBottom() {
  chatContainer.scrollTop = chatContainer.scrollHeight;
}

// ======================================
// HISTORY
// ======================================

function addHistoryItem(question) {
  const item = document.createElement("div");

  item.className = "history-item";

  item.textContent = question;

  item.addEventListener("click", () => {
    questionInput.value = question;

    questionInput.focus();
  });

  historyContainer.prepend(item);
}

// ======================================
// PROMPTS
// ======================================

function setupExamplePrompts() {
  document.querySelectorAll(".example-card").forEach((card) => {
    card.addEventListener("click", () => {
      questionInput.value = card.innerText.trim();

      questionInput.focus();
    });
  });
}

// ======================================
// ENTER KEY
// ======================================

questionInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();

    askAI();
  }
});

// ======================================
// SECURITY
// ======================================

function escapeHtml(text) {
  const div = document.createElement("div");

  div.textContent = text;

  return div.innerHTML;
}

window.addEventListener("DOMContentLoaded", () => {
  document.getElementById("question").value = "";
});

document
  .getElementById("deactivate-btn")
  .addEventListener("click", async () => {
    const res = await fetch("/deactivate-db", { method: "POST" });
    const data = await res.json();

    if (data.success) {
      activeDatabase.textContent = "No Database Active";
      chatContainer.innerHTML = "";
      historyContainer.innerHTML = "";

      schemaContainer.innerHTML = `
        <div class="empty-state-small">
          Upload a database
        </div>
      `;

      alert(data.message);
    } else {
      alert(data.message); // 👈 shows "No active database..."
    }
  });
