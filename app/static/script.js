const API_BASE = "/goszakupki";
//const API_BASE = "";

let SYSTEM_TOKEN = null;

let rawPurchases = [];
let filteredPurchases = [];
let viewMode = "table";
let page = 1;

// email subscription

let emailModal, emailInput, codeInput, codeField, emailStatus;
let btnSendCode, btnVerifyCode;
let emailMode = "subscribe";
let sendCodeTimer = null;
let sendCodeSeconds = 60;

const SOON_HOURS = 48;

function $(id){ return document.getElementById(id); }

async function copyText(text){
  const value = String(text || "").trim();
  if (!value) throw new Error("Нет значения для копирования");

  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(value);
    return;
  }

  const ta = document.createElement("textarea");
  ta.value = value;
  ta.style.position = "fixed";
  ta.style.left = "-9999px";
  ta.style.top = "0";
  document.body.appendChild(ta);
  ta.focus();
  ta.select();

  const ok = document.execCommand("copy");
  document.body.removeChild(ta);

  if (!ok) {
    throw new Error("Браузер не смог скопировать текст");
  }
}

function startSendCodeTimer(button, mode) {
  let remaining = sendCodeSeconds;

  button.disabled = true;
  button.textContent = `Отправить через ${remaining} сек`;

  sendCodeTimer = setInterval(() => {
    remaining--;

    if (remaining <= 0) {
      clearInterval(sendCodeTimer);
      sendCodeTimer = null;
      button.disabled = false;

      button.textContent =
        mode === "subscribe" ? "Получить код" : "Получить код для отписки";
      return;
    }

    button.textContent = `Отправить через ${remaining} сек`;
  }, 1000);
}

function setStatus(text, type="info"){
  const el = $("statusBox");
  if (!el) return;
  el.textContent = text;
  el.style.color =
    (type === "error")
      ? "var(--danger)"
      : (type === "ok" ? "var(--ok)" : "var(--muted)");
}

function lockBodyScroll(){
  document.body.style.overflow = "hidden";
  document.body.style.touchAction = "none";
}

function unlockBodyScroll(){
  document.body.style.overflow = "";
  document.body.style.touchAction = "";
}

function fmtMoney(v){
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString("ru-RU") + " ₽";
}

function fmtDateOnly(iso){
  if (!iso) return "—";
  try{
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso).slice(0,10);
    return d.toLocaleDateString("ru-RU");
  }catch{
    return String(iso).slice(0,10);
  }
}

function val(id){
  const v = $(id)?.value;
  return v && String(v).trim().length ? String(v).trim() : null;
}

