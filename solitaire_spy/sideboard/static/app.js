"use strict";
const $ = (s) => document.querySelector(s);
const BASIC = new Set(["forest", "swamp", "mountain", "island", "plains"]);
const LAND_SYM = { same: "=", swap_forest_mountain: "↔", add_mountain: "+" };
const LAND_TXT = { same: "no change", swap_forest_mountain: "swap a Forest for a Mountain", add_mountain: "add a Mountain" };
const state = { deck: null, doc: null, selected: null, showAll: false, view: "matchup", filter: "" };
let saveTimer = null;

const key = (n) => n.toLowerCase();
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };

async function api(path, opts) {
  const r = await fetch(path, opts);
  const body = await r.json();
  if (!r.ok) throw new Error(body.error || r.statusText);
  return body;
}
function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.style.display = "block";
  setTimeout(() => { t.style.display = "none"; }, 4000);
}

// ------------------------------------------------------------------ deck helpers
function deckMaps(deck) {
  const main = new Map(deck.main.map((c) => [key(c.name), c.count]));
  const side = new Map(deck.sideboard.map((c) => [key(c.name), c.count]));  // the server only serves lists with a sideboard
  return { main, side };
}
const LAND_DELTA = { same: 0, swap_forest_mountain: 0, add_mountain: 1 };
// Absolute land count for a matchup: basic lands in the deck's main plus the matchup's land change.
const landCount = (m) => [...state.maps.main].filter(([k]) => BASIC.has(k)).reduce((a, [, n]) => a + n, 0) + LAND_DELTA[m.lands];
const inMain = (card) => state.maps.main.get(key(card)) || 0;
const available = (card) => state.maps.side.get(key(card)) || 0;  // only what the deck's sideboard holds

// ------------------------------------------------------------------ persistence
function scheduleSave() {
  $("#saveState").textContent = "Saving…";
  clearTimeout(saveTimer);
  saveTimer = setTimeout(async () => {
    try {
      await api("/api/matchups", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(state.doc) });
      $("#saveState").textContent = "Saved";
    } catch (e) { $("#saveState").textContent = "Not saved"; toast("Save failed: " + e.message); }
  }, 400);
}

// ------------------------------------------------------------------ matchup list
const current = () => state.doc.matchups.find((m) => m.id === state.selected);

// Each matchup carries `target`: the copies of every card in its post-board list. For the selected
// deck: cut max(0, have - target), bring in max(0, target - have). Cards unknown to the target are left alone.
const targetKeys = new WeakMap();
function targetOf(m, card) {
  if (!targetKeys.has(m)) targetKeys.set(m, new Map(Object.entries(m.target).map(([c, n]) => [key(c), [c, n]])));
  return targetKeys.get(m).get(key(card));
}
// The swap for the selected deck, per matchup:
//  1. cut max(0, have - target); bring in max(0, target - have), limited to what the sideboard holds.
//  2. if the reference list brings in *every* sideboard copy of a card, bring in every copy this deck has
//     (e.g. a 4th Accursed Marauder where the reference sideboard runs 3).
//  3. the swap must stay balanced: the surplus on one side is taken from the other side's ranking,
//     first card first, as far as the deck has spare copies.
const plans = new Map();
function plan(m) {
  if (plans.has(m.id)) return plans.get(m.id);
  const out = new Map(), inn = new Map();
  for (const e of m.out) {
    const t = targetOf(m, e.card);
    const n = t ? Math.max(0, inMain(e.card) - t[1]) : 0;
    if (n) out.set(e.card, n);
  }
  const refSide = state.doc.reference_deck.sideboard;
  for (const e of m.in) {
    const t = targetOf(m, e.card);
    if (!t) continue;
    const full = e.basis === "sheet" && refSide[e.card] && e.copies >= refSide[e.card];
    const n = full ? available(e.card) : Math.max(0, Math.min(t[1] - inMain(e.card), available(e.card)));
    if (n) inn.set(e.card, n);
  }
  const sum = (map) => [...map.values()].reduce((a, n) => a + n, 0);
  const fill = (map, entries, spareOf, extra, opposite) => {
    for (const e of entries) {
      if (extra <= 0) break;
      if (e.basis === "untouchable" || opposite.has(e.card)) continue;  // never cut and add the same card
      const take = Math.min(spareOf(e.card) - (map.get(e.card) || 0), extra);
      if (take > 0) { map.set(e.card, (map.get(e.card) || 0) + take); extra -= take; }
    }
  };
  if (sum(inn) > sum(out)) fill(out, m.out, inMain, sum(inn) - sum(out), inn);
  else if (sum(out) > sum(inn)) fill(inn, m.in, available, sum(out) - sum(inn), out);
  const result = { out, in: inn };
  plans.set(m.id, result);
  return result;
}
const need = (m, side, card) => plan(m)[side].get(card) || 0;
const needTotal = (m, side) => [...plan(m)[side].values()].reduce((a, n) => a + n, 0);
function setTarget(m, card, value) {
  const t = targetOf(m, card);
  m.target[t[0]] = Math.max(0, Math.min(8, value));
  targetKeys.delete(m);
  scheduleSave(); render();
}

