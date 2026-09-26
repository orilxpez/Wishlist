// ---------- Estado ----------
const state = {
  folders: [],
  items: [],           // todos los artículos; se filtran en cliente
  current: "all",      // "all" | "none" | id de carpeta (string)
  editingId: null,     // null = alta nueva
  open: loadOpen(),    // carpetas desplegadas en el árbol
};

const $ = (sel) => document.querySelector(sel);
const isUrl = (s) => /^https?:\/\/\S+$/i.test(s.trim());

function loadOpen() {
  try { return new Set(JSON.parse(localStorage.getItem("open") || "[]")); }
  catch { return new Set(); }
}
function saveOpen() {
  try { localStorage.setItem("open", JSON.stringify([...state.open])); } catch {}
}

// ---------- API ----------
async function api(method, path, body) {
  const res = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Error ${res.status}`);
  return data;
}

function toast(msg, isError = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.toggle("error", isError);
  t.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => (t.hidden = true), 2600);
}

// ---------- Diálogo interno (sustituye a confirm / prompt) ----------
// ask({ label, message, ok, danger })          -> Promise<boolean>
// ask({ label, message, ok, input: "valor" })  -> Promise<string | null>
function ask({ label = "", message = "", ok = "Aceptar", danger = false, input = null }) {
  const dlg = $("#ask-dialog"), field = $("#ask-input"), okBtn = $("#ask-ok");
  $("#ask-label").textContent = label;
  $("#ask-message").textContent = message;
  okBtn.textContent = ok;
  okBtn.className = "pill " + (danger ? "danger" : "light");
  field.hidden = input === null;
  field.value = input ?? "";

  return new Promise((resolve) => {
    const done = (value) => {
      $("#ask-form").onsubmit = $("#ask-cancel").onclick = dlg.oncancel = null;
      dlg.close();
      resolve(value);
    };
    $("#ask-form").onsubmit = (e) => {
      e.preventDefault();
      done(input === null ? true : field.value.trim() || null);
    };
    $("#ask-cancel").onclick = () => done(input === null ? false : null);
    dlg.oncancel = (e) => { e.preventDefault(); done(input === null ? false : null); };  // Esc
    dlg.showModal();
    if (input !== null) { field.focus(); field.select(); } else okBtn.focus();
  });
}

// ---------- Carga ----------
async function refresh() {
  const [folders, items] = await Promise.all([
    api("GET", "/api/folders"),
    api("GET", "/api/items?folder=all"),
  ]);
  Object.assign(state, { folders, items });
  if (!["all", "none"].includes(state.current) &&
      !folders.some((f) => String(f.id) === state.current)) state.current = "all";
  renderTree();
  renderItems();
}

// ---------- Utilidades ----------
function folderName(id) {
  if (id === "all") return "Todo";
  if (id === "none" || id === null || id === "") return "Sin carpeta";
  return state.folders.find((f) => String(f.id) === String(id))?.name ?? "";
}

function itemsIn(id) {
  if (id === "all") return state.items;
  if (id === "none") return state.items.filter((i) => i.folder_id == null);
  return state.items.filter((i) => String(i.folder_id) === String(id));
}

// "1.299,99 €" / "$1,299.99" / "1.299 €" / "29,99 €" -> número
function priceValue(p) {
  if (!p) return null;
  let s = p.replace(/[^\d.,]/g, "").replace(/[.,]$/, "");
  if (!s) return null;
  const comma = s.lastIndexOf(","), dot = s.lastIndexOf(".");
  if (comma >= 0 && dot >= 0) {
    // Ambos: el último es el decimal
    s = comma > dot ? s.replace(/\./g, "").replace(",", ".") : s.replace(/,/g, "");
  } else {
    // Solo uno: si va seguido de exactamente 3 cifras (o se repite) es de miles
    const sep = comma >= 0 ? "," : ".";
    const parts = s.split(sep);
    const thousands = parts.length > 2 || (parts.length === 2 && parts[1].length === 3);
    s = thousands ? parts.join("") : parts.join(".");
  }
  const n = parseFloat(s);
  return isNaN(n) ? null : n;
}

// % de bajada respecto al precio original (ref_price); 0 si no ha bajado
function discount(item) {
  const ref = priceValue(item.ref_price), cur = priceValue(item.price);
  if (!ref || cur == null || cur >= ref) return 0;
  return Math.max(1, Math.round((1 - cur / ref) * 100));
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

const CHEVRON = `<svg viewBox="0 0 16 16" width="10" height="10"><path d="M6 3.5 10.5 8 6 12.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

// ---------- Árbol lateral ----------
function renderTree() {
  const tree = $("#tree");
  tree.innerHTML = "";
  // "Todo" cuenta todos los artículos, también los que no tienen carpeta
  tree.appendChild(treeNode({ id: "all", name: "Todo", expandable: false }));
  if (state.folders.length) tree.appendChild(el("div", "tree-sep"));
  for (const f of state.folders) {
    tree.appendChild(treeNode({ id: String(f.id), name: f.name, expandable: true, editable: true }));
  }
  renderUnsorted();
}

// "Sin carpeta" no es una carpeta más: nota al pie, en mono y apagada
function renderUnsorted() {
  const btn = $("#unsorted");
  const n = itemsIn("none").length;
  btn.hidden = n === 0 && state.current !== "none";
  btn.textContent = `( Sin carpeta · ${String(n).padStart(2, "0")} )`;
  btn.classList.toggle("active", state.current === "none");
}

{
  const btn = $("#unsorted");
  btn.onclick = () => {
    state.current = "none";
    renderTree();
    renderItems();
    if (narrow.matches) setSide(false);
  };
}

function treeNode({ id, name, expandable, editable }) {
  const wrap = el("div", "node");
  const items = itemsIn(id);
  const isOpen = expandable && state.open.has(id);

  const row = el("div", "node-row" + (state.current === id ? " active" : ""));
  const chev = el("button", "chev" + (isOpen ? " open" : "") + (expandable && items.length ? "" : " hidden"));
  chev.innerHTML = CHEVRON;
  chev.title = isOpen ? "Recoger" : "Desplegar";
  chev.onclick = (e) => {
    e.stopPropagation();
    state.open.has(id) ? state.open.delete(id) : state.open.add(id);
    saveOpen();
    renderTree();
  };
  row.append(chev, el("span", "node-name", name), el("span", "node-count", String(items.length).padStart(2, "0")));

  if (editable) {
    const actions = el("span", "node-actions");
    const ren = el("button", "icon-btn", "✎"); ren.title = "Renombrar";
    const del = el("button", "icon-btn", "✕"); del.title = "Eliminar";
    ren.onclick = (e) => { e.stopPropagation(); renameFolder(id, name); };
    del.onclick = (e) => { e.stopPropagation(); deleteFolder(id, name); };
    actions.append(ren, del);
    row.appendChild(actions);
  }
  row.onclick = () => { state.current = id; renderTree(); renderItems(); };

  wrap.appendChild(row);

  if (expandable) {
    const kids = el("div", "children");
    kids.hidden = !isOpen;
    if (isOpen) for (const it of sortItems([...items])) kids.appendChild(leaf(it, id));
    wrap.appendChild(kids);
  }
  return wrap;
}

function leaf(item, folderId) {
  const row = el("div", "leaf");
  row.append(el("span", "t", item.title));
  row.title = item.title;
  row.onclick = () => {
    state.current = folderId;
    renderTree();
    renderItems();
    focusCard(item.id);
  };
  return row;
}

function focusCard(id) {
  const card = document.querySelector(`.card[data-id="${id}"]`);
  if (!card) return;
  card.scrollIntoView({ behavior: "smooth", block: "center" });
  card.classList.add("flash");
  setTimeout(() => card.classList.remove("flash"), 1400);
}

async function renameFolder(id, current) {
  const name = await ask({ label: "( Renombrar carpeta )", ok: "Guardar", input: current });
  if (!name || name === current) return;
  try { await api("PATCH", `/api/folders/${id}`, { name }); refresh(); }
  catch (err) { toast(err.message, true); }
}

async function deleteFolder(id, name) {
  const n = itemsIn(id).length;
  const ok = await ask({
    label: "( Eliminar carpeta )",
    message: n
      ? `«${name}» se eliminará. ${n === 1 ? "Su artículo pasará" : `Sus ${n} artículos pasarán`} a Sin carpeta.`
      : `«${name}» se eliminará.`,
    ok: "Eliminar",
    danger: true,
  });
  if (!ok) return;
  await api("DELETE", `/api/folders/${id}`);
  state.open.delete(id); saveOpen();
  refresh();
}

$("#new-folder-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = $("#new-folder-name");
  try {
    await api("POST", "/api/folders", { name: input.value });
    input.value = "";
    refresh();
  } catch (err) { toast(err.message, true); }
});