function num(id){
  const v = $(id)?.value;
  if (v === "" || v === null || v === undefined) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function dateToIsoRangeStart(id){
  const v = $(id)?.value;
  if (!v) return null;
  return new Date(v + "T00:00:00").toISOString();
}

function dateToIsoRangeEnd(id){
  const v = $(id)?.value;
  if (!v) return null;
  return new Date(v + "T23:59:59.999").toISOString();
}

function getDeadlineStatus(p){
  const dl = p.submission_close_datetime;
  if (!dl) return {key:"active", label:"Без дедлайна", cls:"badge--ok"};

  const d = new Date(dl);
  if (Number.isNaN(d.getTime())) return {key:"active", label:"Дедлайн", cls:"badge--ok"};

  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const deadline = new Date(d.getFullYear(), d.getMonth(), d.getDate() + 1);

  if (deadline <= today) return {key:"expired", label:"Просрочена", cls:"badge--danger"};

  const diffHours = (deadline - now) / 1000 / 60 / 60;
  if (diffHours <= SOON_HOURS) {
    return {key:"soon", label:`Скоро (${Math.ceil(diffHours)}ч)`, cls:"badge--warn"};
  }

  return {key:"active", label:"Активна", cls:"badge--ok"};
}

function normalizeText(s){
  return (s ?? "").toString().toLowerCase();
}

function purchaseSearchBlob(p){
  const c = p.customer || {};
  return [
    p.name,
    p.registration_number,
    p.guid,
    c.full_name,
    c.inn,
  ].map(normalizeText).join(" | ");
}

function applyClientFilters(){
  const q = normalizeText(val("q"));
  const statusFilter = val("statusFilter") || "all";

  filteredPurchases = rawPurchases.filter(p => {
    const st = getDeadlineStatus(p).key;
    if (statusFilter !== "all" && st !== statusFilter) return false;

    if (q){
      const blob = purchaseSearchBlob(p);
      if (!blob.includes(q)) return false;
    }
    return true;
  });
}

function applySort(){
  const sortType = val("sort") || "submission_start_desc";

  const safeDate = (x) => {
    const d = new Date(x || 0);
    return Number.isNaN(d.getTime()) ? 0 : d.getTime();
  };

  filteredPurchases.sort((a,b) => {
    if (sortType === "sum_desc") return (Number(b.initial_sum)||0) - (Number(a.initial_sum)||0);
    if (sortType === "sum_asc") return (Number(a.initial_sum)||0) - (Number(b.initial_sum)||0);
    if (sortType === "name_asc") return String(a.name||"").localeCompare(String(b.name||""), "ru");

    if (sortType === "submission_start_asc") return safeDate(a.submission_start_datetime) - safeDate(b.submission_start_datetime);
    if (sortType === "submission_start_desc") return safeDate(b.submission_start_datetime) - safeDate(a.submission_start_datetime);

    if (sortType === "submission_close_asc") return safeDate(a.submission_close_datetime) - safeDate(b.submission_close_datetime);
    if (sortType === "submission_close_desc") return safeDate(b.submission_close_datetime) - safeDate(a.submission_close_datetime);

    if (sortType === "pub_asc") return safeDate(a.publication_datetime) - safeDate(b.publication_datetime);
    if (sortType === "pub_desc") return safeDate(b.publication_datetime) - safeDate(a.publication_datetime);

    return 0;
  });
}

function paginate(list){
  const size = Number(val("pageSize")) || 20;
  const total = list.length;
  const pages = Math.max(1, Math.ceil(total / size));
  page = Math.min(Math.max(1, page), pages);

  const start = (page - 1) * size;
  const end = start + size;
  return {items: list.slice(start, end), total, pages, size};
}

function renderPagination(pages){
  const wrap = $("pagination");
  if (!wrap) return;
  wrap.innerHTML = "";

  const makeBtn = (label, p, active=false) => {
    const b = document.createElement("button");
    b.className = "pageBtn" + (active ? " pageBtn--active" : "");
    b.textContent = label;
    b.onclick = () => { page = p; render(); };
    return b;
  };

  if (pages <= 1) return;

  wrap.appendChild(makeBtn("←", Math.max(1, page-1)));

  const windowSize = 5;
  const start = Math.max(1, page - Math.floor(windowSize/2));
  const end = Math.min(pages, start + windowSize - 1);

  for (let i=start; i<=end; i++){
    wrap.appendChild(makeBtn(String(i), i, i === page));
  }

  wrap.appendChild(makeBtn("→", Math.min(pages, page+1)));
}

function updateKPIs(shownItems){
  $("kpiFound").textContent = String(rawPurchases.length);
  $("kpiShown").textContent = String(shownItems.length);

  const sum = shownItems.reduce((acc, p) => acc + (Number(p.initial_sum) || 0), 0);
  $("kpiSum").textContent = fmtMoney(sum).replace(" ₽", "");
}

function openModal(p){
  $("modalTitle").textContent = p.name || "Детали";
  const c = p.customer || {};
  const contact = p.contact || {};
  const st = getDeadlineStatus(p);

  $("modalContent").innerHTML = `
      <div class="kv"><div class="kv__k">Статус</div><div class="kv__v">${st.label}</div></div>
      <div class="kv"><div class="kv__k">GUID</div><div class="kv__v"><span class="cellMono">${p.guid || "—"}</span></div></div>
      <div class="kv"><div class="kv__k">Рег. номер</div><div class="kv__v"><span class="cellMono">${p.registration_number || "—"}</span></div></div>
      <div class="kv"><div class="kv__k">Сумма</div><div class="kv__v">${fmtMoney(p.initial_sum)}</div></div>
      <div class="kv"><div class="kv__k">Начало подачи заявки</div><div class="kv__v">${fmtDateOnly(p.submission_start_datetime)}</div></div>
      <div class="kv"><div class="kv__k">Окончание подачи заявки</div><div class="kv__v">${fmtDateOnly(p.submission_close_datetime)}</div></div>
      <div class="kv"><div class="kv__k">Дата публикации</div><div class="kv__v">${fmtDateOnly(p.publication_datetime)}</div></div>
      <div class="kv"><div class="kv__k">Заказчик</div><div class="kv__v">${c.full_name || "—"}</div></div>
      <div class="kv"><div class="kv__k">ИНН / КПП</div><div class="kv__v">${c.inn || "—"} / ${c.kpp || "—"}</div></div>

      <div class="kv"><div class="kv__k">Контакт</div><div class="kv__v">${[contact.last_name, contact.first_name, contact.middle_name].filter(Boolean).join(" ") || "—"}</div></div>
      <div class="kv"><div class="kv__k">Телефон</div><div class="kv__v">${contact.phone || "—"}</div></div>
      <div class="kv"><div class="kv__k">Email</div><div class="kv__v">${contact.email || "—"}</div></div>

      <div class="kv"><div class="kv__k">Лоты</div><div class="kv__v">${Array.isArray(p.lots) ? p.lots.length : "—"}</div></div>
  `;

  $("btnCopyGuid").onclick = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      await copyText(p.guid);
      setStatus("GUID скопирован", "ok");
    } catch (err) {
      console.error(err);
      setStatus("Не удалось скопировать GUID", "error");
    }
  };

  $("btnCopyReg").onclick = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      await copyText(p.registration_number);
      setStatus("Рег. номер скопирован", "ok");
    } catch (err) {
      console.error(err);
      setStatus("Не удалось скопировать рег. номер", "error");
    }
  };

  $("modal").classList.remove("hidden");
  lockBodyScroll();
}

