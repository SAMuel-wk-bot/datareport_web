document.addEventListener("DOMContentLoaded", () => {
    const $ = (id) => document.getElementById(id);
    const controls = ["dimension", "metrica", "agregacion", "limite", "tipoGrafico", "colorPrincipal", "colorSecundario", "orden"];
    let dataset = null;
    let chart = null;
    let columnOrder = [];
    let draggedColumn = null;

    const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", "'":"&#39;", '"':"&quot;"}[char]));
    const number = (value) => new Intl.NumberFormat("es-CR", { maximumFractionDigits: 2 }).format(value || 0);

    function message(text, error = false) {
        const box = $("builderMessage");
        box.textContent = text;
        box.hidden = !text;
        box.classList.toggle("error", error);
    }

    function palette(count) {
        const start = $("colorPrincipal").value;
        const end = $("colorSecundario").value;
        if (count <= 1) return [start];
        const parse = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
        const a = parse(start), b = parse(end);
        return Array.from({ length: count }, (_, index) => {
            const ratio = index / (count - 1);
            const rgb = a.map((value, i) => Math.round(value + (b[i] - value) * ratio));
            return `rgb(${rgb.join(",")})`;
        });
    }

    function renderColumns() {
        $("columnList").innerHTML = columnOrder.map((column) => `<button class="column-chip" type="button" draggable="true" data-column="${escapeHtml(column)}"><span class="drag-handle">&#8942;&#8942;</span>${escapeHtml(column)}</button>`).join("");
        document.querySelectorAll(".column-chip").forEach((chip) => {
            chip.addEventListener("dragstart", () => { draggedColumn = chip.dataset.column; chip.classList.add("dragging"); });
            chip.addEventListener("dragend", () => { draggedColumn = null; chip.classList.remove("dragging"); });
            chip.addEventListener("dragover", (event) => event.preventDefault());
            chip.addEventListener("drop", (event) => {
                event.preventDefault();
                const target = chip.dataset.column;
                if (!draggedColumn || draggedColumn === target) return;
                columnOrder.splice(columnOrder.indexOf(draggedColumn), 1);
                columnOrder.splice(columnOrder.indexOf(target), 0, draggedColumn);
                renderColumns(); renderTable();
            });
        });
    }

    function renderTable() {
        if (!dataset) return;
        $("tableHead").innerHTML = `<tr>${columnOrder.map((column) => `<th>${escapeHtml(column)}</th>`).join("")}</tr>`;
        $("tableBody").innerHTML = dataset.filas.slice(0, 50).map((row) => `<tr>${columnOrder.map((column) => `<td>${escapeHtml(row[column])}</td>`).join("")}</tr>`).join("");
        $("rowCount").textContent = `Mostrando ${Math.min(50, dataset.filas.length)} de ${number(dataset.total_filas)}`;
    }

    async function refresh() {
        message("");
        const config = Object.fromEntries(["dimension", "metrica", "agregacion", "limite", "orden"].map((id) => [id, $(id).value]));
        try {
            const response = await fetch("/api/visualizacion", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(config) });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || "No fue posible generar la visualización.");

            const colors = palette(result.etiquetas.length);
            const type = $("tipoGrafico").value;
            if (chart) chart.destroy();
            chart = new Chart($("dashboardChart"), {
                type,
                data: { labels: result.etiquetas, datasets: [{ label: $("metrica").selectedOptions[0].text, data: result.valores, backgroundColor: colors, borderColor: type === "line" ? $("colorPrincipal").value : colors, borderWidth: 2, borderRadius: type === "bar" ? 8 : 0, tension: 0.32, fill: type === "line" }] },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: ["pie", "doughnut", "polarArea"].includes(type), position: "bottom" } }, scales: ["pie", "doughnut", "polarArea"].includes(type) ? {} : { y: { beginAtZero: true, grid: { color: "rgba(82,55,103,.08)" } }, x: { grid: { display: false } } } }
            });
            $("kpiCategorias").textContent = number(result.resumen.categorias);
            $("kpiTotal").textContent = number(result.resumen.total);
            $("kpiPromedio").textContent = number(result.resumen.promedio);
            $("chartTitle").textContent = `${$("agregacion").selectedOptions[0].text} por ${$("dimension").value}`;
        } catch (error) { message(error.message, true); }
    }

    async function load() {
        try {
            const response = await fetch("/api/datos");
            dataset = await response.json();
            if (!response.ok) throw new Error(dataset.error || "No fue posible cargar los datos.");
            columnOrder = [...dataset.columnas];
            $("kpiFilas").textContent = number(dataset.total_filas);
            renderColumns(); renderTable(); await refresh();
        } catch (error) { message(error.message, true); }
    }

    controls.forEach((id) => $(id).addEventListener("change", refresh));
    $("refreshDashboard").addEventListener("click", refresh);
    $("menuToggle").addEventListener("click", () => $("builderSidebar").classList.toggle("collapsed"));
    $("editTitle").addEventListener("click", () => {
        const title = prompt("Nombre del dashboard:", $("dashboardTitle").textContent);
        if (title?.trim()) $("dashboardTitle").textContent = title.trim();
    });
    load();
});
