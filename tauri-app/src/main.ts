import "./styles.css";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { open, save } from "@tauri-apps/plugin-dialog";
import { openPath } from "@tauri-apps/plugin-opener";

// ---------- helpers ----------

const $ = <T extends HTMLElement = HTMLElement>(id: string): T =>
  document.getElementById(id) as T;

function toast(msg: string, kind: "ok" | "err" | "" = "", ms = 3500) {
  const t = $("toast");
  t.textContent = msg;
  t.className = `toast ${kind}`;
  window.clearTimeout((t as any)._timer);
  (t as any)._timer = window.setTimeout(() => t.classList.add("hidden"), ms);
}

function timestamp(): string {
  return new Date().toTimeString().slice(0, 8);
}

interface Stats {
  total_pages: number;
  marked: number;
  unmarked: number;
  // product name -> qty bucket ("1"/"2"/"3"/"more") -> count
  counts: Record<string, Record<string, number>>;
}

// ---------- tab switching ----------

document.querySelectorAll<HTMLButtonElement>(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    $(`panel-${btn.dataset.tab}`).classList.add("active");
  });
});

// ---------- generic processor tab wiring ----------

interface ProcTab {
  key: "sr" | "st" | "dd";
  eventTab: string; // tab name in Rust events
  command: string;
  outputSuffix: string;
  defaultDirName: string; // subfolder under ~/Documents/Shiprocket Label Processor
  has4x4: boolean;
  hasStats: boolean;
}

const procState: Record<string, { processing: boolean; output: string; inputs: string[] }> = {};

function appendLog(key: string, msg: string) {
  const log = $(`${key}-log`);
  log.textContent += `[${timestamp()}] ${msg}\n`;
  log.scrollTop = log.scrollHeight;
}

function renderStats(el: HTMLElement, stats: Stats) {
  const fmtCounts = (c: Record<string, number>) =>
    Object.entries(c)
      .filter(([, v]) => v > 0)
      .map(([k, v]) => `<div>${k === "more" ? "4+ packs" : `${k}x packs`}: ${v}</div>`)
      .join("") || `<div class="muted">none</div>`;
  const productCols = Object.entries(stats.counts)
    .map(
      ([name, c]) =>
        `<div class="col"><h3>${name} Products</h3>${fmtCounts(c)}</div>`
    )
    .join("");
  el.innerHTML = `
    <div class="col"><h3>Pages</h3>
      <div>Marked: ${stats.marked}</div>
      <div>Unmarked: ${stats.unmarked}</div>
    </div>${productCols}`;
}