function closeModal(){
  $("modal").classList.add("hidden");
  unlockBodyScroll();
}

function renderTable(items){
  const body = $("tableBody");
  body.innerHTML = "";

  items.forEach(p => {
    const c = p.customer || {};
    const st = getDeadlineStatus(p);

    const row = document.createElement("div");
    row.className = "rowItem";
    row.onclick = () => openModal(p);
    row.innerHTML = `
      <div>
        <span class="badge ${st.cls}">
          <span class="badge__dot"></span>
          ${st.label}
        </span>
      </div>

      <div>
        <div class="cellTitle">${fmtMoney(p.initial_sum)}</div>
        <div class="cellSmall">GUID: <span class="cellMono">${(p.guid || "—").slice(0,8)}…</span></div>
      </div>

      <div>
        <div class="cellTitle">${fmtDateOnly(p.submission_start_datetime)}</div>
        <div class="cellSmall">начало подачи</div>
      </div>

      <div>
        <div class="cellTitle">${fmtDateOnly(p.submission_close_datetime)}</div>
        <div class="cellSmall">окончание подачи</div>
      </div>

      <div>
        <div class="cellTitle cellMono">${p.registration_number || "—"}</div>
      </div>

      <div>
        <div class="cellTitle">${p.name || "—"}</div>
      </div>

      <div>
        <div class="cellTitle">${c.full_name || "—"}</div>
        <div class="cellSmall">ИНН: <span class="cellMono">${c.inn || "—"}</span></div>
      </div>

      <div style="display:flex;justify-content:flex-end;align-items:center">
        <button class="pageBtn" onclick="event.stopPropagation(); openModal(window.__pmap['${p.guid}'])">Открыть</button>
      </div>
    `;

    body.appendChild(row);
  });
}

