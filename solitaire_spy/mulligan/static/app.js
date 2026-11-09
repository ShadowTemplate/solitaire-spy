"use strict";

const $ = (s) => document.querySelector(s);
const PAGE = 20;
let S = null;            // server state: deck, tags, rules, sizes, modes
let summary = null;      // per-scope coverage
let scope = { size: 7, mode: "play" };
let filter = "undecided";
let offset = 0;
let landNames = new Set();
let deckName = null;     // currently selected deck list (sent with every request)

// ------------------------------------------------------------------ helpers
function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (v === true) el.setAttribute(k, "");
    else if (v !== false && v != null) el.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid != null) el.append(kid.nodeType ? kid : document.createTextNode(kid));
  return el;
}
const pct = (p) => p === 0 ? "0%" : p >= 0.1 ? (p * 100).toFixed(1) + "%" : p >= 0.001 ? (p * 100).toFixed(2) + "%" : (p * 100).toFixed(4) + "%";
const key = (sc) => `${sc.size}:${sc.mode}`;
// Keeping N cards means mulliganing 7-N times; every scope is judged on the 7-card hand you open with.
const sizeLabel = (n) => n === 7 ? "keep 7" : `keep ${n} (mull ${7 - n})`;
const scopeLabel = (sc = scope) => `${sizeLabel(sc.size)}, on the ${sc.mode}`;
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.add("show"); setTimeout(() => t.classList.remove("show"), 2200); }
async function api(path, method = "GET", body) {
  const r = await fetch(path, { method, headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify({ deck: deckName, ...body }) : undefined });
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}
const ruleById = (id) => S.rules.find((r) => r.id === id);
function newId() { let i = 1; while (ruleById("r" + i)) i++; return "r" + i; }

// ------------------------------------------------------------------ data flow
async function refresh() {
  summary = await api("/api/summary", "POST", { rules: S.rules });
  renderScopes(); renderRules(); await renderHands();
}
async function saveRules(rules) {
  await api("/api/rules", "PUT", { rules });
  S.rules = rules;
  await refresh();
}

// ------------------------------------------------------------------ scope grid
function renderScopes() {
  const g = h("div", { class: "scopegrid" }, h("div"));
  for (const size of S.sizes) g.append(h("div", { class: "colhead" }, sizeLabel(size)));
  for (const mode of S.modes) {
    g.append(h("div", { class: "lbl" }, mode === "play" ? "On play" : "On draw"));
    for (const size of S.sizes) {
      const r = summary[key({ size, mode })];
      const sel = size === scope.size && mode === scope.mode;
      g.append(h("button", { class: "scope" + (sel ? " sel" : ""), onclick: () => { scope = { size, mode }; offset = 0; renderScopes(); renderRules(); renderHands(); } },
        h("div", { class: "big " + (r.undecided < 1e-12 ? "zero" : "some") }, r.undecided < 1e-12 ? "✓ done" : pct(r.undecided)),
        h("div", { class: "bar" }, h("i", { class: "k", style: `width:${r.keep * 100}%` }), h("i", { class: "m", style: `width:${r.mull * 100}%` }), h("i", { class: "u", style: `width:${r.undecided * 100}%` })),
        h("div", { class: "sub" }, `keep ${pct(r.keep)} · mull ${pct(r.mull)}`),
        h("div", { class: "sub" }, `${r.covered_hands.toLocaleString()} / ${r.hands.toLocaleString()} hands`),
        r.conflict > 1e-12 ? h("div", { class: "sub err" }, `⚠ ${pct(r.conflict)} conflict`) : null));
    }
  }
  const root = $("#scopes");
  const cur = summary[key(scope)];
  let allHands = 0, allCovered = 0;
  for (const r of Object.values(summary)) { allHands += r.hands; allCovered += r.covered_hands; }
  const curCovered = cur.covered_hands;
  const stat = (label, big, sub) => h("div", { class: "stat" }, h("div", { class: "sub" }, label), h("div", { class: "big2" }, big), h("div", { class: "sub" }, sub));
  const counters = h("div", { class: "counters" },
    stat(`Selected scope (${scopeLabel()})`, `${curCovered.toLocaleString()} / ${cur.hands.toLocaleString()}`, `7-card hands fully decided (${pct(curCovered / cur.hands)}) · ${pct(cur.keep + cur.mull)} of probability`),
    stat("All 12 scopes", `${allCovered.toLocaleString()} / ${allHands.toLocaleString()}`, `hands fully decided (${pct(allCovered / allHands)})`));
  root.replaceChildren(counters, h("div", { class: "hint" }, "Every scope is judged on the 7-card hand you open with; “keep N (mull 7−N)” is the decision after 7−N mulligans. Goal: ✓ everywhere — every hand decided."), g);
}

