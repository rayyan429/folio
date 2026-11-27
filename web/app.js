// Folio front end: upload PDFs -> watch them get sorted -> review the folders -> download a ZIP.
// Talks to the Flask API in app.py: POST /api/analyze, GET /api/status/<job>, POST /api/approve.

const $ = (id) => document.getElementById(id);
const UNSORTED = "__unsorted__"; // stands for the Unsorted list in moves and menus

let chosenFiles = [];                                    // File objects picked by the user
let state = { jobId: null, folders: [], unsorted: [] };  // folders: [{name, files, keywords}], unsorted: [{file, reason}]
let lastZip = null;                                      // the last downloaded ZIP, for "Download again"

// ---------- Sorter animation: file cards fly from a pile into folders ----------
// Used twice: a looping demo on the upload screen, and once with the user's REAL result,
// after the server has actually grouped and named the folders.
const REDUCED_MOTION = matchMedia("(prefers-reduced-motion: reduce)").matches;
const PILE_SIZE = 4; // how many cards are visible in the pile at once

class Sorter {
  // folders: folder labels; files: [{name, folder: index into folders}]
  // once: play through the files one time, then call onDone (otherwise loop forever)
  constructor(root, { folders, files, once = false, interval = 950, onDone = null }) {
    Object.assign(this, { root, once, interval, onDone });
    this.files = files.slice(); // a queue: the front card flies next
    this.timer = null;
    this.moves = 0;
    this.inFlight = 0;
    this.pile = el("ul", { className: "sorter-pile" });
    this.bins = folders.map((label) => {
      const count = el("span", { className: "bin-count" }, "0 files");
      const node = el("div", { className: "bin" },
        icon("i-folder", "bin-ico"),
        el("div", { className: "bin-text" }, el("span", { className: "bin-label", title: label }, label), count));
      return { node, count, n: 0 };
    });
    root.replaceChildren(this.pile, el("div", { className: "sorter-bins" }, ...this.bins.map((b) => b.node)));
    if (REDUCED_MOTION) { // still picture: everything already in its folder
      this.files.forEach((f) => this.bump(f.folder, false));
      if (once) this.files = [];
    }
    this.renderPile();
  }

  renderPile() {
    const chips = this.files.slice(0, PILE_SIZE).map((f) =>
      el("li", { className: "chip" }, icon("i-file", "pdf-ico"), el("span", { className: "truncate" }, f.name)));
    const extra = this.files.length - PILE_SIZE;
    if (extra > 0) chips.push(el("li", { className: "more" }, `+ ${extra} more`));
    this.pile.replaceChildren(...chips);
  }

  start() {
    if (this.timer) return;
    if (REDUCED_MOTION || !this.files.length) {
      if (this.once && this.onDone) setTimeout(this.onDone, REDUCED_MOTION ? 900 : 0);
      return;
    }
    this.timer = setInterval(() => this.step(), this.interval);
    setTimeout(() => this.step(), 250); // don't make people wait a whole interval for the first card
  }

  stop() {
    clearInterval(this.timer);
    this.timer = null;
  }

  step() {
    if (!this.timer || this.root.offsetParent === null) return; // stopped, or its screen is hidden
    const chip = this.pile.querySelector(".chip");
    if (!chip) return;
    if (!this.once && this.moves > 0 && this.moves % this.files.length === 0) this.resetCounts(); // demo: start over
    this.moves++;

    const file = this.files.shift();
    if (!this.once) this.files.push(file); // the demo loops; the real result plays once
    if (this.once && !this.files.length) this.stop(); // last card is on its way
    const bin = this.bins[file.folder % this.bins.length];

    // Measure where the card is and where its folder is, then fly a copy of the card between them.
    const box = this.root.getBoundingClientRect();
    const from = chip.getBoundingClientRect();
    const to = bin.node.querySelector(".bin-ico").getBoundingClientRect();
    const flyer = chip.cloneNode(true);
    flyer.classList.add("flying");
    Object.assign(flyer.style, { left: `${from.left - box.left}px`, top: `${from.top - box.top}px`, width: `${from.width}px` });
    this.root.append(flyer);
    const dx = to.left + to.width / 2 - (from.left + from.width / 2);
    const dy = to.top + to.height / 2 - (from.top + from.height / 2);
    this.inFlight++;
    flyer.animate([
      { transform: "translate(0, 0) scale(1)", opacity: 1 },
      { transform: `translate(${dx * 0.5}px, ${dy * 0.5 - 28}px) scale(0.8)`, opacity: 1, offset: 0.55 }, // a small arc
      { transform: `translate(${dx}px, ${dy}px) scale(0.25)`, opacity: 0 },
    ], { duration: 750, easing: "cubic-bezier(.45, 0, .25, 1)" }).onfinish = () => {
      flyer.remove();
      this.inFlight--;
      this.bump(file.folder, true);
      if (this.once && !this.files.length && this.inFlight === 0 && this.onDone) setTimeout(this.onDone, 700); // let the last landing register
    };

    // The rest of the pile slides up into the empty spot.
    this.renderPile();
    this.pile.animate([{ transform: `translateY(${from.height + 8}px)` }, { transform: "none" }], { duration: 350, easing: "ease-out" });
  }

