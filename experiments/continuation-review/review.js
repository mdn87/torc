"use strict";

const byId = id => document.getElementById(id);
const form = byId("review");
const statusLabel = {open: "Not started", draft: "In progress", submitted: "Submitted"};
let batch, card, editing;
let dirty = false, pending = null, timer, acting = false, conflicted = false;

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

async function request(url, data) {
  const options = data ? {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(data)
  } : {};
  const response = await fetch(url, options);
  const result = await response.json();
  if (!response.ok) {
    const error = new Error(result.error || "The local review page could not save this change.");
    error.status = response.status;
    throw error;
  }
  return result;
}

function showError(error) {
  conflicted ||= error.status === 409;
  const message = error instanceof TypeError ? "Cannot reach the local review launcher." : error.message;
  byId("error-text").textContent = message + (dirty ? " Your unsaved answers are still on this page." : "");
  byId("problem").hidden = false;
  byId("retry").hidden = conflicted || !dirty;
  if (dirty) byId("save-state").textContent = "Unsaved changes";
}

function renderQueue() {
  const submitted = batch.cards.filter(item => item.status === "submitted").length;
  byId("progress-text").textContent = submitted + " of " + batch.cards.length + " submitted";
  byId("progress").max = batch.cards.length;
  byId("progress").value = submitted;
  const buttons = batch.cards.map((item, i) => {
    const button = element("button", undefined, "case-link");
    button.type = "button";
    if (item.id === card.id) button.setAttribute("aria-current", "step");
    button.append(element("span", String(i + 1).padStart(2, "0"), "case-index"),
                  element("strong", item.title), element("span", statusLabel[item.status], "case-status"));
    button.addEventListener("click", () => {
      if (item.id !== card.id) action(async () => { await flush(); display(item, true); });
    });
    return button;
  });
  byId("cases").replaceChildren(...buttons);
  byId("finish").hidden = submitted !== batch.cards.length || editing;
  byId("lock").hidden = Boolean(batch.locked_at);
  byId("finish-title").textContent = batch.locked_at ? "Practice batch locked" : "Both reviews are submitted";
  byId("finish-note").textContent = batch.locked_at
    ? "Your answers and revision history are available in Export answers."
    : "You can revise either review until you lock this practice batch.";
}

function choices(name, question, options, selected, className) {
  const group = element("fieldset", undefined, className);
  group.append(element("legend", question));
  const row = element("div", undefined, "choices");
  for (const option of options) {
    const label = element("label", undefined, "choice");
    const input = document.createElement("input");
    input.type = "radio";
    input.name = name;
    input.value = option;
    input.checked = option === selected;
    input.disabled = !editing;
    input.required = true;
    label.append(input, element("span", option));
    row.append(label);
  }
  group.append(row);
  return group;
}

function evidenceTable(rows, label) {
  const table = element("table", undefined, "case-table");
  table.setAttribute("aria-label", label);
  const header = table.createTHead().insertRow();
  const width = Math.max(...rows.map(row => row.length));
  for (let i = 0; i < width; i++) {
    const heading = element("th", rows[0][i] || "(no heading)");
    heading.scope = "col";
    header.append(heading);
  }
  const body = table.createTBody();
  for (const values of rows.slice(1)) {
    const row = body.insertRow();
    for (let i = 0; i < width; i++) row.insertCell().textContent = values[i] ?? "";
  }
  return table;
}

function resultPanel(side, questions) {
  const result = card.results[side];
  const panel = element("section", undefined, "result");
  panel.setAttribute("aria-label", "Result " + side);
  const heading = element("h3", "Result ");
  heading.append(element("span", side, "side-letter"));
  const details = document.createElement("details");
  details.append(element("summary", "Changes and evidence"));
  panel.append(heading);
  const outputLabel = element("p", card.output_label, "output-label");
  const rawOutput = element("pre", result.output, "output");
  if (card.comparison) {
    const label = card.comparison.result_label;
    panel.append(element("p", label, "output-label"), evidenceTable(result.display_rows, label));
    details.append(outputLabel, rawOutput, element("p", result.behavior));
  } else {
    panel.append(element("p", result.behavior), outputLabel, rawOutput);
  }
  details.append(element("p", result.change), element("pre", result.evidence, "evidence"));
  panel.append(details);
  for (const criterion of batch.rubric.criteria) {
    const question = questions?.[criterion.id] ?? criterion.question;
    panel.append(choices(side + "-" + criterion.id, question, batch.rubric.ratings,
                         card.answers[side][criterion.id], "rating"));
  }
  return panel;
}

function updateReason() {
  const rubric = batch.rubric;
  const checked = Array.from(form.querySelectorAll("input:checked"));
  const required = checked.some(input => (input.name === "preference"
    ? rubric.reason_preferences : rubric.reason_ratings).includes(input.value));
  byId("reason").required = required;
  byId("reason-hint").textContent = required ? "A short reason is required for this choice." : "Optional for these choices.";
}

function savedStatus() {
  if (batch.locked_at) return "Batch locked";
  if (card.status === "submitted") return "Submitted · revision " + card.revision;
  return card.revision ? "Saved · revision " + card.revision : "No answers yet";
}