// ------------------------------------------------------------------ rules list
function scopeText(r) {
  const sizes = S.sizes.filter((s) => r.sizes.includes(s));
  const sz = sizes.length === S.sizes.length ? "any size" : "keep " + sizes.join("/");
  const md = r.modes.length === 2 ? "play+draw" : r.modes[0] ? "on the " + r.modes[0] : "no mode";
  return `${sz} · ${md}`;
}
function renderRules() {
  $("#rulesScopeLabel").textContent = scopeLabel();
  const s = summary[key(scope)];
  const list = $("#rulesList");
  list.replaceChildren();
  S.rules.forEach((r, i) => {
    const st = s.rules[r.id];
    const sel = filter === "rule:" + r.id;
    const hasConflict = st && st.conflict > 1e-12;
    list.append(h("div", { class: "rule" + (r.enabled ? "" : " off") + (st ? "" : " na") + (sel ? " sel" : "") },
      h("div", { class: "meta" }, String(i + 1)),
      h("div", {},
        h("span", { class: "name", onclick: () => setFilter("rule:" + r.id) }, r.name || "(unnamed)"), " ",
        h("span", { class: "badge " + r.decision }, r.decision), " ",
        hasConflict ? h("span", { class: "badge warn", title: "Also matched by a rule with the opposite decision" }, "⚠ conflict " + pct(st.conflict)) : null,
        h("div", { class: "meta" }, scopeText(r) + (r.enabled ? "" : " · disabled") + (r.note ? " · " + r.note : "")),
        (r.include || []).length || (r.exclude || []).length ? h("div", { class: "meta" },
          [(r.include || []).length ? "needs " + r.include.map((x) => (x.min > 1 ? x.min + "× " : "") + targetName(x.target)).join(", ") : null,
           (r.exclude || []).length ? "without " + r.exclude.map((x) => targetName(x.target)).join(", ") : null].filter(Boolean).join(" · ")) : null,),
      h("div", { class: "pct" }, st ? pct(st.captured) : "—",
        st ? h("small", {}, st.raw > st.captured + 1e-12 ? `${pct(st.raw)} raw (${pct(st.raw - st.captured)} shadowed)` : "captured") : h("small", {}, "not in this scope")),
      h("div", { class: "actions" },
        h("button", { class: "ghost", title: "Higher priority", disabled: i === 0, onclick: () => move(i, -1) }, "↑"),
        h("button", { class: "ghost", title: "Lower priority", disabled: i === S.rules.length - 1, onclick: () => move(i, 1) }, "↓"),
        h("button", { class: "ghost", onclick: () => toggle(i) }, r.enabled ? "Disable" : "Enable"),
        h("button", { class: "ghost", onclick: () => openRule(r) }, "Edit"),
        h("button", { class: "ghost", onclick: () => duplicate(i) }, "Copy"),
        h("button", { class: "ghost", onclick: () => remove(i) }, "Delete"))));
  });
  list.append(h("div", { class: "undecided-row" + (filter === "undecided" ? " sel" : ""), onclick: () => setFilter("undecided") },
    h("span", {}, "Undecided"), h("b", {}, `${pct(s.undecided)} · ${s.undecided_hands.toLocaleString()} hands`)));
}
async function move(i, d) { const j = i + d; const rs = [...S.rules]; [rs[i], rs[j]] = [rs[j], rs[i]]; await saveRules(rs); }
async function toggle(i) { const rs = structuredClone(S.rules); rs[i].enabled = !rs[i].enabled; await saveRules(rs); }
async function duplicate(i) { const rs = structuredClone(S.rules); const c = structuredClone(rs[i]); c.id = newId(); c.name += " (copy)"; rs.splice(i + 1, 0, c); await saveRules(rs); }
async function remove(i) { if (!confirm(`Delete rule "${S.rules[i].name}"?`)) return; const rs = [...S.rules]; rs.splice(i, 1); await saveRules(rs); }