// ---------- Grid ----------
function sortItems(list) {
  const byPrice = (dir) => (a, b) => {
    const pa = priceValue(a.price), pb = priceValue(b.price);
    if (pa === null) return 1;
    if (pb === null) return -1;
    return dir * (pa - pb);
  };
  const sorters = {
    "date-desc": (a, b) => b.created_at.localeCompare(a.created_at),
    "date-asc": (a, b) => a.created_at.localeCompare(b.created_at),
    "price-asc": byPrice(1),
    "price-desc": byPrice(-1),
    title: (a, b) => a.title.localeCompare(b.title, "es"),
    // Mayor rebaja primero; lo que no está rebajado, después por fecha
    discount: (a, b) => discount(b) - discount(a) || b.created_at.localeCompare(a.created_at),
  };
  return list.sort(sorters[$("#sort").value]);
}

function visibleItems() {
  const q = $("#omni").value.trim().toLowerCase();
  const searching = q && !isUrl(q);
  const list = itemsIn(state.current).filter((i) =>
    !searching || i.title.toLowerCase().includes(q) || (i.notes || "").toLowerCase().includes(q)
  );
  return sortItems([...list]);
}

function folderSelect(selectedId) {
  const s = el("select");
  s.appendChild(new Option("Sin carpeta", ""));
  for (const f of state.folders) s.appendChild(new Option(f.name, f.id, false, f.id === selectedId));
  return s;
}