function setupProcessorTab(tab: ProcTab) {
  const k = tab.key;
  procState[tab.eventTab] = { processing: false, output: "", inputs: [] };

  // Per-tab default output folder (persisted across sessions)
  const dirStorageKey = `defaultDir:${tab.defaultDirName}`;
  const dirInput = $(`${k}-default-dir`) as HTMLInputElement;
  const storedDir = localStorage.getItem(dirStorageKey);
  if (storedDir) {
    dirInput.value = storedDir;
  } else {
    invoke("default_output_dir", { tabName: tab.defaultDirName })
      .then((d) => {
        dirInput.value = d as string;
      })
      .catch(() => {});
  }
  const setDefaultDir = (dir: string) => {
    dirInput.value = dir;
    localStorage.setItem(dirStorageKey, dir);
  };

  $(`${k}-browse-dir`).addEventListener("click", async () => {
    const dir = await open({
      title: "Select Default Output Folder",
      directory: true,
      defaultPath: dirInput.value || undefined,
    });
    if (typeof dir === "string") setDefaultDir(dir);
  });

  $(`${k}-browse-in`).addEventListener("click", async () => {
    const picked = await open({
      title: "Select Input PDF File(s)",
      filters: [{ name: "PDF files", extensions: ["pdf"] }],
      multiple: true,
    });
    const files = typeof picked === "string" ? [picked] : picked ?? [];
    if (!files.length) return;

    procState[tab.eventTab].inputs = files;
    const firstName = files[0].split("/").pop() ?? files[0];
    ($(`${k}-input`) as HTMLInputElement).value =
      files.length === 1 ? files[0] : `${firstName}  (+${files.length - 1} more)`;

    const dot = firstName.lastIndexOf(".");
    const base = dot > 0 ? firstName.slice(0, dot) : firstName;
    const dir = dirInput.value || files[0].slice(0, files[0].lastIndexOf("/"));
    const outName =
      files.length === 1 ? `${base}${tab.outputSuffix}` : `combined_${files.length}_files${tab.outputSuffix}`;
    ($(`${k}-output`) as HTMLInputElement).value = `${dir}/${outName}`;

    if (files.length === 1) {
      appendLog(k, `Input file selected: ${firstName}`);
    } else {
      appendLog(k, `${files.length} input files selected (processed together, sorted as one):`);
      files.forEach((f) => appendLog(k, `  • ${f.split("/").pop()}`));
    }
  });

  $(`${k}-browse-out`).addEventListener("click", async () => {
    const file = await save({
      title: "Save Processed PDF",
      defaultPath: ($(`${k}-output`) as HTMLInputElement).value || undefined,
      filters: [{ name: "PDF files", extensions: ["pdf"] }],
    });
    if (file) {
      ($(`${k}-output`) as HTMLInputElement).value = file;
      const folder = file.slice(0, file.lastIndexOf("/"));
      if (folder) setDefaultDir(folder);
      appendLog(k, `Output location set: ${file.split("/").pop()}`);
    }
  });

  $(`${k}-open`).addEventListener("click", async () => {
    const out = procState[tab.eventTab].output;
    if (out) {
      try {
        await openPath(out);
      } catch (e) {
        toast(`Could not open PDF: ${e}`, "err");
      }
    }
  });

  const clearBtn = document.getElementById(`${k}-clear`);
  clearBtn?.addEventListener("click", () => {
    procState[tab.eventTab].inputs = [];
    ($(`${k}-input`) as HTMLInputElement).value = "";
    ($(`${k}-output`) as HTMLInputElement).value = "";
    $(`${k}-log`).textContent = "";
    const st = $(`${k}-status`);
    st.textContent = "Ready to process";
    st.className = "status";
    ($(`${k}-open`) as HTMLButtonElement).disabled = true;
    const stats = document.getElementById(`${k}-stats`);
    if (stats) stats.innerHTML = `<span class="muted">Statistics will appear here after processing</span>`;
    const cb = document.getElementById(`${k}-4x4`) as HTMLInputElement | null;
    if (cb) cb.checked = false;
  });

  document.getElementById(`${k}-clear-log`)?.addEventListener("click", () => {
    $(`${k}-log`).textContent = "";
  });

  document.getElementById(`${k}-save-log`)?.addEventListener("click", async () => {
    const file = await save({
      title: "Save Log File",
      filters: [{ name: "Text files", extensions: ["txt"] }],
    });
    if (file) {
      try {
        await invoke("save_text_file", { path: file, content: $(`${k}-log`).textContent ?? "" });
        appendLog(k, `Log saved to ${file.split("/").pop()}`);
      } catch (e) {
        toast(`Could not save log: ${e}`, "err");
      }
    }
  });

  $(`${k}-process`).addEventListener("click", async () => {
    const state = procState[tab.eventTab];
    if (state.processing) return;
    const inputs = state.inputs;
    const output = ($(`${k}-output`) as HTMLInputElement).value;
    if (!inputs.length) return toast("Please select at least one input PDF file.", "err");
    if (!output) return toast("Please select an output PDF file.", "err");

    state.processing = true;
    state.output = output;
    const btn = $(`${k}-process`) as HTMLButtonElement;
    btn.disabled = true;
    btn.textContent = "Processing…";
    ($(`${k}-open`) as HTMLButtonElement).disabled = true;
    $(`${k}-log`).textContent = "";
    const st = $(`${k}-status`);
    st.textContent = "Processing started…";
    st.className = "status";
    $(`${k}-progress`).classList.add("indeterminate");

    const args: Record<string, unknown> = { inputs, output };
    if (tab.has4x4) args.is4x4 = ($(`${k}-4x4`) as HTMLInputElement).checked;

    try {
      const stats = (await invoke(tab.command, args)) as Stats;
      st.textContent = "Processing completed successfully!";
      st.className = "status ok";
      ($(`${k}-open`) as HTMLButtonElement).disabled = false;
      if (tab.hasStats) renderStats($(`${k}-stats`), stats);
      toast(`PDF processed successfully — saved to ${output.split("/").pop()}`, "ok");
      appendLog(k, "Ready for next processing task");
    } catch (e) {
      st.textContent = "Processing failed";
      st.className = "status err";
      toast(String(e), "err", 6000);
      appendLog(k, `ERROR: ${e}`);
    } finally {
      state.processing = false;
      btn.disabled = false;
      btn.textContent = "Process PDF";
      const fill = $(`${k}-progress`);
      fill.classList.remove("indeterminate");
      fill.style.width = "0%";
      const det = document.getElementById(`${k}-progress-detail`);
      if (det) det.textContent = "";
    }
  });
}