// ------------------------------------------------------------------ hands browser
function setFilter(f) { filter = f; offset = 0; renderRules(); renderHands(); }
function fillFilterOptions() {
  const sel = $("#handsFilter");
  const opts = [["undecided", "Undecided"], ["all", "All hands"], ["keep", "Decided: keep"], ["mull", "Decided: mull"], ["conflict", "Conflicts (keep and mull rules both match)"]];
  S.rules.forEach((r, i) => { opts.push(["rule:" + r.id, `Decided by #${i + 1} ${r.name}`]); opts.push(["matched:" + r.id, `Matches #${i + 1} ${r.name} (incl. shadowed)`]); });
  if (!opts.some(([v]) => v === filter)) filter = "undecided";
  sel.replaceChildren(...opts.map(([v, l]) => h("option", { value: v, selected: v === filter }, l)));
}
function chip(name, n) {
  return h("span", { class: "chip" + (landNames.has(name) ? " land" : "") }, n > 1 ? h("b", {}, n + "×") : null, name,
    h("img", { src: "/img/" + encodeURIComponent(name), loading: "lazy", alt: "" }));
}
let handsReq = 0;
async function renderHands() {
  fillFilterOptions();
  $("#handsScopeLabel").textContent = scopeLabel();
  const mine = ++handsReq;
  const has = $("#handsHas").value.split(",").map((x) => x.trim()).filter(Boolean)
    .map((x) => S.deck.find((c) => c.name.toLowerCase() === x.toLowerCase())?.name || S.deck.find((c) => c.name.toLowerCase().startsWith(x.toLowerCase()))?.name).filter(Boolean);
  const res = await api("/api/hands", "POST", { rules: S.rules, size: scope.size, mode: scope.mode, filter, has, offset, limit: PAGE });
  if (mine !== handsReq) return;
  $("#handsInfo").textContent = `${res.total.toLocaleString()} distinct 7-card hands · ${pct(res.mass)} of all opening hands · most likely first`;
  const list = $("#handsList");
  list.replaceChildren(...res.hands.map((hd) => h("div", { class: "hand" },
    h("div", {},
      h("div", { class: "cards" }, hd.cards.map(([n, c]) => chip(n, c))),
      h("div", { class: "meta hint" },
        hd.decision ? [h("span", { class: "badge " + hd.decision }, hd.decision), ` by #${S.rules.findIndex((r) => r.id === hd.rule) + 1} ${ruleById(hd.rule)?.name || ""}`] : h("span", { class: "badge none" }, "undecided"),
        hd.matched.length > 1 ? ` · matches ${hd.matched.map((id) => "#" + (S.rules.findIndex((r) => r.id === id) + 1)).join(", ")}` : "")),
    h("div", { class: "side" }, h("b", {}, pct(hd.p)), h("small", {}, "1 in " + Math.round(1 / hd.p).toLocaleString()),
      h("button", { class: "ghost", onclick: () => ruleFromHand(hd) }, "→ rule")))));
  if (!res.hands.length) list.append(h("div", { class: "hint" }, filter === "undecided" ? "Nothing undecided here 🎉" : "No hands."));
  $("#pageLabel").textContent = res.total ? `${offset + 1}–${Math.min(offset + PAGE, res.total)} of ${res.total.toLocaleString()}` : "";
  $("#prevPage").disabled = offset === 0;
  $("#nextPage").disabled = offset + PAGE >= res.total;
}

// ------------------------------------------------------------------ rule editor
let draft = null, draftIsNew = false, previewTimer = null;

function leaf(target = "tag:land") {
  return { type: "count", target, metric: "count", cmp: ">=", value: 1 };
}
function blankRule() {
  return { id: newId(), name: "", decision: "keep", enabled: true, note: "", sizes: [scope.size], modes: [scope.mode], include: [], exclude: [], condition: group("all") };
}
function group(mode = "all") { return { type: "group", mode, negate: false, children: [] }; }

