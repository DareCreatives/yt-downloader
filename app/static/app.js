const form = document.getElementById("download-form");
const urlInput = document.getElementById("url");
const formatSelect = document.getElementById("format");
const qualitySelect = document.getElementById("quality");
const submitBtn = document.getElementById("submit-btn");
const statusBox = document.getElementById("status");

let pollTimer = null;

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const url = urlInput.value.trim();
  if (!url) return;

  resetStatus();
  setBusy(true);
  showStatus("Submitting…", "");

  try {
    const res = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url,
        format: formatSelect.value,
        quality: qualitySelect.value,
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Request failed (${res.status})`);
    }

    const { job_id } = await res.json();
    pollJob(job_id);
  } catch (err) {
    showError(err.message || "Something went wrong.");
    setBusy(false);
  }
});

async function pollJob(jobId) {
  clearTimeout(pollTimer);
  try {
    const res = await fetch(`/api/job/${jobId}`);
    if (!res.ok) throw new Error("Job not found");
    const job = await res.json();

    renderJob(job);

    if (job.status === "completed") {
      setBusy(false);
      return;
    }
    if (job.status === "failed") {
      setBusy(false);
      return;
    }
    pollTimer = setTimeout(() => pollJob(jobId), 1200);
  } catch (err) {
    showError(err.message);
    setBusy(false);
  }
}

function renderJob(job) {
  const pct = Math.max(0, Math.min(100, job.progress || 0));
  const safeTitle = escapeHtml(job.title || job.url);

  let html = `<h3>${labelFor(job.status)}</h3>`;
  html += `<p class="title">${safeTitle}</p>`;
  html += `<div class="bar"><div style="width:${pct}%"></div></div>`;
  html += `<p class="title">${pct.toFixed(1)}%</p>`;

  if (job.status === "failed" && job.error) {
    html += `<p class="error">Error: ${escapeHtml(job.error)}</p>`;
  }
  if (job.status === "completed") {
    html += `<a class="download-link" href="/api/file/${job.job_id}" download>⬇ Save file</a>`;
  }
  statusBox.innerHTML = html;
  statusBox.classList.remove("hidden");
}

function labelFor(status) {
  return {
    queued: "Queued…",
    downloading: "Downloading…",
    completed: "Ready to save",
    failed: "Failed",
  }[status] || status;
}

function showStatus(title, subtitle) {
  statusBox.innerHTML = `<h3>${escapeHtml(title)}</h3>` +
    (subtitle ? `<p class="title">${escapeHtml(subtitle)}</p>` : "");
  statusBox.classList.remove("hidden");
}

function showError(msg) {
  statusBox.innerHTML = `<h3>Error</h3><p class="error">${escapeHtml(msg)}</p>`;
  statusBox.classList.remove("hidden");
}

function resetStatus() {
  clearTimeout(pollTimer);
  statusBox.classList.add("hidden");
  statusBox.innerHTML = "";
}

function setBusy(busy) {
  submitBtn.disabled = busy;
  submitBtn.textContent = busy ? "Working…" : "Download";
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}
