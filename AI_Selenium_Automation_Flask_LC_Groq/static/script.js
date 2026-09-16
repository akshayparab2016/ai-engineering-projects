document.addEventListener("DOMContentLoaded", () => {
  const runButton = document.getElementById("runButton");
  const btnSpinner = document.getElementById("btnSpinner");
  const btnText = runButton.querySelector(".btn-text");
  const instructionInput = document.getElementById("instruction");
  const resultMessage = document.getElementById("resultMessage");
  const pythonCode = document.getElementById("pythonCode");
  const aiResult = document.getElementById("aiResult");
  const statusBadge = document.getElementById("statusBadge");
  const liveFeed = document.getElementById("liveFeed");
  const liveFeedPlaceholder = document.getElementById("liveFeedPlaceholder");
  const chipButtons = document.querySelectorAll(".chip-btn");

  chipButtons.forEach((chip) => {
    chip.addEventListener("click", () => {
      instructionInput.value = chip.getAttribute("data-text");
      instructionInput.focus();
    });
  });

  runButton.addEventListener("click", async function () {
    const instruction = instructionInput.value.trim();

    if (!instruction) {
      setStatus("error", "Error");
      resultMessage.textContent =
        "Please enter an instruction before executing automation.";
      return;
    }

    setLoadingState(true);
    setStatus("running", "Running...");
    resultMessage.textContent = "Generating automation plan...";
    pythonCode.textContent = "# Generating Python code...";
    aiResult.textContent = "// Waiting for AI model output...";
    liveFeed.style.display = "none";
    liveFeedPlaceholder.style.display = "flex";

    try {
      const response = await fetch("/automate-stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ instruction }),
      });

      if (!response.ok) {
        throw new Error(`Server returned status ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Split buffer by newline and process complete messages
        let lines = buffer.split("\n");
        buffer = lines.pop(); // Keep partial line in the buffer

        for (let line of lines) {
          line = line.trim();
          if (line.startsWith("data:")) {
            const rawJson = line.replace(/^data:\s*/, "");
            if (rawJson) {
              try {
                const data = JSON.parse(rawJson);
                handleStreamPayload(data);
              } catch (err) {
                console.warn(
                  "Skipped invalid JSON chunk from stream:",
                  rawJson,
                );
              }
            }
          }
        }
      }
    } catch (error) {
      setStatus("error", "Error");
      resultMessage.textContent = "Request Error: " + error.message;
    } finally {
      setLoadingState(false);
    }
  });

  function handleStreamPayload(data) {
    if (data.status === "initialized") {
      pythonCode.textContent = data.python_code || "# No code generated.";
      aiResult.textContent = JSON.stringify(data.ai_result, null, 4);
      resultMessage.textContent =
        "Action plan compiled. Initializing browser automation stream...";
    } else if (data.status === "in_progress") {
      resultMessage.textContent = data.message;
      updateScreenshot(data.screenshot);
    } else if (data.status === "completed") {
      setStatus("success", "Completed");
      resultMessage.textContent = data.message;
      updateScreenshot(data.screenshot);
    } else if (data.status === "error") {
      setStatus("error", "Failed");
      resultMessage.textContent = data.message;
      updateScreenshot(data.screenshot);
    }
  }

  function updateScreenshot(base64Image) {
    if (base64Image) {
      liveFeed.src = `data:image/png;base64,${base64Image}`;
      liveFeed.style.display = "block";
      liveFeedPlaceholder.style.display = "none";
    }
  }

  function setLoadingState(isLoading) {
    runButton.disabled = isLoading;
    btnSpinner.style.display = isLoading ? "inline-block" : "none";
    btnText.textContent = isLoading
      ? "Running Stream..."
      : "Execute Automation";
  }

  function setStatus(state, label) {
    statusBadge.className = "status-badge " + state;
    statusBadge.textContent = label;
  }
});