function openRule(rule) {
  draftIsNew = !rule;
  draft = rule ? structuredClone(rule) : blankRule();
  draft.include = draft.include || []; draft.exclude = draft.exclude || [];
  renderRuleDialog();
  $("#ruleDialog").showModal();
}
function ruleFromHand(hd) {
  draftIsNew = true;
  draft = { ...blankRule(), name: hd.cards.map(([n, c]) => (c > 1 ? c + " " : "") + n).join(" + "),
    include: hd.cards.map(([n, c]) => ({ target: "card:" + n, min: c })) };
  renderRuleDialog();
  $("#ruleDialog").showModal();
}
function targetSelect(value, onchange) {
  return h("select", { onchange: (e) => onchange(e.target.value) },
    h("optgroup", { label: "Tags" }, Object.keys(S.tags).map((t) => h("option", { value: "tag:" + t, selected: value === "tag:" + t }, t))),
    h("optgroup", { label: "Cards" }, S.deck.map((c) => h("option", { value: "card:" + c.name, selected: value === "card:" + c.name }, c.name))));
}
function conditionNode(node, parent) {
  if (node.type === "count") {
    return h("div", { class: "leaf" },
      h("select", { onchange: (e) => { node.metric = e.target.value; schedulePreview(); } },
        h("option", { value: "count", selected: node.metric === "count" }, "copies of"),
        h("option", { value: "distinct", selected: node.metric === "distinct" }, "different cards among")),
      targetSelect(node.target, (v) => { node.target = v; schedulePreview(); }),
      h("select", { onchange: (e) => { node.cmp = e.target.value; schedulePreview(); } },
        [">=", "==", "<=", ">", "<", "!="].map((c) => h("option", { value: c, selected: node.cmp === c }, c))),
      h("input", { type: "number", min: 0, max: 7, value: node.value, oninput: (e) => { node.value = parseInt(e.target.value || "0", 10); schedulePreview(); } }),
      h("button", { class: "ghost", title: "Remove", onclick: () => { parent.children.splice(parent.children.indexOf(node), 1); renderRuleDialog(); schedulePreview(); } }, "✕"));
  }
  const box = h("div", { class: "group" },
    h("div", { class: "gh" },
      h("label", {}, h("input", { type: "checkbox", checked: node.negate, onchange: (e) => { node.negate = e.target.checked; schedulePreview(); } }), " NOT"),
      h("select", { onchange: (e) => { node.mode = e.target.value; schedulePreview(); } },
        h("option", { value: "all", selected: node.mode === "all" }, "ALL of the following"),
        h("option", { value: "any", selected: node.mode === "any" }, "ANY of the following")),
      h("button", { onclick: () => { node.children.push(leaf()); renderRuleDialog(); schedulePreview(); } }, "+ condition"),
      h("button", { onclick: () => { node.children.push(group("any")); renderRuleDialog(); schedulePreview(); } }, "+ group"),
      parent ? h("button", { class: "ghost", title: "Remove group", onclick: () => { parent.children.splice(parent.children.indexOf(node), 1); renderRuleDialog(); schedulePreview(); } }, "✕") : null));
  if (!node.children.length) box.append(h("div", { class: "hint" }, node.mode === "all" ? "Empty ALL matches every hand in scope." : "Empty ANY matches nothing."));
  node.children.forEach((c) => box.append(conditionNode(c, node)));
  return box;
}
// "Must include" (each target with a minimum number of copies among the 7 seen cards) and "Must not include"
// (none of that target may be among them). Cards not listed are simply allowed.
const targetName = (t) => t.slice(t.indexOf(":") + 1) + (t.startsWith("tag:") ? " (tag)" : "");
// Visual palette: click a card or tag to require it. Each click raises the minimum copies (≥1, ≥2, … up to what
// the deck holds), one more click forbids it ("must not include"), one more clears it. Right-click goes backwards.
let paletteQuery = "";
function tileMax(target) {
  const copies = (name) => S.deck.find((c) => c.name === name)?.count || 0;
  const total = target.startsWith("card:") ? copies(target.slice(5)) : (S.tags[target.slice(4)] || []).reduce((a, n) => a + copies(n), 0);
  return Math.max(1, Math.min(7, total));
}
function tileState(target) {
  const inc = draft.include.find((x) => x.target === target);
  if (inc) return { kind: "inc", min: inc.min || 1 };
  return draft.exclude.some((x) => x.target === target) ? { kind: "exc" } : { kind: "none" };
}
function stepTile(target, dir) {
  const max = tileMax(target), st = tileState(target);
  draft.include = draft.include.filter((x) => x.target !== target);
  draft.exclude = draft.exclude.filter((x) => x.target !== target);
  const inc = (min) => draft.include.push({ target, min });
  if (dir > 0) {
    if (st.kind === "none") inc(1);
    else if (st.kind === "inc" && st.min < max) inc(st.min + 1);
    else if (st.kind === "inc") draft.exclude.push({ target });
  } else {
    if (st.kind === "none") draft.exclude.push({ target });
    else if (st.kind === "exc") inc(max);
    else if (st.min > 1) inc(st.min - 1);
  }
}
function requirementsEditor() {
  const grid = h("div", { class: "tilegrid" });
  const tagRow = h("div", { class: "tagchips" });
  const summary = h("div", { class: "hint", style: "margin:6px 0 0" });
  const tile = (target, label, sub, img) => {
    const st = tileState(target);
    const badge = st.kind === "inc" ? "≥" + st.min : st.kind === "exc" ? "✗" : null;
    const el = h("button", { type: "button", class: `tile ${st.kind}${img ? "" : " tagtile"}`, title: `${label} — click: more copies required · right-click: back`,
      onclick: () => { stepTile(target, 1); draw(); schedulePreview(); },
      oncontextmenu: (e) => { e.preventDefault(); stepTile(target, -1); draw(); schedulePreview(); } },
      img ? h("img", { src: "/img/" + encodeURIComponent(img), loading: "lazy", alt: "" }) : null,
      h("span", { class: "tname" }, label), h("span", { class: "tsub" }, sub),
      badge ? h("span", { class: "tbadge" }, badge) : null);
    return el;
  };
  const draw = () => {
    const q = paletteQuery.trim().toLowerCase();
    const match = (s) => !q || s.toLowerCase().includes(q);
    tagRow.replaceChildren(...Object.keys(S.tags).filter(match).map((t) => tile("tag:" + t, t, `tag · ${S.tags[t].length} card${S.tags[t].length === 1 ? "" : "s"}`, null)));
    grid.replaceChildren(...S.deck.filter((c) => match(c.name)).map((c) => tile("card:" + c.name, c.name, `${c.count} in deck`, c.name)));
    const fmt = (it) => (it.min > 1 ? "≥" + it.min + " " : "") + targetName(it.target);
    summary.textContent = (draft.include.length || draft.exclude.length)
      ? [draft.include.length ? "Needs: " + draft.include.map(fmt).join(", ") : null, draft.exclude.length ? "Without: " + draft.exclude.map(fmt).join(", ") : null].filter(Boolean).join("  ·  ")
      : "Nothing selected — the rule only uses its extra condition below.";
  };
  const search = h("input", { type: "text", placeholder: "filter cards and tags…", value: paletteQuery, oninput: (e) => { paletteQuery = e.target.value; draw(); } });
  const box = h("div", { class: "group palette" },
    h("div", { class: "gh" }, h("b", {}, "Cards & tags"), search,
      h("button", { class: "ghost", onclick: () => { draft.include = []; draft.exclude = []; draw(); schedulePreview(); } }, "Clear all")),
    h("div", { class: "hint", style: "margin:0 0 6px" },
      "Click once = must have ≥1 of it among the 7 cards seen; again = ≥2, ≥3…; once more = must NOT have it; once more = clear. Right-click goes back a step."),
    tagRow, grid, summary);
  draw();
  return box;
}