setupProcessorTab({
  key: "sr",
  eventTab: "shiprocket",
  command: "process_shiprocket",
  outputSuffix: "_processed.pdf",
  defaultDirName: "label_processor",
  has4x4: true,
  hasStats: true,
});
setupProcessorTab({
  key: "st",
  eventTab: "st",
  command: "process_st",
  outputSuffix: "_ST_processed.pdf",
  defaultDirName: "st_courier",
  has4x4: false,
  hasStats: false,
});
setupProcessorTab({
  key: "dd",
  eventTab: "delhivery",
  command: "process_delhivery",
  outputSuffix: "_processed.pdf",
  defaultDirName: "delhivery_direct",
  has4x4: false,
  hasStats: false,
});

const tabToKey: Record<string, string> = { shiprocket: "sr", st: "st", delhivery: "dd" };

listen<{ tab: string; message: string }>("proc-log", (e) => {
  const k = tabToKey[e.payload.tab];
  if (k) appendLog(k, e.payload.message);
});

listen<{ tab: string; current: number; total: number }>("proc-progress", (e) => {
  const k = tabToKey[e.payload.tab];
  if (!k) return;
  const fill = $(`${k}-progress`);
  fill.classList.remove("indeterminate");
  fill.style.width = `${(e.payload.current / Math.max(1, e.payload.total)) * 100}%`;
  const det = document.getElementById(`${k}-progress-detail`);
  if (det) det.textContent = `${e.payload.current}/${e.payload.total} pages processed`;
});

// ---------- Courier PDF Generator tab ----------

interface QueueOrder {
  order_id: string;
  phone: string;
  items: string;
  address: string;
}

const queue: QueueOrder[] = [];
const queueSelected = new Set<number>();

function updateQueueControls() {
  ($("c-remove-selected") as HTMLButtonElement).disabled = queueSelected.size === 0;
  const all = $("c-select-all") as HTMLInputElement;
  all.checked = queue.length > 0 && queueSelected.size === queue.length;
  all.indeterminate = queueSelected.size > 0 && queueSelected.size < queue.length;
  $("c-queue-count").textContent = queue.length
    ? queueSelected.size
      ? `(${queueSelected.size} of ${queue.length} selected)`
      : `(${queue.length})`
    : "";
}

