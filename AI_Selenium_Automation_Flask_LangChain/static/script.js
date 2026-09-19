document.addEventListener("DOMContentLoaded", () => {
  const $ = (id) => document.getElementById(id);

  const runButton = $("runButton");
  const stopButton = $("stopButton");
  const runPlanButton = $("runPlanButton");
  const downloadButton = $("downloadButton");
  const btnSpinner = $("btnSpinner");
  const btnText = runButton.querySelector(".btn-text");
  const instructionInput = $("instruction");
  const charCount = $("charCount");
  const resultMessage = $("resultMessage");
  const pythonCode = $("pythonCode");
  const pythonWrapper = $("pythonWrapper");
  const aiResult = $("aiResult");
  const statusBadge = $("statusBadge");
  const progress = $("progress");
  const progressBar = $("progressBar");
  const extractedSection = $("extractedSection");
  const extractedOutput = $("extractedOutput");

  const CODE_PLACEHOLDER = "# Python automation code will appear here...";

  let controller = null; // AbortController for the run in progress
  let runFinished = false; // true once the server sent "completed" or "error"
  let extractedBlocks = [];
  let generatedCode = "";
  let typingToken = 0; // bumps to cancel a "typing" animation in progress

  /* ---------------------------------------------------------------- UI state */

  function setStatus(state, label) {
    statusBadge.className = "status-badge " + state;
    statusBadge.textContent = label;
  }

  function setMessage(text, tone = "") {
    resultMessage.className = "result-message" + (tone ? " " + tone : "");
    resultMessage.textContent = text;
  }

  function setProgress(done, total, tone = "") {
    const pct = total ? Math.round((done / total) * 100) : 0;
    progressBar.style.width = pct + "%";
    progress.setAttribute("aria-valuenow", String(pct));
    progress.className = "progress" + (tone ? " " + tone : "");
  }

  function syncPlanButton() {
    runPlanButton.disabled = Boolean(controller) || !aiResult.value.trim();
  }

  function setLoadingState(isLoading) {
    runButton.disabled = isLoading;
    stopButton.hidden = !isLoading;
    btnSpinner.style.display = isLoading ? "inline-block" : "none";
    btnText.textContent = isLoading ? "Running..." : "Execute automation";
    syncPlanButton();
  }

  function resetWorkspace(keepPlan) {
    setProgress(0, 0);
    typingToken++;
    extractedBlocks = [];
    extractedOutput.textContent = "";
    extractedSection.hidden = true;

    if (!keepPlan) {
      generatedCode = "";
      pythonCode.textContent = "# Waiting for the action plan...";
      aiResult.value = "";
    }
  }

  /* ---------------------------------------------------------- Live writing */

  // Types text into a <code> element in quick bursts so the script appears to be written live.
  function typeInto(element, scroller, text) {
    const token = ++typingToken;
    const burst = Math.max(6, Math.ceil(text.length / 80));
    let pos = 0;
    element.textContent = "";

    function tick() {
      if (token !== typingToken) return; // cancelled by a new run
      pos = Math.min(text.length, pos + burst);
      element.textContent = text.slice(0, pos);
      scroller.scrollTop = scroller.scrollHeight;
      if (pos < text.length) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  // Appends a piece of raw model output to the JSON pane while the AI is still writing.
  function appendPlanChunk(text) {
    aiResult.value += text;
    aiResult.scrollTop = aiResult.scrollHeight;
  }

  function addExtracted(data) {
    const items = (data.extracted || []).map((text, i) => `${i + 1}. ${text.replace(/\s+/g, " ")}`);
    if (!items.length) return;

    const heading = `Step ${data.step_index}` + (data.selector ? ` (${data.selector})` : "");
    extractedBlocks.push(`${heading}\n${items.join("\n")}`);
    extractedOutput.textContent = extractedBlocks.join("\n\n");
    extractedSection.hidden = false;
  }

  /* ---------------------------------------------------------- Stream events */

  function handleEvent(data) {
    switch (data.status) {
      case "planning":
        setStatus("running", "Planning");
        setMessage(data.message);
        aiResult.readOnly = true; // no editing while the AI is writing
        break;

      case "plan_chunk":
        appendPlanChunk(data.text);
        break;

      case "plan_retry":
        aiResult.value = "";
        setMessage(data.message);
        break;

      case "initialized":
        aiResult.readOnly = false;
        generatedCode = data.python_code || "";
        aiResult.value = JSON.stringify(data.ai_result, null, 2);
        aiResult.scrollTop = 0;
        typeInto(pythonCode, pythonWrapper, generatedCode || "# No code generated.");
        setStatus("running", "Running");
        setMessage("Action plan ready. Launching the browser...");
        syncPlanButton();
        break;

      case "browser_starting":
        setStatus("running", "Running");
        setMessage(data.message);
        break;

      case "step_start":
        setMessage("Automation is running in the browser...");
        break;

      case "step_done":
        setProgress(data.step_index, data.total_steps);
        addExtracted(data);
        break;

      case "completed": {
        runFinished = true;
        let summary = "Automation completed successfully. The browser session has been closed.";
        if (extractedBlocks.length) summary += " The text it collected is shown below.";
        setStatus("success", "Completed");
        setMessage(summary, "success");
        setProgress(data.total_steps, data.total_steps, "success");
        break;
      }

      case "error":
        runFinished = true;
        aiResult.readOnly = false;
        setStatus("error", "Failed");
        setMessage(data.message, "error");
        progress.className = "progress error";
        break;
    }
  }

  async function streamRequest(url, payload, signal) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal,
    });

    if (!response.ok || !response.body) {
      throw new Error(`Server returned status ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Server-Sent Events are separated by a blank line.
      const events = buffer.split("\n\n");
      buffer = events.pop(); // keep the incomplete tail

      for (const raw of events) {
        const line = raw.split("\n").find((l) => l.startsWith("data:"));
        if (!line) continue;

        let data;
        try {
          data = JSON.parse(line.slice(5).trim());
        } catch (err) {
          console.warn("Skipped invalid JSON chunk from stream:", line);
          continue;
        }
        handleEvent(data);
      }
    }
  }

  async function startRun(url, payload, { keepPlan = false, startMessage = "" } = {}) {
    if (controller) return;

    controller = new AbortController();
    runFinished = false;
    resetWorkspace(keepPlan);
    setLoadingState(true);
    setStatus("running", "Running");
    setMessage(startMessage);

    try {
      await streamRequest(url, payload, controller.signal);
      if (!runFinished) {
        setStatus("error", "Failed");
        setMessage("The connection to the server was lost before the automation finished. Please try again.", "error");
      }
    } catch (error) {
      if (error.name === "AbortError") {
        setStatus("stopped", "Stopped");
        setMessage("Automation stopped. The browser will close as soon as the current action finishes.");
        progress.className = "progress";
      } else {
        setStatus("error", "Error");
        setMessage("Could not reach the server: " + error.message, "error");
      }
    } finally {
      controller = null;
      aiResult.readOnly = false;
      setLoadingState(false);
    }
  }

  /* ---------------------------------------------------------------- Actions */

  function runInstruction() {
    if (controller) return;

    const instruction = instructionInput.value.trim();
    if (!instruction) {
      setStatus("error", "Error");
      setMessage("Please describe what the browser should do before running the automation.", "error");
      return;
    }

    startRun("/automate-stream", { instruction }, { startMessage: "Initiating automation..." });
  }

  function runEditedPlan() {
    if (controller) return;

    let steps;
    try {
      steps = JSON.parse(aiResult.value);
    } catch (err) {
      setStatus("error", "Invalid JSON");
      setMessage("The action plan is not valid JSON, so it was not run. " + err.message, "error");
      return;
    }

    startRun("/run-plan", { steps }, { keepPlan: true, startMessage: "Initiating automation..." });
  }

  runButton.addEventListener("click", runInstruction);
  runPlanButton.addEventListener("click", runEditedPlan);
  stopButton.addEventListener("click", () => controller && controller.abort());
  aiResult.addEventListener("input", syncPlanButton);

  instructionInput.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      runInstruction();
    }
  });

  instructionInput.addEventListener("input", updateCharCount);

  function updateCharCount() {
    charCount.textContent = `${instructionInput.value.length} / ${instructionInput.maxLength}`;
  }

  /* ------------------------------------------------------------- Presets */

  function setInstruction(text) {
    instructionInput.value = text;
    updateCharCount();
    instructionInput.focus();
  }

  document.querySelectorAll(".chip-btn").forEach((chip) => {
    chip.addEventListener("click", () => setInstruction(chip.getAttribute("data-text")));
  });

  /* ----------------------------------------------------- Copy and download */

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (err) {
      const helper = document.createElement("textarea");
      helper.value = text;
      helper.style.position = "fixed";
      helper.style.opacity = "0";
      document.body.appendChild(helper);
      helper.select();
      let ok = false;
      try {
        ok = document.execCommand("copy");
      } catch (e) {
        ok = false;
      }
      helper.remove();
      return ok;
    }
  }

  document.querySelectorAll(".copy-btn[data-target]").forEach((button) => {
    button.addEventListener("click", async () => {
      const target = $(button.dataset.target);
      const label = button.querySelector("span");
      if (!target || !label) return;

      if (!button.dataset.label) button.dataset.label = label.textContent;

      let text = "value" in target ? target.value : target.textContent;
      if (target === pythonCode && generatedCode) text = generatedCode; // full script, even mid-typing
      const ok = await copyText(text);

      label.textContent = ok ? "Copied" : "Copy failed";
      setTimeout(() => {
        label.textContent = button.dataset.label;
      }, 1500);
    });
  });

  downloadButton.addEventListener("click", () => {
    if (!generatedCode) {
      setMessage("There is no script to download yet. Run an automation first to generate one.");
      return;
    }

    const blob = new Blob([generatedCode], { type: "text/x-python" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "automation.py";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  });

  /* ------------------------------------------------------------------ Init */

  pythonCode.textContent = CODE_PLACEHOLDER;
  updateCharCount();
  syncPlanButton();
});