function renderItems() {
  const list = visibleItems();
  const all = itemsIn(state.current);
  $("#view-title").textContent = folderName(state.current);
  $("#view-count").textContent = `(${String(all.length).padStart(2, "0")})`;

  const grid = $("#grid");
  grid.innerHTML = "";
  $("#empty").hidden = list.length > 0;

  for (const item of list) {
    const card = el("article", "card");
    card.dataset.id = item.id;

    // Imagen + acciones al pasar el ratón
    const thumb = el("div", "thumb");
    if (item.image) {
      const img = el("img");
      img.referrerPolicy = "no-referrer";
      img.loading = "lazy";
      img.decoding = "async";
      img.draggable = false;  // sin "fantasma" al mantener pulsada la imagen
      img.onload = () => fitImage(img, thumb);
      img.onerror = () => img.replaceWith(el("div", "noimg label", "Sin imagen"));
      img.src = item.image;
      thumb.appendChild(img);
    } else thumb.appendChild(el("div", "noimg label", "Sin imagen"));
    thumb.onclick = () => openExternal(item.url);

    const overlay = el("div", "overlay");
    overlay.onclick = (e) => e.stopPropagation();
    const move = folderSelect(item.folder_id);
    move.title = "Mover a carpeta";
    move.onchange = () => moveItem(item.id, move.value ? Number(move.value) : null);
    const edit = el("button", "edit", "Editar");
    edit.onclick = () => openDialog(item);
    const del = el("button", "del", "✕");
    del.title = "Eliminar";
    del.onclick = async () => {
      const ok = await ask({
        label: "( Eliminar )",
        message: `«${item.title}» se eliminará de la wishlist.`,
        ok: "Eliminar",
        danger: true,
      });
      if (!ok) return;
      await api("DELETE", `/api/items/${item.id}`);
      refresh();
    };
    overlay.append(move, edit, del);
    thumb.appendChild(overlay);

    // Texto
    const info = el("div", "info");
    const title = el("a", "title", item.title);
    title.href = "#";
    title.title = item.url;
    title.onclick = (e) => { e.preventDefault(); openExternal(item.url); };
    const meta = el("div", "meta label");
    const price = el("span", "price", item.price || "—");
    const off = discount(item);
    if (off) {
      // Dos versiones: "(↓44%)" normal y solo "↓" en tamaño S, donde no cabe
      const tag = el("span", "sale");
      tag.append(el("span", "sale-full", `(↓${off}%)`), el("span", "sale-short", "↓"));
      tag.title = `Antes ${item.ref_price} (−${off}%)`;
      price.append(" ", tag);
    }
    meta.append(
      price,
      el("span", "", new Date(item.created_at).toLocaleDateString("es-ES", { day: "2-digit", month: "2-digit", year: "2-digit" }))
    );
    info.append(title, meta, el("p", "notes", item.notes || ""));

    card.append(thumb, info);
    grid.appendChild(card);
  }
}

