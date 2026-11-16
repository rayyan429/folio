// Folio front end: upload PDFs -> review proposed folders -> approve and download a ZIP.
// Talks to the Flask API in app.py: POST /api/analyze and POST /api/approve.

const $ = (id) => document.getElementById(id);
const UNSORTED = "__unsorted__"; // value used in the "Move to" menus for the Unsorted list

let chosenFiles = [];                                    // File objects picked by the user
let state = { jobId: null, folders: [], unsorted: [] };  // folders: [{name, files: [...]}], unsorted: [{file, reason}]

// ---------- Step 1: choosing files ----------
const dropzone = $("dropzone");
$("picker").addEventListener("change", (e) => setChosen(e.target.files));
dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("over"); });
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("over"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("over");
  setChosen(e.dataTransfer.files);
});

function setChosen(fileList) {
  chosenFiles = Array.from(fileList);
  const list = $("chosen");
  list.replaceChildren(...chosenFiles.map((f) => el("li", {}, f.name)));
  $("analyzeBtn").disabled = chosenFiles.length === 0;
  $("analyzeBtn").textContent = chosenFiles.length > 1 ? `Sort these ${chosenFiles.length} files` : "Sort this file";
}

// ---------- Step 2: send them to the API ----------
$("analyzeBtn").addEventListener("click", async () => {
  const form = new FormData();
  chosenFiles.forEach((f) => form.append("files", f));
  show("working");
  $("workingText").textContent = `Reading slides and describing figures in ${chosenFiles.length} file(s)…`;
  try {
    const res = await fetch("/api/analyze", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `Server error (${res.status})`);
    state = { jobId: data.job_id, folders: data.folders, unsorted: data.unsorted };
    showNotes(data);
    render();
    show("review");
  } catch (err) {
    show("upload");
    showError(err.message);
  }
});

// ---------- Step 3: review ----------
function render() {
  const container = $("folders");
  const cards = state.folders.map((folder, i) => folderCard(folder, i));
  if (state.unsorted.length) cards.push(unsortedCard());
  container.replaceChildren(...cards);
}

function folderCard(folder, index) {
  const name = el("input", { className: "folder-name", value: folder.name, "aria-label": "Folder name" });
  name.addEventListener("input", () => { folder.name = name.value; });
  const files = folder.files.length
    ? folder.files.map((file) => fileRow(file, index))
    : [el("li", { className: "empty" }, "Empty folder (skipped in the ZIP)")];
  return el("div", { className: "folder" }, name, el("ul", { className: "files" }, ...files));
}

function unsortedCard() {
  const rows = state.unsorted.map((u) => fileRow(u.file, UNSORTED, u.reason));
  return el("div", { className: "folder unsorted" },
    el("div", { className: "folder-title" }, `Unsorted (${state.unsorted.length})`),
    el("ul", { className: "files" }, ...rows));
}

function fileRow(file, from, reason) {
  // The "Move to" dropdown lists every folder plus Unsorted; picking one moves the file there.
  const select = el("select", { "aria-label": `Move ${file} to` },
    el("option", { value: "", disabled: true, selected: true }, "Move to…"),
    ...state.folders.map((f, i) => el("option", { value: String(i), disabled: i === from }, f.name || "Untitled")),
    el("option", { value: UNSORTED, disabled: from === UNSORTED }, "Unsorted"));
  select.addEventListener("change", () => moveFile(file, from, select.value));
  const row = el("li", { className: "file" }, el("span", { className: "file-name", title: file }, file), select);
  if (reason) row.append(el("span", { className: "file-reason" }, reason));
  return row;
}

function moveFile(file, from, to) {
  let reason = "";
  if (from === UNSORTED) {
    reason = state.unsorted.find((u) => u.file === file)?.reason || "";
    state.unsorted = state.unsorted.filter((u) => u.file !== file);
  } else {
    state.folders[from].files = state.folders[from].files.filter((f) => f !== file);
  }
  if (to === UNSORTED) state.unsorted.push({ file, reason: reason || "moved here by you" });
  else state.folders[Number(to)].files.push(file);
  render();
}

$("addFolderBtn").addEventListener("click", () => {
  state.folders.push({ name: "New folder", files: [] });
  render();
  const inputs = document.querySelectorAll(".folder-name");
  inputs[inputs.length - 1].select(); // ready to type the new name
});

// ---------- Step 4: approve -> download the ZIP ----------
$("approveBtn").addEventListener("click", async () => {
  const button = $("approveBtn");
  button.disabled = true;
  button.textContent = "Building ZIP…";
  try {
    const res = await fetch("/api/approve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: state.jobId,
        folders: state.folders.filter((f) => f.files.length),
        unsorted: state.unsorted.map((u) => u.file),
      }),
    });
    if (!res.ok) throw new Error((await res.json()).error || `Server error (${res.status})`);
    const url = URL.createObjectURL(await res.blob());
    const link = el("a", { href: url, download: "folio-sorted.zip" });
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    showError(err.message);
  } finally {
    button.disabled = false;
    button.textContent = "Approve and download ZIP";
  }
});

$("restartBtn").addEventListener("click", () => {
  $("picker").value = "";
  setChosen([]);
  show("upload");
});

// ---------- helpers ----------
function show(id) {
  ["upload", "working", "review"].forEach((s) => { $(s).hidden = s !== id; });
  $("error").hidden = true;
}

function showError(message) {
  $("error").textContent = message;
  $("error").hidden = false;
}

function showNotes(data) {
  $("method").hidden = !data.method;
  $("method").textContent = data.method ? `Grouping: ${data.method}.` : "";
  const warnings = $("warnings");
  warnings.replaceChildren(...(data.warnings || []).map((w) => el("li", {}, w)));
  warnings.hidden = !(data.warnings || []).length;
}

// Small helper to build elements without innerHTML (file names can contain any characters).
function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key in node && !key.includes("-")) node[key] = value;
    else node.setAttribute(key, value);
  }
  node.append(...children);
  return node;
}