function renderCards(items){
  const wrap = $("cards");
  wrap.innerHTML = "";

  items.forEach(p => {
    const c = p.customer || {};
    const st = getDeadlineStatus(p);

    const card = document.createElement("div");
    card.className = "card";
    card.onclick = () => openModal(p);

    card.innerHTML = `
      <div class="row card__top">
        <div class="card__title">${p.name || "—"}</div>
        <span class="badge ${st.cls}">
          <span class="badge__dot"></span>
          ${st.label}
        </span>
      </div>

      <div class="card__sum">${fmtMoney(p.initial_sum)}</div>

      <div class="card__grid">
        <div class="card__meta card__meta--full">
          <b>Рег.№:</b> <span class="cellMono">${p.registration_number || "—"}</span>
        </div>

        <div class="card__meta">
          <b>Начало подачи заявки:</b>
          <span>${fmtDateOnly(p.submission_start_datetime)}</span>
        </div>

        <div class="card__meta">
          <b>Окончание подачи заявки:</b>
          <span>${fmtDateOnly(p.submission_close_datetime)}</span>
        </div>

        <div class="card__meta card__meta--full">
          <b>Заказчик:</b> ${c.full_name || "—"}
        </div>
      </div>
    `;

    wrap.appendChild(card);
  });
}

function render(){
  applyClientFilters();
  applySort();

  window.__pmap = Object.fromEntries(
    filteredPurchases.filter(p => p.guid).map(p => [p.guid, p])
  );

  const {items, total, pages, size} = paginate(filteredPurchases);

  $("resultInfo").textContent = `Показано ${items.length} из ${total} • Страница ${page}/${pages} • Размер ${size}`;
  renderPagination(pages);
  updateKPIs(items);

  if (viewMode === "table"){
    $("tableWrap").classList.remove("hidden");
    $("cardsWrap").classList.add("hidden");
    renderTable(items);
  }else{
    $("cardsWrap").classList.remove("hidden");
    $("tableWrap").classList.add("hidden");
    renderCards(items);
  }
}

function saveStateToUrl(){
  const params = new URLSearchParams();

  [
    "initial_sum_from","initial_sum_to",
    "publication_datetime_from","publication_datetime_to",
    "submission_start_datetime_from","submission_start_datetime_to",
    "submission_close_datetime_from","submission_close_datetime_to"
  ].forEach(id => {
    const el = $(id);
    if (!el) return;
    if (el.value) params.set(id, el.value);
  });

  if (val("q")) params.set("q", val("q"));
  params.set("sort", val("sort") || "submission_start_desc");
  params.set("pageSize", val("pageSize") || "20");
  params.set("statusFilter", val("statusFilter") || "all");
  params.set("view", viewMode);

  history.replaceState(null, "", "?" + params.toString());
}

function loadStateFromUrl(){
  const params = new URLSearchParams(location.search);

  const setIf = (id) => {
    const v = params.get(id);
    if (v !== null && $(id)) $(id).value = v;
  };

  [
    "initial_sum_from","initial_sum_to",
    "publication_datetime_from","publication_datetime_to",
    "submission_start_datetime_from","submission_start_datetime_to",
    "submission_close_datetime_from","submission_close_datetime_to",
    "q","sort","pageSize","statusFilter"
  ].forEach(setIf);

  const v = params.get("view");
  if (v === "cards") setView("cards");
  else setView("table");
}

function setView(mode){
  viewMode = mode;
  const t = $("viewTable");
  const c = $("viewCards");

  if (mode === "cards"){
    c.classList.add("segmented__btn--active");
    t.classList.remove("segmented__btn--active");
  }else{
    t.classList.add("segmented__btn--active");
    c.classList.remove("segmented__btn--active");
  }

  render();
  saveStateToUrl();
}

async function fetchToken(){
  try{
    setStatus("Получаю токен…");
    const res = await fetch(`${API_BASE}/config`);
    const data = await res.json();
    SYSTEM_TOKEN = data.system_token;
    setStatus("Токен получен", "ok");
  }catch(e){
    console.error(e);
    setStatus("Не удалось получить токен (/config)", "error");
  }
}

async function fetchAllPurchasesForExport(){
  if (!SYSTEM_TOKEN){
    throw new Error("Нет SYSTEM_TOKEN");
  }

  const res = await fetch(`${API_BASE}/get_all_purchases`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token: SYSTEM_TOKEN })
  });

  let json = {};
  try {
    json = await res.json();
  } catch {
    throw new Error("Сервер вернул некорректный JSON");
  }

  if (!res.ok) {
    throw new Error(json.detail || json.message || "Ошибка загрузки всех закупок");
  }

  return Array.isArray(json.data) ? json.data : [];
}