function renderRuleDialog() {
  const d = $("#ruleDialog");
  const cb = (arr, val, label) => h("label", {}, h("input", { type: "checkbox", checked: arr.includes(val), onchange: (e) => { if (e.target.checked) arr.push(val); else arr.splice(arr.indexOf(val), 1); schedulePreview(); } }), " " + label);
  d.replaceChildren(
    h("h3", {}, draftIsNew ? "New rule" : "Edit rule"),
    h("div", { class: "formrow" }, h("label", { class: "t" }, "Name"), h("input", { type: "text", value: draft.name, placeholder: "e.g. Any land + Generous Ent", oninput: (e) => { draft.name = e.target.value; } })),
    h("div", { class: "formrow" }, h("label", { class: "t" }, "Decision"),
      h("select", { onchange: (e) => { draft.decision = e.target.value; renderRuleDialog(); } },
        h("option", { value: "keep", selected: draft.decision === "keep" }, "Keep"), h("option", { value: "mull", selected: draft.decision === "mull" }, "Mulligan"))),
    h("div", { class: "formrow cbs" }, h("label", { class: "t" }, "Hand size"), S.sizes.map((s) => cb(draft.sizes, s, sizeLabel(s).replace("keep ", "")))),
    h("div", { class: "formrow cbs" }, h("label", { class: "t" }, "Turn order"), S.modes.map((m) => cb(draft.modes, m, "on the " + m))),
    h("div", { class: "formrow" }, h("label", { class: "t" }, "Note"), h("input", { type: "text", value: draft.note || "", oninput: (e) => { draft.note = e.target.value; } })),
    requirementsEditor(),
    h("div", { class: "hint" }, "Extra condition (optional — everything above must also hold)"),
    conditionNode(draft.condition, null),
    h("div", { class: "preview", id: "preview" }, "…"),
    h("div", { class: "dlgfoot" }, h("span", { id: "dlgErr", class: "err" }),
      h("button", { onclick: () => d.close() }, "Cancel"),
      h("button", { class: "primary", onclick: commitRule }, "Save rule")));
  schedulePreview();
}
function draftRules() {
  const rs = structuredClone(S.rules);
  const i = rs.findIndex((r) => r.id === draft.id);
  if (i >= 0) rs[i] = structuredClone(draft); else rs.push(structuredClone(draft));
  return rs;
}
function schedulePreview() { clearTimeout(previewTimer); previewTimer = setTimeout(runPreview, 150); }
async function runPreview() {
  const box = $("#preview"); if (!box) return;
  try {
    const rs = draftRules();
    const sm = await api("/api/summary", "POST", { rules: rs });
    const g = h("div", { class: "pgrid" }, h("div"));
    S.sizes.forEach((s) => g.append(h("div", {}, s)));
    for (const mode of S.modes) {
      g.append(h("div", {}, mode));
      for (const size of S.sizes) {
        const st = sm[key({ size, mode })].rules[draft.id];
        const before = summary[key({ size, mode })].undecided, after = sm[key({ size, mode })].undecided;
        g.append(h("div", { class: "c" + (size === scope.size && mode === scope.mode ? " sel" : ""), title: "captured by this rule · undecided before → after" },
          st ? pct(st.captured) : "—", h("div", { class: "hint", style: "margin:0;font-size:10px" }, `${pct(before)}→${pct(after)}`)));
      }
    }
    box.replaceChildren(h("div", {}, "Captured by this rule (given its position in the list), and undecided before → after:"), g);
    $("#dlgErr").textContent = "";
  } catch (e) { box.textContent = ""; $("#dlgErr").textContent = e.message; }
}
async function commitRule() {
  if (!draft.name.trim()) { $("#dlgErr").textContent = "Give the rule a name."; return; }
  try { await saveRules(draftRules()); $("#ruleDialog").close(); toast("Rule saved"); }
  catch (e) { $("#dlgErr").textContent = e.message; }
}