function display(item, focus = false, revise = false) {
  card = item;
  editing = !batch.locked_at && (revise || card.status !== "submitted");
  history.replaceState(null, "", "#" + card.id);
  byId("position").textContent = "Practice case " + (batch.cards.indexOf(card) + 1) + " of " + batch.cards.length;
  byId("case-title").textContent = card.title;
  document.title = card.title + " · TORC practice";
  byId("request").textContent = card.request;
  byId("interruption").textContent = card.clarified_interruption ?? card.interruption;
  byId("scored-context").hidden = !card.clarified_interruption;
  byId("scored-context").open = false;
  byId("original-interruption").textContent = card.clarified_interruption ? card.interruption : "";
  byId("success").replaceChildren(...card.success.map(text => element("li", text)));
  const comparison = card.comparison;
  const questions = batch.rubric.case_questions?.[card.id];
  byId("input-label").textContent = comparison?.expected_label ?? card.input_label;
  byId("input").hidden = Boolean(comparison);
  byId("input").textContent = card.input;
  byId("expected").hidden = !comparison;
  if (comparison) {
    byId("expected").replaceChildren(element("p", comparison.guide),
                                     evidenceTable(comparison.expected, comparison.expected_label));
  }
  byId("review-instructions").textContent = comparison
    ? "Imagine you asked for this change. Look at what each result gives you, then decide which one you would use. Both are written practice examples."
    : "Both results are written examples for practice. Rate each against the original request.";
  byId("results").replaceChildren(resultPanel("A", questions), resultPanel("B", questions));
  const preference = questions?.preference ?? batch.rubric.preference_question;
  byId("preference").replaceChildren(choices("preference", preference, batch.rubric.preferences,
                                            card.answers.preference));
  byId("reason-label").textContent = questions?.reason ?? batch.rubric.reason_question;
  byId("reason").value = card.answers.reason;
  byId("reason").readOnly = !editing;
  updateReason();
  byId("submit").hidden = !editing;
  byId("revise").hidden = editing || Boolean(batch.locked_at);
  byId("save-help").textContent = editing ? "Answers save to this computer as you work."
    : "Submitted by " + batch.reviewer + ". Earlier answers are kept in the export.";
  byId("save-state").textContent = savedStatus();
  renderQueue();
  byId("case").hidden = false;
  if (focus) byId("case-title").focus();
}

function currentAnswers() {
  const data = new FormData(form);
  const answers = {A: {}, B: {}, preference: data.get("preference") || "", reason: data.get("reason")};
  for (const side of ["A", "B"]) {
    for (const {id} of batch.rubric.criteria) {
      const value = data.get(side + "-" + id);
      if (value) answers[side][id] = value;
    }
  }
  return answers;
}

async function save(submit) {
  const result = await request("/api/save", {
    card_id: card.id, binding: card.binding, base_revision: card.revision, answers: currentAnswers(), submit
  });
  Object.assign(card, result);
  byId("problem").hidden = true;
  renderQueue();
  if (!dirty) byId("save-state").textContent = savedStatus();
}

// Serialize saves so edits made during an earlier request get their own revision.
async function flush() {
  clearTimeout(timer);
  if (conflicted) throw new Error("Reload the saved reviews before continuing.");
  while (dirty || pending) {
    if (!pending) {
      dirty = false;
      pending = save(false).catch(error => { dirty = true; throw error; })
        .finally(() => { pending = null; });
    }
    await pending;
  }
}

function changed(event) {
  if (!editing) return;
  dirty = true;
  updateReason();
  if (conflicted) return;
  byId("save-state").textContent = "Saving…";
  clearTimeout(timer);
  if (event.target === byId("reason")) timer = setTimeout(() => flush().catch(showError), 250);
  else flush().catch(showError);
}

async function action(work) {
  if (acting) return;
  acting = true;
  form.inert = true;
  try { await work(); }
  catch (error) { showError(error); }
  finally { form.inert = false; acting = false; }
}

form.addEventListener("input", changed);
form.addEventListener("submit", event => {
  event.preventDefault();
  if (!editing) return;
  action(async () => {
    await flush();
    await save(true);
    const next = batch.cards.find(item => item.status !== "submitted");
    display(next || card, true);
    if (!next) byId("finish").scrollIntoView({block: "center"});
  });
});
byId("revise").addEventListener("click", () => {
  display(card, false, true);
  form.querySelector("input").focus();
});
byId("lock").addEventListener("click", () => {
  byId("lock-dialog").returnValue = "cancel";
  byId("lock-dialog").showModal();
});
byId("lock-dialog").addEventListener("close", () => {
  if (byId("lock-dialog").returnValue !== "lock") return;
  action(async () => {
    await flush();
    const revisions = Object.fromEntries(batch.cards.map(item => [item.id, item.revision]));
    Object.assign(batch, await request("/api/lock", {batch_id: batch.batch_id, revisions}));
    display(card, true);
    byId("finish").scrollIntoView({block: "center"});
  });
});
byId("export").addEventListener("click", event => {
  event.preventDefault();
  action(async () => {
    await flush();
    const link = document.createElement("a");
    link.href = "/api/export";
    link.download = "practice-review.json";
    link.click();
  });
});
byId("retry").addEventListener("click", () => action(flush));
byId("reload").addEventListener("click", () => location.reload());
window.addEventListener("beforeunload", event => {
  if (dirty || pending) { event.preventDefault(); event.returnValue = true; }
});
document.addEventListener("visibilitychange", () => {
  if (document.hidden && dirty && !conflicted) flush().catch(showError);
});

request("/api/review").then(result => {
  batch = result;
  byId("reviewer").textContent = "Reviewer · " + batch.reviewer;
  const requested = batch.cards.find(item => "#" + item.id === location.hash);
  const drafts = batch.cards.filter(item => item.status === "draft")
    .sort((a, b) => b.saved_at.localeCompare(a.saved_at));
  display(requested || drafts[0] || batch.cards.find(item => item.status === "open") || batch.cards[0]);
}).catch(showError);