function safeExportValue(v){
  return v ?? "";
}

function formatExportDate(value){
  if (!value) return "";

  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "";

  return d;
}

function buildExportRows(purchases){
  const rows = [];
  let lotSequence = 1;

  for (const p of purchases) {
    const resultInfo = p?.result_info || {};
    const lots = Array.isArray(p?.lots) && p.lots.length ? p.lots : [{}];

    for (const lot of lots) {
      rows.push({
        "Реестровый номер закупки": safeExportValue(p?.registration_number),
        "Порядковый номер лота": lotSequence++,
        "Наименование лота": safeExportValue(lot?.subject || p?.name),
        "Начальная (максимальная) цена контракта": Number(p?.initial_sum) || 0,
        "Валюта": safeExportValue(lot?.currency || p?.currency || "RUB"),
        "Наименование Заказчика": safeExportValue(p?.customer?.full_name),
        "Организация, осуществляющая размещение ": safeExportValue(
          p?.customer?.placement_organization || p?.customer?.full_name
        ),
        "Дата размещения": formatExportDate(p?.submission_start_datetime),
        "Дата обновления": formatExportDate(p?.publication_datetime),
        "Дата начала подачи заявок": formatExportDate(p?.submission_start_datetime),
        "Дата окончания подачи заявок": formatExportDate(p?.submission_close_datetime),
        "Победитель ": safeExportValue(resultInfo?.["Победитель"]),
        "Другие\nучастники": safeExportValue(resultInfo?.["Другие участники"]),
        "Ячейки": safeExportValue(resultInfo?.["Ячейки"]),
        "Кол-во ячеек": safeExportValue(resultInfo?.["Кол-во ячеек"]),
        "Типовой проект": safeExportValue(resultInfo?.["Типовой проект"]),
        "Проектировщик": safeExportValue(resultInfo?.["Проектировщик"]),
        "Дата исполнения договора": safeExportValue(resultInfo?.["Дата исполнения договора"]),
        "Филиал/РЭС": safeExportValue(resultInfo?.["Филиал/РЭС"]),
      });
    }
  }

  return rows;
}

async function apiSearch(){
  if (!SYSTEM_TOKEN){
    setStatus("Нет SYSTEM_TOKEN", "error");
    return;
  }

  const body = {
    token: SYSTEM_TOKEN,
    initial_sum_from: num("initial_sum_from"),
    initial_sum_to: num("initial_sum_to"),

    publication_datetime_from: dateToIsoRangeStart("publication_datetime_from"),
    publication_datetime_to: dateToIsoRangeEnd("publication_datetime_to"),

    submission_start_datetime_from: dateToIsoRangeStart("submission_start_datetime_from"),
    submission_start_datetime_to: dateToIsoRangeEnd("submission_start_datetime_to"),

    submission_close_datetime_from: dateToIsoRangeStart("submission_close_datetime_from"),
    submission_close_datetime_to: dateToIsoRangeEnd("submission_close_datetime_to"),
  };

  try{
    setStatus("Загружаю данные…");
    const res = await fetch(`${API_BASE}/get_all_purchases`, {
      method:"POST",
      headers:{ "Content-Type":"application/json" },
      body: JSON.stringify(body)
    });
    const json = await res.json();
    rawPurchases = json.data || [];
    page = 1;
    setStatus(`Готово: получено ${rawPurchases.length}`, "ok");
    render();
    saveStateToUrl();
  }catch(e){
    console.error(e);
    setStatus("Ошибка запроса /get_all_purchases", "error");
  }
}

async function adminPost(url, payload = null){
  if (!SYSTEM_TOKEN){
    setStatus("Нет SYSTEM_TOKEN", "error");
    return;
  }
  try{
    setStatus(`Выполняю ${url}…`);
    const res = await fetch(url, {
      method:"POST",
      headers:{ "Content-Type":"application/json" },
      body: JSON.stringify(payload || {token: SYSTEM_TOKEN})
    });
    if (!res.ok){
      const t = await res.text();
      throw new Error(`HTTP ${res.status}: ${t}`);
    }
    const json = await res.json();
    const info = json.data ? JSON.stringify(json.data) : (json.message || "Готово");
    setStatus(`${json.message || "OK"} | ${info}`.slice(0, 180), "ok");
    await apiSearch();
  }catch(e){
    console.error(e);
    setStatus(`Ошибка ${url}: ${e.message}`, "error");
  }
}