function renderList() {
  const box = $("#matchupList"); box.replaceChildren();
  const f = state.filter.toLowerCase();
  for (const m of state.doc.matchups) {
    if (f && !m.name.toLowerCase().includes(f)) continue;
    const row = el("div", "mu" + (m.id === state.selected ? " sel" : ""));
    row.append(el("span", "sym", LAND_SYM[m.lands]), el("span", "nm", m.name), el("span", "sz", (needTotal(m, "out") === needTotal(m, "in") ? `+/- ${needTotal(m, "out")}` : `−${needTotal(m, "out")} +${needTotal(m, "in")}`)));
    row.title = `${landCount(m)} lands: ${LAND_TXT[m.lands]}`;
    row.onclick = () => { state.selected = m.id; setView("matchup"); };
    box.append(row);
  }
}

// ------------------------------------------------------------------ detail with drag & drop
function renderDetail() {
  const box = $("#detail"); box.replaceChildren();
  const m = current();
  if (!m) return;
  const card = el("div", "card");
  const head = el("div", "dethead");
  head.append(el("h2", null, m.name), el("span", "chip", `${landCount(m)} lands: ${LAND_TXT[m.lands]}`),
    el("span", "chip", `swap: ${needTotal(m, "out")} out / ${needTotal(m, "in")} in`));
  card.append(head);
  if (m.notes) card.append(el("div", "note", m.notes));
  const cols = el("div", "cols");
  cols.append(renderColumn(m, "out"), renderColumn(m, "in"));
  card.append(cols);
  const t = el("label", "toggle");
  const cb = el("input"); cb.type = "checkbox"; cb.checked = state.showAll;
  cb.onchange = () => { state.showAll = cb.checked; renderDetail(); };
  t.append(cb, document.createTextNode("Also show cards that are not in / not available to this deck list (dimmed)"));
  card.append(t);
  box.append(card);
}

function renderColumn(m, side) {
  const col = el("div", "col " + side);
  col.append(el("h3", null, side === "out" ? "Side OUT — cut first at the top" : "Side IN — bring in first at the top"));
  col.append(el("p", "hint", side === "out"
    ? "Least useful cards in this matchup. Drag to re-rank."
    : "Most important cards to add. Drag to re-rank."));
  const list = m[side];
  const usable = (e) => (side === "out" ? inMain(e.card) > 0 : available(e.card) > 0);
  const visible = list.filter((e) => state.showAll || usable(e));
  let rank = 0, lastBasis = null;
  for (const e of visible) {
    const ok = usable(e);
    const n = need(m, side, e.card);
    // a card the deck actually has to swap is "recommended"; the rest is grouped by how it was ranked
    const tier = n > 0 ? "sheet" : (e.basis === "optional" || e.basis === "untouchable" ? e.basis : "inferred");
    if (tier !== lastBasis) {
      col.append(el("div", "tier", { sheet: "Recommended", optional: "Optional", inferred: "Other cards — frequency order", untouchable: "Untouchable — never cut in any matchup" }[tier]));
      lastBasis = tier;
    }
    const row = el("div", `row ${tier}${ok ? "" : " absent"}`);
    row.draggable = true;
    row.dataset.card = e.card;
    const name = el("span", "cn", e.card);
    // copies the deck holds: in the main for OUT, in the sideboard for IN
    const have = el("span", "have", `/${side === "out" ? inMain(e.card) : available(e.card)}`);
    have.title = side === "out" ? "copies in the main deck" : "copies in the sideboard";
    const tgt = targetOf(m, e.card);
    const badge = el("span", "badge" + (n ? "" : " zero"), n ? `${side === "out" ? "−" : "+"}${n}` : "·");
    badge.title = n ? `copies to swap for this deck list (post-board target: ${tgt[1]})`
      : tgt ? `no swap needed (post-board target: ${tgt[1]}, you play ${inMain(e.card)})` : "no post-board target";
    const step = el("span", "stepper");
    if (tgt) {
      // the stepper edits the post-board target: more copies of the card means fewer cut / more brought in
      for (const [label, d] of [["−", side === "out" ? 1 : -1], ["+", side === "out" ? -1 : 1]]) {
        const b = el("button", null, label);
        b.onclick = () => setTarget(m, e.card, tgt[1] + d);
        step.append(b);
      }
    }
    const qty = el("span", "qty"); qty.append(badge, have);
    row.append(el("span", "rk", ok ? "#" + (++rank) : ""), name, qty, step);
    attachDrag(row, m, side, e.card);
    col.append(row);
  }
  if (side === "out") {
    const ranked = new Set(list.map((e) => key(e.card)));
    const unranked = [...state.maps.main.keys()].filter((k) => !ranked.has(k));
    if (unranked.length) col.append(el("p", "hint", "Not ranked: " + state.deck.main.filter((c) => unranked.includes(key(c.name))).map((c) => c.name).join(", ")));
  }
  return col;
}