// ------------------------------------------------------------------ tags editor
function openTags() {
  // rows keep their original name so a rename can be carried over to the rules that use the tag
  const rows = Object.entries(S.tags).map(([name, cards]) => ({ name, orig: name, cards: [...cards] }));
  const d = $("#tagsDialog");
  const usage = (orig) => S.rules.filter((r) => usesTag(r, orig)).length;
  const render = () => {
    d.replaceChildren(h("h3", {}, "Card tags"), h("div", { class: "hint" }, "Tag cards, then use the tag in rule conditions (“at least 1 of tag land_finder”). Renaming a tag updates the rules that use it."),
      ...rows.map((row) => h("div", { class: "tagrow" },
        h("div", { class: "formrow" },
          h("input", { type: "text", value: row.name, oninput: (e) => { row.name = e.target.value.trim(); } }),
          row.orig ? h("span", { class: "meta" }, `used by ${usage(row.orig)} rule${usage(row.orig) === 1 ? "" : "s"}`) : h("span", { class: "meta" }, "new"),
          h("button", { class: "ghost", onclick: () => { if (row.orig && usage(row.orig) && !confirm(`"${row.orig}" is used by ${usage(row.orig)} rule(s); they will match nothing. Delete anyway?`)) return; rows.splice(rows.indexOf(row), 1); render(); } }, "Delete tag")),
        h("div", { class: "cbs" }, S.deck.map((c) => h("label", {}, h("input", { type: "checkbox", checked: row.cards.includes(c.name), onchange: (e) => { if (e.target.checked) row.cards.push(c.name); else row.cards.splice(row.cards.indexOf(c.name), 1); } }), " " + c.name))))),
      h("div", { class: "formrow" }, h("input", { type: "text", id: "newTag", placeholder: "new_tag_name" }), h("button", { onclick: () => { const v = $("#newTag").value.trim(); if (v && !rows.some((r) => r.name === v)) { rows.push({ name: v, orig: null, cards: [] }); render(); } } }, "Add tag")),
      h("div", { class: "dlgfoot" }, h("span", { id: "tagErr", class: "err" }), h("button", { onclick: () => d.close() }, "Cancel"),
        h("button", { class: "primary", onclick: async () => {
          try {
            if (new Set(rows.map((r) => r.name)).size !== rows.length) throw new Error("Tag names must be unique and non-empty.");
            const tags = Object.fromEntries(rows.map((r) => [r.name, r.cards]));
            await api("/api/tags", "PUT", { tags });
            S.tags = tags;
            const rename = Object.fromEntries(rows.filter((r) => r.orig && r.orig !== r.name).map((r) => [r.orig, r.name]));
            if (Object.keys(rename).length) await saveRules(structuredClone(S.rules).map((r) => renameTag(r, rename)));
            d.close(); await refresh(); toast("Tags saved");
          } catch (e) { $("#tagErr").textContent = e.message; }
        } }, "Save tags")));
  };
  render(); d.showModal();
}
// Does a rule reference `tag:<name>` in its condition or requirement lists?
function usesTag(rule, name) {
  const inCond = (n) => n.type === "group" ? n.children.some(inCond) : n.target === "tag:" + name;
  return inCond(rule.condition) || [...(rule.include || []), ...(rule.exclude || [])].some((x) => x.target === "tag:" + name);
}
function renameTag(rule, rename) {
  const fix = (t) => (t.startsWith("tag:") && rename[t.slice(4)] ? "tag:" + rename[t.slice(4)] : t);
  const walk = (n) => { if (n.type === "group") n.children.forEach(walk); else n.target = fix(n.target); };
  walk(rule.condition);
  [...(rule.include || []), ...(rule.exclude || [])].forEach((x) => { x.target = fix(x.target); });
  return rule;
}