async function exportJson(){
  try {
    const allPurchases = await fetchAllPurchasesForExport();
    const rows = buildExportRows(allPurchases).map((row) => {
      const normalized = { ...row };

      [
        "Дата размещения",
        "Дата обновления",
        "Дата начала подачи заявок",
        "Дата окончания подачи заявок"
      ].forEach((key) => {
        if (normalized[key] instanceof Date) {
          normalized[key] = normalized[key].toISOString();
        }
      });

      return normalized;
    });

    const blob = new Blob(
      [JSON.stringify(rows, null, 2)],
      { type:"application/json;charset=utf-8" }
    );

    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "purchases.json";
    a.click();
    URL.revokeObjectURL(a.href);
  } catch (err) {
    console.error("Ошибка экспорта JSON:", err);
    alert("Не удалось выгрузить JSON");
  }
}

async function exportXlsx() {
  try {
    const allPurchases = await fetchAllPurchasesForExport();
    const rows = buildExportRows(allPurchases);

    const workbook = new ExcelJS.Workbook();
    const worksheet = workbook.addWorksheet("Purchases");

    const columns = [
      { header: "Реестровый номер закупки", key: "Реестровый номер закупки", width: 16 },
      { header: "Порядковый номер лота", key: "Порядковый номер лота", width: 9 },
      { header: "Наименование лота", key: "Наименование лота", width: 55 },
      { header: "Начальная (максимальная) цена контракта", key: "Начальная (максимальная) цена контракта", width: 16 },
      { header: "Валюта", key: "Валюта", width: 9 },
      { header: "Наименование Заказчика", key: "Наименование Заказчика", width: 28 },
      { header: "Организация, осуществляющая размещение ", key: "Организация, осуществляющая размещение ", width: 21 },
      { header: "Дата размещения", key: "Дата размещения", width: 13 },
      { header: "Дата обновления", key: "Дата обновления", width: 13 },
      { header: "Дата начала подачи заявок", key: "Дата начала подачи заявок", width: 11 },
      { header: "Дата окончания подачи заявок", key: "Дата окончания подачи заявок", width: 13 },
      { header: "Победитель ", key: "Победитель ", width: 14 },
      { header: "Другие\nучастники", key: "Другие\nучастники", width: 15 },
      { header: "Ячейки", key: "Ячейки", width: 9 },
      { header: "Кол-во ячеек", key: "Кол-во ячеек", width: 13 },
      { header: "Типовой проект", key: "Типовой проект", width: 15 },
      { header: "Проектировщик", key: "Проектировщик", width: 29 },
      { header: "Дата исполнения договора", key: "Дата исполнения договора", width: 13 },
      { header: "Филиал/РЭС", key: "Филиал/РЭС", width: 14 },
    ];

    worksheet.columns = columns;
    worksheet.addRows(rows);

    const thinBorder = {
      top: { style: "thin" },
      left: { style: "thin" },
      bottom: { style: "thin" },
      right: { style: "thin" }
    };

    const yellowHeaderCols = new Set([
      "Победитель ",
      "Другие\nучастники",
      "Ячейки",
      "Кол-во ячеек",
      "Типовой проект",
      "Проектировщик",
      "Дата исполнения договора",
      "Филиал/РЭС"
    ]);

    worksheet.getRow(1).height = 67.5;

    worksheet.getRow(1).eachCell((cell) => {
      cell.font = {
        name: "Calibri",
        size: 11,
        bold: true
      };

      cell.alignment = {
        horizontal: "center",
        vertical: "middle",
        wrapText: true
      };

      cell.border = thinBorder;

      if (yellowHeaderCols.has(cell.value)) {
        cell.fill = {
          type: "pattern",
          pattern: "solid",
          fgColor: { argb: "FFFFFF00" }
        };
      }
    });

    for (let rowNumber = 2; rowNumber <= worksheet.rowCount; rowNumber++) {
      const row = worksheet.getRow(rowNumber);

      row.eachCell((cell, colNumber) => {
        cell.font = {
          name: "Calibri",
          size: 11
        };

        cell.alignment = {
          wrapText: true,
          vertical: "middle"
        };
        cell.border = thinBorder;

        if (colNumber === 1) {
          cell.alignment.horizontal = "left";
        }

        if (colNumber === 2) {
          cell.alignment.horizontal = "center";
          cell.alignment.vertical = "middle";
        }

        if (colNumber >= 8 && colNumber <= 11 && cell.value instanceof Date) {
          cell.numFmt = "mm-dd-yy";
        }

        if (colNumber === 4 && typeof cell.value === "number") {
          cell.numFmt = "#,##0.00";
        }
      });
    }

    const buffer = await workbook.xlsx.writeBuffer();
    const blob = new Blob(
      [buffer],
      { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }
    );

    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "purchases.xlsx";
    a.click();
    URL.revokeObjectURL(a.href);
  } catch (err) {
    console.error("Ошибка экспорта XLSX:", err);
    alert("Не удалось выгрузить XLSX");
  }
}