  bump(folder, animate) { // one more file landed in this folder
    const bin = this.bins[folder % this.bins.length];
    bin.n++;
    bin.count.textContent = `${bin.n} file${bin.n === 1 ? "" : "s"}`;
    if (!animate) return;
    bin.node.classList.add("receiving");
    bin.node.querySelector(".bin-ico").animate([{ transform: "scale(1)" }, { transform: "scale(1.18)" }, { transform: "scale(1)" }], { duration: 300 });
    setTimeout(() => bin.node.classList.remove("receiving"), 350);
  }

  resetCounts() {
    this.bins.forEach((b) => { b.n = 0; b.count.textContent = "0 files"; });
  }
}

// Demo on the upload screen: a mix of schoolwork and everyday files, to show Folio isn't limited to one kind.
const heroSorter = new Sorter($("heroSorter"), {
  folders: ["Circuits", "Trip to College Station", "Taxes & Receipts"],
  files: [
    { name: "kirchhoffs-laws.pdf", folder: 0 }, { name: "flight-to-cll.pdf", folder: 1 },
    { name: "w2-form.pdf", folder: 2 }, { name: "op-amp-lab.pdf", folder: 0 },
    { name: "hotel-booking.pdf", folder: 1 }, { name: "tuition-receipt.pdf", folder: 2 },
    { name: "ac-power-notes.pdf", folder: 0 }, { name: "kyle-field-tickets.pdf", folder: 1 },
    { name: "bank-statement.pdf", folder: 2 },
  ],
});
let workSorter = null; // built from the real result, once the server has finished grouping

// ---------- Step 1: choosing files ----------
const dropzone = $("dropzone");
$("picker").addEventListener("change", (e) => { addChosen(e.target.files); e.target.value = ""; });
dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("over"); });
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("over"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("over");
  addChosen(e.dataTransfer.files);
});
$("clearBtn").addEventListener("click", () => { chosenFiles = []; renderChosen(); });

function addChosen(fileList) { // adds to the list instead of replacing it, skipping exact repeats
  for (const f of fileList) {
    if (!chosenFiles.some((c) => c.name === f.name && c.size === f.size)) chosenFiles.push(f);
  }
  renderChosen();
}

function renderChosen() {
  const n = chosenFiles.length;
  $("chosenWrap").hidden = n === 0;
  $("chosenTitle").textContent = `${n} file${n === 1 ? "" : "s"} to sort`;
  $("chosen").replaceChildren(...chosenFiles.map((f, i) => {
    const remove = el("button", { className: "icon-btn", title: "Remove", "aria-label": `Remove ${f.name}` }, icon("i-x"));
    remove.addEventListener("click", () => { chosenFiles.splice(i, 1); renderChosen(); });
    const isPdf = f.name.toLowerCase().endsWith(".pdf");
    return el("li", {},
      icon("i-file", "pdf-ico"),
      el("span", { className: "truncate", title: f.name }, f.name),
      isPdf ? el("span", { className: "size" }, formatSize(f.size)) : el("span", { className: "flag" }, "not a PDF"),
      remove);
  }));
  $("analyzeBtn").disabled = n === 0;
  $("analyzeBtn").textContent = n > 1 ? `Sort ${n} files` : "Sort file";
}