let dragged = null;
function attachDrag(row, m, side, card) {
  row.addEventListener("dragstart", (ev) => {
    dragged = { id: m.id, side, card };
    row.classList.add("dragging");
    ev.dataTransfer.effectAllowed = "move";
    ev.dataTransfer.setData("text/plain", card);
  });
  row.addEventListener("dragend", () => { dragged = null; row.classList.remove("dragging"); clearOver(); });
  row.addEventListener("dragover", (ev) => {
    if (!dragged || dragged.id !== m.id || dragged.side !== side || dragged.card === card) return;
    ev.preventDefault();
    clearOver();
    const r = row.getBoundingClientRect();
    row.classList.add(ev.clientY < r.top + r.height / 2 ? "over-top" : "over-bottom");
  });
  row.addEventListener("drop", (ev) => {
    if (!dragged || dragged.id !== m.id || dragged.side !== side || dragged.card === card) return;
    ev.preventDefault();
    const r = row.getBoundingClientRect();
    moveCard(m, side, dragged.card, card, ev.clientY >= r.top + r.height / 2);
  });
}
function clearOver() { document.querySelectorAll(".over-top,.over-bottom").forEach((n) => n.classList.remove("over-top", "over-bottom")); }

// Move `card` next to `target` in the full list (hidden entries keep their relative place).
function moveCard(m, side, card, target, after) {
  const list = m[side];
  const from = list.findIndex((e) => e.card === card);
  const [item] = list.splice(from, 1);
  const to = list.findIndex((e) => e.card === target);
  list.splice(after ? to + 1 : to, 0, item);
  scheduleSave();
  render();
}

// ------------------------------------------------------------------ overview matrix
function renderMatrix() {
  const box = $("#matrixView"); box.replaceChildren();
  box.append(el("h2", null, "All matchups"), el("p", "hint", "Copies to swap for the selected deck list: red − = side out, green + = side in. Click a matchup to open it."));
  const cards = new Map();
  for (const m of state.doc.matchups) for (const side of ["out", "in"]) for (const e of m[side]) if (need(m, side, e.card) > 0) cards.set(key(e.card), e.card);
  const cols = [...cards.values()].sort((a, b) => (inMain(b) > 0) - (inMain(a) > 0) || a.localeCompare(b));
  const wrap = el("div", "matrix-wrap"), table = el("table", "matrix");
  const hr = el("tr"); hr.append(el("th", "corner"));
  cols.forEach((c) => hr.append(el("th", null, c)));
  const thead = el("thead"); thead.append(hr); table.append(thead);
  const tb = el("tbody");
  for (const m of state.doc.matchups) {
    const tr = el("tr");
    const th = el("th", "rowh", `${LAND_SYM[m.lands]} ${m.name}`);
    th.onclick = () => { state.selected = m.id; setView("matchup"); };
    tr.append(th);
    for (const c of cols) {
      const o = need(m, "out", c), i = need(m, "in", c);
      const td = el("td");
      if (o) { td.className = "o"; td.textContent = "−" + o; }
      else if (i) { td.className = "i"; td.textContent = "+" + i; }
      tr.append(td);
    }
    tb.append(tr);
  }
  table.append(tb); wrap.append(table); box.append(wrap);
}

// ------------------------------------------------------------------ wiring
function setView(v) {
  state.view = v;
  $("#matchupView").hidden = v !== "matchup";
  $("#matrixView").hidden = v !== "matrix";
  $("#tabMatchup").classList.toggle("sel", v === "matchup");
  $("#tabMatrix").classList.toggle("sel", v === "matrix");
  render();
}
function render() {
  plans.clear();  // deck, targets or rankings may have changed
  if (state.view === "matchup") { renderList(); renderDetail(); } else renderMatrix();
}
async function loadDeck(name) {
  state.deck = await api("/api/deck?name=" + encodeURIComponent(name));
  state.maps = deckMaps(state.deck);
  const n = state.deck.main.reduce((a, c) => a + c.count, 0), s = state.deck.sideboard.reduce((a, c) => a + c.count, 0);
  $("#deckInfo").textContent = `${n} main · ${s} sideboard`;
  render();
}
async function init() {
  const [decks, doc] = await Promise.all([api("/api/decks"), api("/api/matchups")]);
  state.doc = doc;
  state.selected = doc.matchups[0].id;
  const sel = $("#deckSelect");
  decks.decks.forEach((d) => sel.append(new Option(d, d)));
  sel.value = decks.default;
  sel.onchange = () => loadDeck(sel.value).catch((e) => toast(e.message));
  $("#filter").oninput = (ev) => { state.filter = ev.target.value; renderList(); };
  $("#tabMatchup").onclick = () => setView("matchup");
  $("#tabMatrix").onclick = () => setView("matrix");
  await loadDeck(decks.default);
}
init().catch((e) => toast(e.message));