function renderQueue() {
  const tbody = document.querySelector<HTMLTableSectionElement>("#c-table tbody")!;
  tbody.innerHTML = "";
  queue.forEach((o, idx) => {
    const tr = document.createElement("tr");

    const tdCheck = document.createElement("td");
    tdCheck.className = "check-col";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = queueSelected.has(idx);
    cb.addEventListener("change", () => {
      if (cb.checked) queueSelected.add(idx);
      else queueSelected.delete(idx);
      updateQueueControls();
    });
    tdCheck.appendChild(cb);
    tr.appendChild(tdCheck);

    const mkTd = (t: string) => {
      const td = document.createElement("td");
      td.textContent = t;
      return td;
    };
    tr.appendChild(mkTd(o.order_id));
    tr.appendChild(mkTd(o.phone));
    tr.appendChild(mkTd(o.items));
    tr.appendChild(mkTd(o.address.replace(/\n/g, ", ")));

    // clicking the row (outside inputs) toggles selection too
    tr.addEventListener("click", (e) => {
      if ((e.target as HTMLElement).tagName === "INPUT") return;
      cb.checked = !cb.checked;
      cb.dispatchEvent(new Event("change"));
    });
    tbody.appendChild(tr);
  });
  updateQueueControls();
}

$("c-select-all").addEventListener("change", () => {
  const all = $("c-select-all") as HTMLInputElement;
  queueSelected.clear();
  if (all.checked) queue.forEach((_, i) => queueSelected.add(i));
  renderQueue();
});

$("c-remove-selected").addEventListener("click", () => {
  if (!queueSelected.size) return;
  const removed = queueSelected.size;
  const keep = queue.filter((_, i) => !queueSelected.has(i));
  queue.length = 0;
  queue.push(...keep);
  queueSelected.clear();
  renderQueue();
  toast(`Removed ${removed} order${removed > 1 ? "s" : ""} from the queue.`, "");
});

$("c-add").addEventListener("click", () => {
  const order_id = ($("c-order-id") as HTMLInputElement).value.trim();
  const phone = ($("c-phone") as HTMLInputElement).value.trim();
  const items = ($("c-items") as HTMLInputElement).value.trim();
  const address = ($("c-address") as HTMLTextAreaElement).value.trim();
  if (!order_id || !address) {
    return toast("Order ID and Address are required.", "err");
  }
  queue.push({ order_id, phone, items, address });
  renderQueue();
  ($("c-order-id") as HTMLInputElement).value = "";
  ($("c-phone") as HTMLInputElement).value = "";
  ($("c-items") as HTMLInputElement).value = "";
  ($("c-address") as HTMLTextAreaElement).value = "";
  $("c-order-id").focus();
});

$("c-fetch").addEventListener("click", async () => {
  const key = ($("c-order-id") as HTMLInputElement).value.trim();
  if (!key) return toast("Please enter an Order ID", "err");
  const btn = $("c-fetch") as HTMLButtonElement;
  btn.disabled = true;
  btn.textContent = "Fetching…";
  try {
    const o = (await invoke("fetch_order", {
      searchKey: key,
      searchType: "order_id",
    })) as QueueOrder;
    ($("c-order-id") as HTMLInputElement).value = o.order_id;
    ($("c-phone") as HTMLInputElement).value = o.phone;
    ($("c-items") as HTMLInputElement).value = o.items;
    ($("c-address") as HTMLTextAreaElement).value = o.address;
    toast("Order details fetched from Shiprocket", "ok");
  } catch (e) {
    toast(String(e), "err", 6000);
    if (String(e).includes("configure")) openSettings();
  } finally {
    btn.disabled = false;
    btn.textContent = "Fetch Info";
  }
});

$("c-generate").addEventListener("click", async () => {
  if (!queue.length) return toast("No orders to process.", "err");
  const btn = $("c-generate") as HTMLButtonElement;
  btn.disabled = true;
  btn.textContent = "Generating…";
  try {
    const path = (await invoke("generate_labels", {
      orders: queue,
      is4x4: ($("c-4x4") as HTMLInputElement).checked,
    })) as string;
    toast(`Labels generated: ${path.split("/").pop()}`, "ok");
    await openPath(path).catch(() => {});
  } catch (e) {
    toast(String(e), "err", 6000);
  } finally {
    btn.disabled = false;
    btn.textContent = "Generate Labels PDF";
  }
});

