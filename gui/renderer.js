const socket = new WebSocket('ws://localhost:8765');
const { ipcRenderer } = require("electron");

let stopBtn = null;
let groupBtn = null;
let undoBtn = null;
let undoInProgress = false;

// Connection established
socket.onopen = () => {
  console.log("WebSocket connected");

  // Minimal UI toast for new users
  const toast = document.createElement("div");
  toast.textContent = "New user? Click 'Start Folder Embedding' first! It may take some time.";
  toast.style.position = "fixed";
  toast.style.bottom = "20px";
  toast.style.left = "50%";
  toast.style.transform = "translateX(-50%)";
  toast.style.backgroundColor = "#333";
  toast.style.color = "white";
  toast.style.padding = "12px 20px";
  toast.style.borderRadius = "6px";
  toast.style.zIndex = "9999";
  toast.style.boxShadow = "0 2px 5px rgba(0,0,0,0.2)";
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 5000);

  // Cache some button references
  stopBtn = document.getElementById("stop-embedding");
  groupBtn = document.getElementById("group-folders");
  undoBtn = document.getElementById("undo-grouping");
};

// Incoming messages from backend
socket.onmessage = (event) => {
  console.log("Received from Python:", event.data);

  let data;
  try {
    data = JSON.parse(event.data);
  } catch (err) {
    console.error("Failed to parse JSON:", err);
    return;
  }

  // Embedding progress
  if (data.action === "embed_progress") {
    const progressBar = document.getElementById("embedding-progress");
    const label = document.getElementById("progress-label");

    if (progressBar && label) {
      progressBar.style.display = "block";
      label.style.display = "block";

      progressBar.value = data.done;
      progressBar.max = data.total;
      label.textContent = `Embedding folders (${data.done}/${data.total})`;

      if (data.done === data.total) {
        label.textContent = "Embedding complete!";
        if (groupBtn) groupBtn.disabled = false;
        if (undoBtn) undoBtn.disabled = false;
        if (stopBtn) stopBtn.style.display = "none";
        setTimeout(() => {
          progressBar.style.display = "none";
          label.style.display = "none";
        }, 1000);
      }
    }
    return;
  }

  // Embed lifecycle messages
  if (data.action === "embed_started") {
    if (stopBtn) stopBtn.style.display = "inline-block";
    if (groupBtn) groupBtn.disabled = true;
    if (undoBtn) undoBtn.disabled = true;
    return;
  }

  if (data.action === "embed_stopping") {
    if (stopBtn) stopBtn.style.display = "none";
    if (groupBtn) groupBtn.disabled = false;
    if (undoBtn) undoBtn.disabled = false;
    const label = document.getElementById("progress-label");
    if (label) label.textContent = "Stopping embedding...";
    return;
  }

  if (data.action === "embed_stopped") {
    if (stopBtn) stopBtn.style.display = "none";
    if (groupBtn) groupBtn.disabled = false;
    if (undoBtn) undoBtn.disabled = false;
    alert("Embedding was cancelled.");
    const progressBar = document.getElementById("embedding-progress");
    const label = document.getElementById("progress-label");
    if (progressBar) progressBar.style.display = "none";
    if (label) label.style.display = "none";
    return;
  }

  if (data.action === "embed_complete") {
    if (stopBtn) stopBtn.style.display = "none";
    if (groupBtn) groupBtn.disabled = false;
    if (undoBtn) undoBtn.disabled = false;
    const label = document.getElementById("progress-label");
    if (label) label.textContent = "Embedding completed!";
    setTimeout(() => {
      const progressBar = document.getElementById("embedding-progress");
      const label2 = document.getElementById("progress-label");
      if (progressBar) progressBar.style.display = "none";
      if (label2) label2.style.display = "none";
    }, 1000);
    return;
  }

  // Folder grouping result
  if (data.action === "group_result") {
    document.getElementById("embedding-progress").style.display = "none";
    document.getElementById("progress-label").style.display = "none";
    if (data.status === "success") {
      alert("Folders grouped into:\n\n" + JSON.stringify(data.groups, null, 2));
    } else {
      alert("Grouping failed: " + data.message);
    }
    return;
  }

  // Undo result
  if (data.action === "undo_result") {
    undoInProgress = false;

    if (data.status === "success") {
      alert("Undo completed.");
    } else if (data.status === "error") {
      alert("Undo failed: " + (data.message || "Unknown error"));
    }

    const progressBar = document.getElementById("embedding-progress");
    const label = document.getElementById("progress-label");
    if (progressBar) progressBar.style.display = "none";
    if (label) label.style.display = "none";

    return;
  }

  if (data.action === "status" && undoInProgress) {
    return;
  }

  // Move/Skip result
  if (data.action === "status") {
    if (undoInProgress) return;
    const card = document.getElementById(getCardId(data.path));
    if (!card) return;

    const status = document.createElement("p");
    status.textContent =
      data.status === "moved" ? "Moved" :
      data.status === "skipped" ? "Skipped" :
      "Error";

    card.appendChild(status);
    return;
  }

  // Render new file card (broadcast from server)
  if (!data.path) return;

  const cardId = getCardId(data.path);
  if (document.getElementById(cardId)) return;

  const fileContainer = document.getElementById("file-container");
  const fileCard = document.createElement("div");
  fileCard.classList.add("file-card");
  fileCard.id = cardId;

  const title = document.createElement("h3");
  title.textContent = data.filename;

  const category = document.createElement("p");
  category.textContent = `Suggested category: ${data.category}`;

  const summary = document.createElement("p");
  summary.textContent = `Summary: ${data.summary || "No summary available."}`;
  summary.classList.add("summary");

  const moveBtn = document.createElement("button");
  moveBtn.textContent = "Move";
  moveBtn.onclick = () => {
    socket.send(JSON.stringify({ action: "move", path: data.path, category: data.category }));
    moveBtn.disabled = true;
    skipBtn.disabled = true;
  };

  const skipBtn = document.createElement("button");
  skipBtn.textContent = "Skip";
  skipBtn.onclick = () => {
    socket.send(JSON.stringify({ action: "skip", path: data.path }));
    moveBtn.disabled = true;
    skipBtn.disabled = true;
  };

  fileCard.appendChild(title);
  fileCard.appendChild(category);
  fileCard.appendChild(summary);
  fileCard.appendChild(moveBtn);
  fileCard.appendChild(skipBtn);
  fileContainer.appendChild(fileCard);
};