// ---------- Step 2: sort, showing the server's real progress ----------
// The server works in the background; the page asks for its progress every 0.7 s:
//   reading (each file's text + figures) -> grouping (embeddings, clustering, naming) -> done (the folders)
// The fly-into-folders animation only plays at the end, with the real folders.
const STAGES = ["reading", "grouping", "sorting"];
const STAGE_HINTS = {
  reading: "Reading the text and describing the figures in each file. New files take about 20 seconds each; files Folio has seen before are instant.",
  grouping: "Comparing every file with every other file to find the topics, then naming each group.",
  sorting: "Here are your folders.",
};
let timer = null;
let workCards = {}; // file name -> its card on the working screen

$("analyzeBtn").addEventListener("click", async () => {
  const form = new FormData();
  chosenFiles.forEach((f) => form.append("files", f));
  show("working");
  $("workSorter").hidden = true;
  $("workFiles").hidden = false;
  setStage("reading");
  const started = Date.now();
  $("elapsed").textContent = "0";
  timer = setInterval(() => { $("elapsed").textContent = Math.floor((Date.now() - started) / 1000); }, 1000);

  try {
    const res = await fetch("/api/analyze", { method: "POST", body: form });
    const data = await readJson(res);
    if (!res.ok) throw new Error(data.error || `Server error (${res.status})`);
    buildWorkCards(data.files);
    const result = await waitForResult(data.job_id);
    await playSorting(result);
    state = { jobId: data.job_id, folders: result.folders, unsorted: result.unsorted };
    showNotes(result);
    render();
    show("review");
  } catch (err) {
    show("upload");
    showError(err.message);
  } finally {
    clearInterval(timer);
  }
});

async function waitForResult(jobId) { // polls /api/status until the job is done
  let failures = 0;
  for (;;) {
    await sleep(700);
    let data;
    try {
      const res = await fetch(`/api/status/${jobId}`);
      data = await readJson(res);
      if (!res.ok) throw new Error(data.error || `Server error (${res.status})`);
      failures = 0;
    } catch (err) {
      if (++failures >= 5) throw err; // a few blips are fine; five in a row means the server is gone
      continue;
    }
    updateWork(data);
    if (data.stage === "done") return data.result;
    if (data.stage === "error") throw new Error(data.error);
  }
}

function buildWorkCards(names) {
  workCards = {};
  $("workFiles").replaceChildren(...names.map((name) => {
    const card = el("li", { className: "work-file" },
      el("span", { className: "state" }),
      el("span", { className: "name truncate", title: name }, name),
      el("span", { className: "detail" }));
    workCards[name] = { card, status: null };
    updateCard(name, { status: "waiting" });
    return card;
  }));
  $("readCount").textContent = `0/${names.length}`;
  setProgress(0);
}

function updateWork(data) {
  data.files.forEach((f) => updateCard(f.name, f));
  const finished = data.files.filter((f) => f.status === "done" || f.status === "unsorted").length;
  $("readCount").textContent = `${finished}/${data.files.length}`;
  if (data.stage === "reading") setProgress(finished / data.files.length);
  else if (data.stage === "grouping") setStage("grouping");
}

function updateCard(name, f) {
  const entry = workCards[name];
  if (!entry) return;
  const signature = JSON.stringify(f);
  if (entry.status === signature) return; // only touch cards that changed, so spinners don't restart
  entry.status = signature;
  const [stateBox, , detail] = entry.card.children;
  entry.card.className = `work-file ${f.status}`;
  if (f.status === "waiting") {
    stateBox.replaceChildren(icon("i-file"));
    detail.replaceChildren("Waiting");
  } else if (f.status === "reading") {
    stateBox.replaceChildren(el("span", { className: "spin" }));
    detail.replaceChildren("Reading slides and figures…");
  } else if (f.status === "done") {
    stateBox.replaceChildren(icon("i-check"));
    const parts = [`${f.slides} page${f.slides === 1 ? "" : "s"}`, `${f.figures} figure${f.figures === 1 ? "" : "s"} described`];
    detail.replaceChildren(parts.join(" · "));
    if (f.cached) detail.append(el("span", { className: "badge", title: "Seen before, so no new AI calls were needed" }, icon("i-bolt"), "cached"));
  } else if (f.status === "unsorted") {
    stateBox.replaceChildren(icon("i-alert"));
    detail.replaceChildren(`Unsorted · ${f.reason}`);
  }
}