$("c-shopify").addEventListener("click", async () => {
  if (!queue.length) return toast("No orders to update.", "err");
  const btn = $("c-shopify") as HTMLButtonElement;
  btn.disabled = true;
  btn.textContent = "Updating…";
  try {
    const report = (await invoke("update_shopify", {
      orderIds: queue.map((o) => o.order_id),
    })) as { total: number; updated: string[]; failed: string[] };
    let msg = `Processed ${report.total} orders. Success: ${report.updated.length}, Failed: ${report.failed.length}`;
    if (report.failed.length) msg += ` (failed: ${report.failed.join(", ")})`;
    toast(msg, report.failed.length ? "err" : "ok", 7000);
  } catch (e) {
    toast(String(e), "err", 6000);
    if (String(e).includes("configure")) openSettings();
  } finally {
    btn.disabled = false;
    btn.textContent = "Update Shopify";
  }
});

// ---------- Configuration panel ----------

interface ProductRule {
  name: string;
  stamp_label: string;
  canonical_name: string;
  keywords: string[];
  skus: string[];
  track_in_stats: boolean;
}

interface RulesConfig {
  products: ProductRule[];
  shiprocket: {
    stamp_x: number;
    stamp_y: number;
    stamp_size: number;
    stamp_color: string;
    crop_mm: number;
    crop_skip_last_page: boolean;
    group_max_qty: number;
  };
  st: { line_filter: string; phone_pattern: string; phone_note: string };
  delhivery: {
    line_filter: string;
    skip_contains: string[];
    skip_prefixes: string[];
    qty_patterns: string[];
    qty_scan_lines: number;
    stamp_x: number;
    stamp_from_bottom: number;
    stamp_size: number;
    stamp_color: string;
    phone_pattern: string;
    phone_note: string;
  };
  courier: {
    brand_name: string;
    title_color: string;
    from_address: string;
    from_address_4x4: string;
  };
}

interface AppConfig {
  email: string;
  password: string;
  token: string;
  shopify_url: string;
  shopify_token: string;
  rules: RulesConfig;
}

// Working copy edited by the panel; products live here, scalar fields are
// read from the inputs at save time.
let cfgProducts: ProductRule[] = [];

const val = (id: string) => ($(id) as HTMLInputElement).value;
const setVal = (id: string, v: string | number) => {
  ($(id) as HTMLInputElement).value = String(v);
};
const checked = (id: string) => ($(id) as HTMLInputElement).checked;
const setChecked = (id: string, v: boolean) => {
  ($(id) as HTMLInputElement).checked = v;
};
const splitCsv = (s: string) =>
  s.split(",").map((x) => x.trim()).filter((x) => x.length > 0);