// Decide cómo encajar la foto en el marco 4:5, mirando los CUATRO lados del borde:
//  - Los 4 lados claros -> el objeto está rodeado de fondo (producto recortado,
//    portada de libro…) -> "contain": entero, sobre el color de ese fondo.
//  - Algún lado no es claro -> fotografía (modelo, suelo, sombra o el propio
//    sujeto tocan el borde) -> "cover": llena la tarjeta.
// Calibrado con imágenes reales (lado más oscuro, % de píxeles claros):
// pendientes 100 %, libro 100 % | vaqueros con modelo 0 % (suelo), oreja 0 %.
const fitCache = new Map();
const probe = document.createElement("canvas").getContext("2d", { willReadFrequently: true });

function fitImage(img, thumb) {
  let fit = fitCache.get(img.src);
  if (!fit) {
    fit = { contain: true, bg: null };  // por defecto: foto entera, fondo claro
    try {
      const S = 48;
      probe.canvas.width = probe.canvas.height = S;
      probe.drawImage(img, 0, 0, S, S);
      const px = probe.getImageData(0, 0, S, S).data;
      const at = (x, y) => { const i = (y * S + x) * 4; return [px[i], px[i + 1], px[i + 2]]; };
      const isLight = (p) => (p[0] + p[1] + p[2]) / 3 > 215 && Math.max(...p) - Math.min(...p) < 30;

      // Los cuatro lados del borde por separado
      const sides = [[], [], [], []];
      for (let i = 0; i < S; i++) {
        sides[0].push(at(i, 0));      // arriba
        sides[1].push(at(i, S - 1));  // abajo
        sides[2].push(at(0, i));      // izquierda
        sides[3].push(at(S - 1, i));  // derecha
      }
      const lightShare = (side) => side.filter(isLight).length / side.length;
      const surrounded = sides.every((side) => lightShare(side) >= 0.6);

      const light = sides.flat().filter(isLight);
      const avgOf = (list) => [0, 1, 2].map((c) => Math.round(list.reduce((s, p) => s + p[c], 0) / list.length));
      fit = surrounded
        ? { contain: true, bg: `rgb(${avgOf(light).join(",")})` }
        : { contain: false, bg: null };
    } catch {
      // Imagen remota sin permiso de lectura (aún no cacheada): valor por defecto
    }
    fitCache.set(img.src, fit);
  }
  thumb.classList.toggle("contain", fit.contain);
  if (fit.bg) thumb.style.background = fit.bg;
  img.classList.add("ready");
}

async function moveItem(id, folderId) {
  await api("PATCH", `/api/items/${id}`, { folder_id: folderId });
  toast(`Movido a ${folderName(folderId)}`);
  refresh();
}

// Abre en el navegador del sistema, no dentro de la app
function openExternal(url) {
  if (window.pywebview?.api) window.pywebview.api.open_url(url);
  else window.open(url, "_blank");
}

// El orden elegido se recuerda entre sesiones
function setSort(value) {
  $("#sort").value = value;
  try { localStorage.setItem("sort", value); } catch {}
  renderItems();
  renderTree();
}
$("#sort").addEventListener("change", () => setSort($("#sort").value));
try {
  const s = localStorage.getItem("sort");
  if (s && [...$("#sort").options].some((o) => o.value === s)) $("#sort").value = s;
} catch {}

// ---------- Tamaño de tarjetas (S / M / L) ----------
function setSize(size) {
  document.documentElement.dataset.size = size;
  document.querySelectorAll("#size-toggle button").forEach((b) => {
    b.classList.toggle("on", b.dataset.size === size);
    b.setAttribute("aria-checked", b.dataset.size === size);
  });
  try { localStorage.setItem("size", size); } catch {}
}
document.querySelectorAll("#size-toggle button").forEach((b) => {
  b.setAttribute("role", "radio");
  b.onclick = () => setSize(b.dataset.size);
});
setSize((() => { try { return localStorage.getItem("size") || "m"; } catch { return "m"; } })());

// ---------- Barra lateral como panel en ventanas estrechas ----------
const narrow = window.matchMedia("(max-width: 960px)");
const setSide = (open) => document.body.classList.toggle("side-open", open);
$("#menu-btn").onclick = () => setSide(!document.body.classList.contains("side-open"));
$("#scrim").onclick = () => setSide(false);
$("#close-side").onclick = () => setSide(false);
narrow.addEventListener("change", () => setSide(false));
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && document.body.classList.contains("side-open")) setSide(false);
});
// Al elegir carpeta o artículo en el panel, se cierra solo
$("#tree").addEventListener("click", (e) => {
  if (narrow.matches && e.target.closest(".node-row, .leaf") && !e.target.closest(".chev, .icon-btn")) {
    setSide(false);
  }
});

// ---------- Campo único: URL = añadir, texto = buscar ----------
const omni = $("#omni");
omni.addEventListener("input", () => {
  $("#omni-btn").hidden = !isUrl(omni.value);
  renderItems();
});

