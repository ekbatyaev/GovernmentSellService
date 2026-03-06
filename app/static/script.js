let purchases = [];
let SYSTEM_TOKEN = null;


async function fetchToken() {
    try {
        const res = await fetch("/dfwerjewbfd");
        const data = await res.json();
        SYSTEM_TOKEN = data.system_token;

        await search();
    } catch (e) {
        console.error("Не удалось получить token:", e);
    }
}

// Вызываем при загрузке страницы
fetchToken();

async function search() {
    if (!SYSTEM_TOKEN) {
        alert("Системный токен не получен");
        return;
    }

    const body = {
        token: SYSTEM_TOKEN,
        name: val("name"),
        initial_sum_from: num("initial_sum_from"),
        initial_sum_to: num("initial_sum_to"),
        publication_datetime_from: dateVal("publication_datetime_from"),
        publication_datetime_to: dateVal("publication_datetime_to"),
        submission_close_datetime_from: dateVal("submission_close_datetime_from"),
        submission_close_datetime_to: dateVal("submission_close_datetime_to"),
        source_file: val("source_file")
    };

    try {
        const res = await fetch("/get_all_purchases", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
        });

        const data = await res.json();
        purchases = data.data || [];
        applySort();
    } catch (e) {
        console.error("Ошибка запроса:", e);
    }
}

function applySort() {
    const type = document.getElementById("sort")?.value;

    if (type === "sum_desc")
        purchases.sort((a, b) => b.initial_sum - a.initial_sum);

    if (type === "sum_asc")
        purchases.sort((a, b) => a.initial_sum - b.initial_sum);

    render();
}

function render() {
    const container = document.getElementById("cards");
    container.innerHTML = "";

    document.getElementById("count").innerText = `${purchases.length} закупок`;

    purchases.forEach(p => {
        const customer = p.customer_json || {};
        const contact = p.contact_json || {};

        const card = document.createElement("div");
        card.className = "card";
        card.onclick = () => card.classList.toggle("open");

        card.innerHTML = `
            <div class="title">${p.name}</div>
            <div class="number">${p.registration_number}</div>
            <div class="sum">${Number(p.initial_sum).toLocaleString()} ₽</div>
            <div class="meta">📅 Публикация: ${p.publication_datetime?.slice(0,10) || "-"}</div>
            <div class="meta">⏳ Подача: ${p.submission_close_datetime?.slice(0,10) || "-"}</div>
            <div class="details">
                <div><b>Заказчик:</b> ${customer.full_name || "-"}</div>
                <div><b>ИНН:</b> ${customer.inn || "-"}</div>
                <br>
                <div><b>Контакт:</b></div>
                <div>${contact.last_name || ""} ${contact.first_name || ""}</div>
                <div>${contact.phone || "-"}</div>
                <div>${contact.email || "-"}</div>
                <br>
                <div><b>Источник:</b> ${p.source_file || "-"}</div>
            </div>
        `;

        container.appendChild(card);
    });
}

// Вспомогательные функции
function val(id) {
    const v = document.getElementById(id)?.value;
    return v ? v : null;
}

function num(id) {
    const v = document.getElementById(id)?.value;
    return v ? Number(v) : null;
}

function dateVal(id) {
    const v = document.getElementById(id)?.value;
    return v ? new Date(v).toISOString() : null;
}