function renderProductsTable() {
  const tbody = document.querySelector<HTMLTableSectionElement>("#cfg-products tbody")!;
  tbody.innerHTML = "";
  cfgProducts.forEach((p, idx) => {
    const tr = document.createElement("tr");
    const mkInput = (value: string, onChange: (v: string) => void, width = "") => {
      const td = document.createElement("td");
      const inp = document.createElement("input");
      inp.type = "text";
      inp.value = value;
      if (width) inp.style.minWidth = width;
      inp.addEventListener("change", () => onChange(inp.value));
      td.appendChild(inp);
      return td;
    };
    tr.appendChild(mkInput(p.name, (v) => (p.name = v), "70px"));
    tr.appendChild(mkInput(p.stamp_label, (v) => (p.stamp_label = v), "70px"));
    tr.appendChild(mkInput(p.canonical_name, (v) => (p.canonical_name = v), "180px"));
    tr.appendChild(
      mkInput(p.keywords.join(", "), (v) => (p.keywords = splitCsv(v)), "110px")
    );
    tr.appendChild(mkInput(p.skus.join(", "), (v) => (p.skus = splitCsv(v)), "130px"));

    const tdStats = document.createElement("td");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = p.track_in_stats;
    cb.addEventListener("change", () => (p.track_in_stats = cb.checked));
    tdStats.appendChild(cb);
    tr.appendChild(tdStats);

    const tdBtns = document.createElement("td");
    tdBtns.className = "row-btns";
    const mkBtn = (label: string, title: string, fn: () => void) => {
      const b = document.createElement("button");
      b.className = "btn";
      b.textContent = label;
      b.title = title;
      b.addEventListener("click", fn);
      return b;
    };
    tdBtns.appendChild(
      mkBtn("↑", "Higher sort priority", () => {
        if (idx > 0) {
          [cfgProducts[idx - 1], cfgProducts[idx]] = [cfgProducts[idx], cfgProducts[idx - 1]];
          renderProductsTable();
        }
      })
    );
    tdBtns.appendChild(
      mkBtn("↓", "Lower sort priority", () => {
        if (idx < cfgProducts.length - 1) {
          [cfgProducts[idx + 1], cfgProducts[idx]] = [cfgProducts[idx], cfgProducts[idx + 1]];
          renderProductsTable();
        }
      })
    );
    tdBtns.appendChild(
      mkBtn("✕", "Remove product", () => {
        cfgProducts.splice(idx, 1);
        renderProductsTable();
      })
    );
    tr.appendChild(tdBtns);
    tbody.appendChild(tr);
  });
}

function fillRulesForm(rules: RulesConfig) {
  cfgProducts = rules.products.map((p) => ({ ...p, keywords: [...p.keywords], skus: [...p.skus] }));
  renderProductsTable();

  setVal("cfg-sr-x", rules.shiprocket.stamp_x);
  setVal("cfg-sr-y", rules.shiprocket.stamp_y);
  setVal("cfg-sr-size", rules.shiprocket.stamp_size);
  setVal("cfg-sr-color", rules.shiprocket.stamp_color);
  setVal("cfg-sr-crop", rules.shiprocket.crop_mm);
  setVal("cfg-sr-maxqty", rules.shiprocket.group_max_qty);
  setChecked("cfg-sr-skiplast", rules.shiprocket.crop_skip_last_page);

  setVal("cfg-st-filter", rules.st.line_filter);
  setVal("cfg-st-phone", rules.st.phone_pattern);
  setVal("cfg-st-note", rules.st.phone_note);

  setVal("cfg-dd-filter", rules.delhivery.line_filter);
  setVal("cfg-dd-skipc", rules.delhivery.skip_contains.join(", "));
  setVal("cfg-dd-skipp", rules.delhivery.skip_prefixes.join(", "));
  setVal("cfg-dd-scan", rules.delhivery.qty_scan_lines);
  setVal("cfg-dd-x", rules.delhivery.stamp_x);
  setVal("cfg-dd-bottom", rules.delhivery.stamp_from_bottom);
  setVal("cfg-dd-size", rules.delhivery.stamp_size);
  setVal("cfg-dd-color", rules.delhivery.stamp_color);
  setVal("cfg-dd-phone", rules.delhivery.phone_pattern);
  setVal("cfg-dd-note", rules.delhivery.phone_note);
  ($("cfg-dd-qty") as HTMLTextAreaElement).value = rules.delhivery.qty_patterns.join("\n");

  setVal("cfg-c-brand", rules.courier.brand_name);
  setVal("cfg-c-color", rules.courier.title_color);
  ($("cfg-c-from") as HTMLTextAreaElement).value = rules.courier.from_address;
  ($("cfg-c-from4") as HTMLTextAreaElement).value = rules.courier.from_address_4x4;
}