// ------------------------------------------------------------------ boot
async function loadDeck(name) {
  deckName = name;
  S = await api("/api/state?deck=" + encodeURIComponent(name));
  landNames = new Set(S.tags.land || []);
  $("#deckInfo").textContent = `${S.deck_size} cards · ${S.deck.length} distinct`;
  filter = "undecided"; offset = 0; $("#handsHas").value = "";
  await refresh();
}
(async function init() {
  const { decks, default: def } = await api("/api/decks");
  const sel = $("#deckSelect");
  sel.replaceChildren(...decks.map((d) => h("option", { value: d, selected: d === def }, d + (d === def ? " (default)" : ""))));
  sel.onchange = async (e) => { try { await loadDeck(e.target.value); } catch (err) { toast(err.message); } };
  $("#btnNewRule").onclick = () => openRule(null);
  $("#btnTags").onclick = openTags;
  $("#handsFilter").onchange = (e) => setFilter(e.target.value);
  let t; $("#handsHas").oninput = () => { clearTimeout(t); t = setTimeout(() => { offset = 0; renderHands(); }, 250); };
  $("#prevPage").onclick = () => { offset = Math.max(0, offset - PAGE); renderHands(); };
  $("#nextPage").onclick = () => { offset += PAGE; renderHands(); };
  await loadDeck(def);
})();