$("#omni-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const url = omni.value.trim();
  if (!isUrl(url)) return;
  const btn = $("#omni-btn");
  btn.disabled = true;
  btn.textContent = "Leyendo…";
  // Algunas tiendas (COS…) hacen esperar la primera vez mientras verifican
  const slow = setTimeout(() => { btn.textContent = "La tienda tarda…"; }, 6000);
  let data = { url };
  try {
    data = { ...data, ...(await api("POST", "/api/preview", { url })) };
    if (!data.price) data.status = "No se encontró el precio; puedes añadirlo a mano.";
  } catch (err) {
    data.status = err.message;
  } finally {
    clearTimeout(slow);
    btn.disabled = false;
    btn.textContent = "Añadir";
  }
  openDialog(null, data);
  omni.value = "";
  btn.hidden = true;
  renderItems();
});

// Pegar una URL fuera de un campo la mete en el buscador
document.addEventListener("paste", (e) => {
  if (e.target.matches("input, textarea")) return;
  const text = e.clipboardData.getData("text").trim();
  if (isUrl(text)) {
    omni.value = text;
    omni.focus();
    $("#omni-btn").hidden = false;
  }
});

// ---------- Diálogo alta / edición ----------
const dialog = $("#item-dialog");

function setPreview(src) {
  const img = $("#f-preview");
  img.style.visibility = src ? "visible" : "hidden";
  if (src) img.src = src;
}

// Marca de rebaja junto a "Precio" en el diálogo, según lo que haya escrito
function updateDialogSale() {
  const off = discount({ price: $("#f-price").value, ref_price: state.dialogRef });
  $("#f-sale").textContent = off ? `(↓${off}%)` : "";
  $("#f-sale").title = off ? `Antes ${state.dialogRef}` : "";
}

function openDialog(item = null, prefill = {}) {
  state.editingId = item?.id ?? null;
  // Precio original: el guardado al editar, o el tachado de la tienda al añadir
  state.dialogRef = item ? item.ref_price : prefill.ref_price || null;
  const data = item || prefill;
  $("#dialog-title").textContent = item ? "( Editar )" : "( Nuevo )";
  $("#scrape-status").textContent = prefill.status || "";
  $("#f-title").value = data.title || "";
  $("#f-price").value = data.price || "";
  $("#f-image").value = data.image || "";
  $("#f-notes").value = data.notes || "";
  $("#f-url").value = data.url || "";
  const defaultFolder = item ? item.folder_id
    : (/^\d+$/.test(state.current) ? Number(state.current) : null);
  const sel = folderSelect(defaultFolder);
  sel.id = "f-folder";
  $("#f-folder").replaceWith(sel);
  setPreview(data.image);
  state.dialogPrice = data.price || "";
  updateDialogSale();
  dialog.showModal();
}

$("#f-image").addEventListener("input", (e) => setPreview(e.target.value));
$("#f-price").addEventListener("input", () => {
  // Al añadir, la marca sigue al precio escrito. Al editar, cambiar el precio a mano
  // lo convierte en el nuevo precio original, así que la marca desaparece.
  if (!state.editingId) updateDialogSale();
  else if ($("#f-price").value !== state.dialogPrice) $("#f-sale").textContent = "";
  else updateDialogSale();
});
$("#cancel-btn").onclick = () => dialog.close();

$("#item-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    title: $("#f-title").value.trim(),
    price: $("#f-price").value.trim(),
    image: $("#f-image").value.trim(),
    notes: $("#f-notes").value.trim(),
    url: $("#f-url").value.trim(),
    folder_id: $("#f-folder").value ? Number($("#f-folder").value) : null,
  };
  if (!state.editingId && state.dialogRef) body.ref_price = state.dialogRef;
  try {
    if (state.editingId) await api("PATCH", `/api/items/${state.editingId}`, body);
    else await api("POST", "/api/items", body);
    dialog.close();
    toast(state.editingId ? "Guardado" : "Añadido");
    refresh();
  } catch (err) { toast(err.message, true); }
});

refresh();

// Mientras se comprueban precios en segundo plano, refresca si alguno cambia
async function watchPriceCheck() {
  let seen = 0;
  for (;;) {
    await new Promise((r) => setTimeout(r, 4000));
    let st;
    try { st = await api("GET", "/api/check-status"); } catch { return; }
    if (st.updated > seen) { seen = st.updated; refresh(); }
    if (!st.running) return;
  }
}
watchPriceCheck();
