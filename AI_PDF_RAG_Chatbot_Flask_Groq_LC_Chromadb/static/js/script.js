async function uploadPDF() {
  let files = document.getElementById("pdf").files;

  if (files.length === 0) {
    Swal.fire({
      icon: "warning",
      title: "No PDF Selected",
      text: "Please choose PDF files first.",
    });

    return;
  }

  let formData = new FormData();
  for (let file of files) {
    formData.append("files", file);
  }

  Swal.fire({
    title: "Uploading PDF(s)...",
    text: "Please wait",
    allowOutsideClick: false,
    didOpen: () => {
      Swal.showLoading();
    },
  });

  try {
    let response = await fetch("/upload", {
      method: "POST",
      body: formData,
    });

    let data = await response.json();

    Swal.close();

    if (data.message) {
      Swal.fire({
        icon: "success",
        title: "PDF(s) Uploaded Successfully",
        text: "You can now ask questions.",
        confirmButtonText: "OK",
      });
    } else {
      Swal.fire({
        icon: "error",
        title: "Upload Failed",
        text: data.error,
      });
    }
  } catch (error) {
    Swal.fire({
      icon: "error",
      title: "Error",
      text: "Something went wrong.",
    });
  }
}

function handleEnter(event) {
  if (event.key === "Enter") {
    askQuestion();
  }
}

async function askQuestion() {
  let input = document.getElementById("question");

  let question = input.value.trim();

  if (!question) return;

  let chat = document.getElementById("chat");

  chat.innerHTML += `
        <div class="message user">
            ${question}
        </div>
    `;

  input.value = "";

  let loader = document.createElement("div");

  loader.className = "typing";

  loader.innerHTML = `
        <span></span>
        <span></span>
        <span></span>
    `;

  chat.appendChild(loader);

  chat.scrollTop = chat.scrollHeight;

  try {
    let response = await fetch("/ask", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        question: question,
      }),
    });

    let data = await response.json();

    loader.remove();

    chat.innerHTML += `
            <div class="message bot">
                ${data.answer}
            </div>
        `;

    chat.scrollTop = chat.scrollHeight;
  } catch (error) {
    loader.remove();

    chat.innerHTML += `
            <div class="message bot">
                Error fetching answer.
            </div>
        `;
  }
}

document.getElementById("pdf").addEventListener("change", function () {
  const count = this.files.length;

  const fileCount = document.getElementById("file-count");

  if (count === 0) {
    fileCount.innerText = "No files selected";
  } else if (count === 1) {
    fileCount.innerText = this.files[0].name;
  } else {
    fileCount.innerText = `${count} PDF files selected`;
  }
});