function resetFilters(){
  [
    "q",
    "initial_sum_from","initial_sum_to",
    "publication_datetime_from","publication_datetime_to",
    "submission_start_datetime_from","submission_start_datetime_to",
    "submission_close_datetime_from","submission_close_datetime_to"
  ].forEach(id => {
    if ($(id)) $(id).value = "";
  });

  $("sort").value = "submission_start_desc";
  $("pageSize").value = "20";
  $("statusFilter").value = "all";
  page = 1;

  saveStateToUrl();
  render();
}

function loadTheme(){
  const t = localStorage.getItem("theme") || "dark";
  document.documentElement.setAttribute("data-theme", t);
}

function toggleTheme(){
  const cur = document.documentElement.getAttribute("data-theme") || "dark";
  const next = (cur === "light") ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("theme", next);
}

function bindEvents(){
  $("btnTheme").onclick = toggleTheme;
  $("btnRefresh").onclick = apiSearch;
  $("btnSearch").onclick = apiSearch;
  $("btnReset").onclick = () => { resetFilters(); apiSearch(); };

  $("sort").onchange = () => { page = 1; render(); saveStateToUrl(); };
  $("pageSize").onchange = () => { page = 1; render(); saveStateToUrl(); };
  $("statusFilter").onchange = () => { page = 1; render(); saveStateToUrl(); };

  $("q").addEventListener("input", () => { page = 1; render(); saveStateToUrl(); });

  $("viewTable").onclick = () => setView("table");
  $("viewCards").onclick = () => setView("cards");

  $("btnExportJson").onclick = () => exportJson();
  $("btnExportXlsx").onclick = () => exportXlsx();

  $("btnDeleteExpired").onclick = () => adminPost(`${API_BASE}/admin/delete_expired`);

  $("btnSubscribeEmailNewsLetter").onclick = () => openEmailModal("subscribe");
  $("btnUnsubscribeEmailNewsLetter").onclick = () => openEmailModal("unsubscribe");
  $("btnSendCode").onclick = sendAuthCode;
  $("btnVerifyCode").onclick = verifyAuthCode;

  $("emailModalBackdrop").onclick = closeEmailModal;
  $("emailModalClose").onclick = closeEmailModal;

  $("btnRunBackfill").onclick = () => {
    const days = document.getElementById("daysInput").value;

    if (!days || days < 1) {
      alert("Пожалуйста, введите корректное количество дней (минимум 1)");
      return;
    }

    adminPost(`${API_BASE}/admin/run_backfill`, {
      token: SYSTEM_TOKEN,
      days: days
    });
  };

  $("btnRunProcessDay").onclick = () => {
    const dateInput = document.getElementById("process_day_input");
    const dateStr = dateInput.value;

    if (!dateStr) {
      alert("Пожалуйста, выберите дату");
      return;
    }

    const today = new Date().toISOString().split("T")[0];

    if (dateStr > today) {
      alert("Дата не может быть в будущем. Пожалуйста, выберите сегодняшнюю или прошлую дату");
      dateInput.value = "";
      return;
    }

    const datetimeStr = `${dateStr}T00:00:00`;

    adminPost(`${API_BASE}/admin/run_process_day`, {
      token: SYSTEM_TOKEN,
      date: datetimeStr
    });
  };

  $("modalBackdrop").onclick = closeModal;
  $("modalClose").onclick = closeModal;
  $("btnModalOk").onclick = closeModal;

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
  });
}