function setStage(stage) {
  const current = STAGES.indexOf(stage);
  document.querySelectorAll(".stages li").forEach((li, i) => {
    li.classList.toggle("active", i === current);
    li.classList.toggle("complete", i < current);
  });
  $("stageHint").textContent = STAGE_HINTS[stage];
  $("workingTitle").textContent = stage === "sorting" ? "Sorting into folders" : "Sorting your files";
  document.querySelector(".progress").classList.toggle("indeterminate", stage === "grouping");
  if (stage !== "reading") setProgress(stage === "sorting" ? 1 : 0);
}

function setProgress(fraction) {
  $("progressBar").style.width = `${Math.round(fraction * 100)}%`;
}

function playSorting(result) { // the real folders appear, and each file flies into the folder it was sorted into
  setStage("sorting");
  const labels = result.folders.map((f) => f.name);
  if (result.unsorted.length) labels.push("Unsorted");
  const folderOf = {};
  result.folders.forEach((f, i) => f.files.forEach((name) => { folderOf[name] = i; }));
  result.unsorted.forEach((u) => { folderOf[u.file] = labels.length - 1; });
  const files = Object.keys(workCards).filter((n) => n in folderOf).map((n) => ({ name: n, folder: folderOf[n] }));

  $("workFiles").hidden = true;
  $("workSorter").hidden = false;
  return new Promise((resolve) => {
    workSorter = new Sorter($("workSorter"), {
      folders: labels, files, once: true,
      interval: Math.max(220, Math.min(650, 4500 / Math.max(files.length, 1))), // about 4-5 s in total, whatever the count
      onDone: resolve,
    });
    workSorter.start();
  });
}

// ---------- Step 3: review ----------
function render() {
  const sorted = state.folders.reduce((n, f) => n + f.files.length, 0);
  const folders = state.folders.filter((f) => f.files.length).length;
  $("summary").textContent = `${sorted} file${sorted === 1 ? "" : "s"} in ${folders} folder${folders === 1 ? "" : "s"}` +
    (state.unsorted.length ? `, ${state.unsorted.length} unsorted` : "") + ".";
  $("approveBtn").disabled = sorted + state.unsorted.length === 0;

  const cards = state.folders.map((folder, i) => folderCard(folder, i));
  if (state.unsorted.length) cards.push(unsortedCard());
  $("folders").replaceChildren(...cards);
}

function folderCard(folder, index) {
  const name = el("input", { className: "folder-name", value: folder.name, "aria-label": "Folder name", spellcheck: false });
  name.addEventListener("input", () => { folder.name = name.value; }); // no re-render, so the cursor stays put
  name.addEventListener("change", () => render());                     // refresh the move menus once editing is done
  const files = folder.files.length
    ? folder.files.map((file) => fileRow(file, index))
    : [el("li", { className: "empty" }, "Drop files here")];
  const parts = [el("div", { className: "folder-head" }, icon("i-folder", "folder-ico"), name, el("span", { className: "count" }, String(folder.files.length)))];
  if (folder.keywords?.length) { // the words that set this folder's files apart, so the grouping isn't a black box
    parts.push(el("div", { className: "keywords", title: "Words that set this folder's files apart" },
      ...folder.keywords.map((k) => el("span", {}, k))));
  }
  parts.push(el("ul", { className: "files" }, ...files));
  const card = el("div", { className: "card folder" }, ...parts);
  makeDropTarget(card, index);
  return card;
}

function unsortedCard() {
  const card = el("div", { className: "card folder unsorted" },
    el("div", { className: "folder-head" }, icon("i-folder", "folder-ico"),
      el("span", { className: "folder-title" }, "Unsorted"),
      el("span", { className: "count" }, String(state.unsorted.length))),
    el("ul", { className: "files" }, ...state.unsorted.map((u) => fileRow(u.file, UNSORTED, u.reason))));
  makeDropTarget(card, UNSORTED);
  return card;
}

