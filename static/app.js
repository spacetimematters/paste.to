const urlInput = document.getElementById("url");
const goBtn = document.getElementById("go");
const status = document.getElementById("status");
const result = document.getElementById("result");
const resultLink = document.getElementById("result-link");
const modeButtons = document.querySelectorAll(".mode");

let currentMode = "video";

// Mode toggle
modeButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    modeButtons.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    currentMode = btn.dataset.mode;
  });
});

// Enable button when input has content
urlInput.addEventListener("input", () => {
  goBtn.disabled = !urlInput.value.trim();
  result.classList.add("hidden");
  status.classList.add("hidden");
  status.classList.remove("error");
});

// Auto-paste on focus
urlInput.addEventListener("focus", async () => {
  if (!urlInput.value && navigator.clipboard && navigator.clipboard.readText) {
    try {
      const text = await navigator.clipboard.readText();
      if (text && (text.includes("youtube.com") || text.includes("youtu.be"))) {
        urlInput.value = text;
        urlInput.dispatchEvent(new Event("input"));
      }
    } catch {}
  }
});

// Submit on Enter
urlInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !goBtn.disabled) goBtn.click();
});

// Download
goBtn.addEventListener("click", async () => {
  const url = urlInput.value.trim();
  if (!url) return;

  goBtn.disabled = true;
  result.classList.add("hidden");
  status.classList.remove("hidden", "error");
  status.textContent = currentMode === "video" ? "downloading video..." : "fetching thumbnail...";

  try {
    const res = await fetch("/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, mode: currentMode }),
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.error || "Download failed");
    }

    status.textContent = data.title;
    resultLink.href = `/file/${data.task_id}/${encodeURIComponent(data.filename)}`;
    resultLink.textContent = currentMode === "video" ? "Save video" : "Save image";
    result.classList.remove("hidden");
  } catch (err) {
    status.classList.add("error");
    status.textContent = err.message;
  } finally {
    goBtn.disabled = !urlInput.value.trim();
  }
});