// Encode path to ID
function getCardId(path) {
  return "card-" + btoa(path).replace(/[^a-z0-9]/gi, '');
}

// View History Button
document.getElementById("view-history").onclick = async () => {
  document.getElementById("history-tab").classList.add("active");

  const search = document.getElementById("search-input").value;
  const category = document.getElementById("filter-category").value;

  const rows = await ipcRenderer.invoke('get-logs', { search, category });
  const tbody = document.querySelector("#history-table tbody");
  tbody.innerHTML = "";

  rows.forEach(row => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.filename}</td>
      <td>${row.category}</td>
      <td>${new Date(row.timestamp).toLocaleString()}</td>
      <td>${row.summary.slice(0, 100)}...</td>
    `;
    tbody.appendChild(tr);
  });
};

// Group Similar Folders
document.getElementById("group-folders").onclick = () => {
  const progressBar = document.getElementById("embedding-progress");
  const label = document.getElementById("progress-label");
  progressBar.style.display = "block";
  label.style.display = "block";
  progressBar.value = 0;
  label.textContent = "Preparing to group folders...";
  socket.send(JSON.stringify({ action: "group_folders" }));
};

document.getElementById("start-embedding").onclick = () => {
  const progressBar = document.getElementById("embedding-progress");
  const label = document.getElementById("progress-label");
  groupBtn = document.getElementById("group-folders");
  undoBtn = document.getElementById("undo-grouping");
  stopBtn = document.getElementById("stop-embedding");

  progressBar.style.display = "block";
  label.style.display = "block";
  if (stopBtn) stopBtn.style.display = "inline-block";
  progressBar.value = 0;
  label.textContent = "Starting embedding...";

  if (groupBtn) groupBtn.disabled = true;
  if (undoBtn) undoBtn.disabled = true;

  socket.send(JSON.stringify({ action: "start_embedding" }));
};

document.getElementById("stop-embedding").onclick = () => {
  console.log("Sending stop_embedding message");
  socket.send(JSON.stringify({ action: "stop_embedding" }));
  // Hide immediately while server acknowledges
  const stopBtnLocal = document.getElementById("stop-embedding");
  if (stopBtnLocal) stopBtnLocal.style.display = "none";
};

document.getElementById("undo-grouping").onclick = () => {
  undoInProgress = true;

  const progressBar = document.getElementById("embedding-progress");
  const label = document.getElementById("progress-label");

  if (progressBar) progressBar.style.display = "block";
  if (label) {
    label.style.display = "block";
    label.textContent = "Undoing grouping...";
  }

  socket.send(JSON.stringify({ action: "undo_grouping" }));
};