function fileRow(file, from, reason) {
  // The menu lists every folder plus Unsorted; it's the keyboard-friendly way to move a file.
  const select = el("select", { className: "move", "aria-label": `Move ${file} to` },
    el("option", { value: "", disabled: true, selected: true }, "Move to…"),
    ...state.folders.map((f, i) => el("option", { value: String(i), disabled: i === from }, f.name || "Untitled")),
    el("option", { value: UNSORTED, disabled: from === UNSORTED }, "Unsorted"));
  select.addEventListener("change", () => moveFile(file, from, select.value === UNSORTED ? UNSORTED : Number(select.value)));

  const row = el("li", { className: "file", draggable: true },
    icon("i-grip", "grip"), icon("i-file", "pdf-ico"),
    el("span", { className: "truncate", title: file }, file), select);
  if (reason) row.append(el("span", { className: "file-reason" }, reason));

  row.addEventListener("dragstart", (e) => {
    e.dataTransfer.setData("text/plain", JSON.stringify({ file, from }));
    e.dataTransfer.effectAllowed = "move";
    row.classList.add("dragging");
  });
  row.addEventListener("dragend", () => row.classList.remove("dragging"));
  return row;
}

function makeDropTarget(card, to) { // lets a dragged file be dropped anywhere on a folder card
  card.addEventListener("dragover", (e) => { e.preventDefault(); card.classList.add("drop-target"); });
  card.addEventListener("dragleave", (e) => { if (!card.contains(e.relatedTarget)) card.classList.remove("drop-target"); });
  card.addEventListener("drop", (e) => {
    e.preventDefault();
    card.classList.remove("drop-target");
    try {
      const { file, from } = JSON.parse(e.dataTransfer.getData("text/plain"));
      moveFile(file, from, to);
    } catch { /* something other than one of our files was dropped */ }
  });
}

function moveFile(file, from, to) {
  if (from === to) return;
  let reason = "";
  if (from === UNSORTED) {
    reason = state.unsorted.find((u) => u.file === file)?.reason || "";
    state.unsorted = state.unsorted.filter((u) => u.file !== file);
  } else {
    state.folders[from].files = state.folders[from].files.filter((f) => f !== file);
  }
  if (to === UNSORTED) state.unsorted.push({ file, reason: reason || "moved here by you" });
  else state.folders[to].files.push(file);
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
  button.lastChild.textContent = "Building ZIP…";
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
    if (!res.ok) throw new Error((await readJson(res)).error || `Server error (${res.status})`);
    lastZip = await res.blob();
    download(lastZip);
    const folders = state.folders.filter((f) => f.files.length).length;
    $("doneSummary").textContent = `${folders} folder${folders === 1 ? "" : "s"}${state.unsorted.length ? " plus Unsorted" : ""}, saved as folio-sorted.zip.`;
    show("done");
  } catch (err) {
    showError(err.message);
  } finally {
    button.disabled = false;
    button.lastChild.textContent = "Approve & download ZIP";
  }
});

$("redownloadBtn").addEventListener("click", () => lastZip && download(lastZip));
$("restartBtn").addEventListener("click", startOver);
$("newBtn").addEventListener("click", startOver);

function startOver() {
  chosenFiles = [];
  renderChosen();
  show("upload");
}

// ---------- helpers ----------
function show(screen) {
  ["upload", "working", "review", "done"].forEach((s) => { $(s).hidden = s !== screen; });
  $("error").hidden = true;
  if (screen === "upload") heroSorter.start(); else heroSorter.stop(); // only animate what's on screen
  window.scrollTo({ top: 0 });
}

function showError(message) {
  $("error").textContent = message;
  $("error").hidden = false;
}

function showNotes(data) {
  $("method").hidden = !data.method;
  $("method").textContent = data.method ? `Grouping: ${data.method}.` : "";
  const warnings = data.warnings || [];
  $("warnings").replaceChildren(...warnings.map((w) => el("li", {}, w)));
  $("warnings").hidden = warnings.length === 0;
}

async function readJson(res) { // error pages (e.g. "file too large") aren't JSON, so don't crash on them
  try { return await res.json(); } catch { return { error: res.status === 413 ? "Those files are too large to upload at once." : `Server error (${res.status})` }; }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function download(blob) {
  const url = URL.createObjectURL(blob);
  const link = el("a", { href: url, download: "folio-sorted.zip" });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function formatSize(bytes) {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function icon(id, className = "") { // <svg><use href="#id"></svg> from the icons defined in index.html
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  if (className) svg.setAttribute("class", className);
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `#${id}`);
  svg.append(use);
  return svg;
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

show("upload");