function initEmailModal(){
  emailModal = $("emailModal");
  emailInput = $("emailInput");
  codeInput = $("codeInput");
  codeField = $("codeField");
  emailStatus = $("emailStatus");

  btnSendCode = $("btnSendCode");
  btnVerifyCode = $("btnVerifyCode");
}

function resetSendCodeTimer() {
  if (sendCodeTimer) {
    clearInterval(sendCodeTimer);
    sendCodeTimer = null;
  }

  btnSendCode.disabled = false;
  btnSendCode.textContent =
    emailMode === "subscribe" ? "Получить код" : "Получить код для отписки";
}

function openEmailModal(mode = "subscribe"){
  emailMode = mode;

  resetSendCodeTimer();
  emailModal.classList.remove("hidden");
  lockBodyScroll();

  emailInput.value = "";
  codeInput.value = "";
  codeField.style.display = "none";
  btnVerifyCode.style.display = "none";
  emailStatus.innerText = "";

  btnVerifyCode.innerText =
    mode === "subscribe" ? "Подписаться" : "Отписаться";

  btnSendCode.innerText =
    mode === "subscribe"
      ? "Получить код"
      : "Получить код для отписки";
}

function closeEmailModal(){
  emailModal.classList.add("hidden");
  unlockBodyScroll();

  emailInput.value = "";
  codeInput.value = "";
  codeField.style.display = "none";
  btnVerifyCode.style.display = "none";
  emailStatus.innerText = "";
}

async function apiPost(url, body){
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });

  let data = {};
  try { data = await res.json(); } catch {}

  if (!res.ok){
    throw new Error(data.detail || "Ошибка");
  }

  return data;
}

async function sendAuthCode(){
  const email = emailInput.value;

  if (!email){
    emailStatus.innerText = "Введите email";
    return;
  }

  if (!SYSTEM_TOKEN){
    emailStatus.innerText = "Нет токена";
    return;
  }

  try{
    emailStatus.innerText = "Отправка...";

    await apiPost(`${API_BASE}/send_auth_code`, {
      email: email,
      token: SYSTEM_TOKEN
    });

    emailStatus.innerText = "Код отправлен";

    codeField.style.display = "block";
    btnVerifyCode.style.display = "inline-block";

    startSendCodeTimer(btnSendCode, emailMode);
  }catch(e){
    emailStatus.innerText = "❌ " + e.message;
  }
}

async function verifyAuthCode(){
  const email = emailInput.value;
  const code = codeInput.value;

  if (!code){
    emailStatus.innerText = "Введите код";
    return;
  }

  try{
    emailStatus.innerText = "Проверка...";

    await apiPost(`${API_BASE}/verify_code`, {
      email: email,
      code: String(code),
      token: SYSTEM_TOKEN
    });

    if (emailMode === "subscribe"){
      await apiPost(`${API_BASE}/put_newsletter`, {
        email: email,
        token: SYSTEM_TOKEN
      });
    } else {
      await apiPost(`${API_BASE}/delete_newsletter`, {
        email: email,
        token: SYSTEM_TOKEN
      });
    }

    emailStatus.innerText =
      emailMode === "subscribe"
        ? "✅ Почта добавлена"
        : "✅ Вы отписались";

    setTimeout(closeEmailModal, 1200);
  }catch(e){
    emailStatus.innerText = "❌ " + e.message;
  }
}

async function init(){
  loadTheme();
  initEmailModal();
  bindEvents();
  loadStateFromUrl();
  await fetchToken();
  await apiSearch();
}

init();