function collectRules(): RulesConfig {
  return {
    products: cfgProducts,
    shiprocket: {
      stamp_x: Number(val("cfg-sr-x")),
      stamp_y: Number(val("cfg-sr-y")),
      stamp_size: Number(val("cfg-sr-size")),
      stamp_color: val("cfg-sr-color"),
      crop_mm: Number(val("cfg-sr-crop")),
      crop_skip_last_page: checked("cfg-sr-skiplast"),
      group_max_qty: Math.max(1, Number(val("cfg-sr-maxqty")) || 4),
    },
    st: {
      line_filter: val("cfg-st-filter"),
      phone_pattern: val("cfg-st-phone"),
      phone_note: val("cfg-st-note"),
    },
    delhivery: {
      line_filter: val("cfg-dd-filter"),
      skip_contains: splitCsv(val("cfg-dd-skipc")),
      skip_prefixes: splitCsv(val("cfg-dd-skipp")),
      qty_patterns: ($("cfg-dd-qty") as HTMLTextAreaElement).value
        .split("\n")
        .map((s) => s.trim())
        .filter((s) => s.length > 0),
      qty_scan_lines: Math.max(1, Number(val("cfg-dd-scan")) || 5),
      stamp_x: Number(val("cfg-dd-x")),
      stamp_from_bottom: Number(val("cfg-dd-bottom")),
      stamp_size: Number(val("cfg-dd-size")),
      stamp_color: val("cfg-dd-color"),
      phone_pattern: val("cfg-dd-phone"),
      phone_note: val("cfg-dd-note"),
    },
    courier: {
      brand_name: val("cfg-c-brand"),
      title_color: val("cfg-c-color"),
      from_address: ($("cfg-c-from") as HTMLTextAreaElement).value,
      from_address_4x4: ($("cfg-c-from4") as HTMLTextAreaElement).value,
    },
  };
}

async function loadConfigIntoPanel() {
  const cfg = (await invoke("get_config")) as AppConfig;
  setVal("set-email", cfg.email);
  setVal("set-password", cfg.password);
  setVal("set-shopify-url", cfg.shopify_url);
  setVal("set-shopify-token", cfg.shopify_token);
  fillRulesForm(cfg.rules);
}

function openSettings() {
  document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
  document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
  $("settings-btn").classList.add("active");
  $("panel-config").classList.add("active");
}

$("cfg-save").addEventListener("click", async () => {
  if (!cfgProducts.length) return toast("At least one product is required.", "err");
  for (const p of cfgProducts) {
    if (!p.name.trim() || !p.stamp_label.trim()) {
      return toast("Every product needs a name and a stamp label.", "err");
    }
  }
  const cfg: AppConfig = {
    email: val("set-email").trim(),
    password: val("set-password").trim(),
    token: "",
    shopify_url: val("set-shopify-url").trim(),
    shopify_token: val("set-shopify-token").trim(),
    rules: collectRules(),
  };
  try {
    await invoke("save_config", { cfg });
    toast("Configuration saved — it applies from the next processing run.", "ok");
  } catch (err) {
    toast(String(err), "err");
  }
});

$("cfg-reload").addEventListener("click", () => {
  loadConfigIntoPanel().then(() => toast("Reloaded saved configuration.", ""));
});

$("cfg-reset").addEventListener("click", async () => {
  const rules = (await invoke("get_default_rules")) as RulesConfig;
  fillRulesForm(rules);
  toast("Rules reset to defaults — press Save Configuration to keep them.", "");
});

$("cfg-add-product").addEventListener("click", () => {
  cfgProducts.push({
    name: "New Product",
    stamp_label: "NEW",
    canonical_name: "",
    keywords: [],
    skus: [],
    track_in_stats: false,
  });
  renderProductsTable();
});

loadConfigIntoPanel().catch(() => {});

// debug hook for browser-based UI checks without the Tauri backend
(window as any).__fillRules = fillRulesForm;
