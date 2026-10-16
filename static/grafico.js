// ==========================================================
// Dashboard de Comparação Tripla
// ==========================================================

var estado = {
    variavel: "tmax",
    ano: null,
    estacoes: ["ufra", "82191", "a201"],
    dados: null,
    mensal: null,
    chart: null
};


// ==========================================================
// Inicialização
// ==========================================================
document.addEventListener("DOMContentLoaded", async function () {
    await carregarAnos();
    configurarEventos();
    await carregarTudo();
});


async function carregarAnos() {
    var sel = document.getElementById("select-ano");
    try {
        var resp = await fetch("/api/comparacao/anos");
        var json = await resp.json();

        sel.innerHTML = "";
        if (!json.anos || json.anos.length === 0) {
            sel.innerHTML = '<option value="">Sem dados</option>';
            return;
        }

        for (var i = 0; i < json.anos.length; i++) {
            var opt = document.createElement("option");
            opt.value = json.anos[i];
            opt.textContent = json.anos[i];
            sel.appendChild(opt);
        }

        // Ano mais recente por padrão
        sel.value = json.anos[json.anos.length - 1];
        estado.ano = parseInt(sel.value, 10);
    } catch (e) {
        console.error("Erro ao carregar anos:", e);
        sel.innerHTML = '<option value="">Erro</option>';
    }
}


function configurarEventos() {
    document.getElementById("select-variavel").addEventListener("change", function () {
        estado.variavel = this.value;
        carregarTudo();
    });

    document.getElementById("select-ano").addEventListener("change", function () {
        estado.ano = parseInt(this.value, 10);
        carregarTudo();
    });

    ["ufra", "82191", "a201"].forEach(function (id) {
        document.getElementById("check-" + id).addEventListener("change", function () {
            atualizarEstacoes();
            carregarTudo();
        });
    });

    document.querySelectorAll(".comp-tab").forEach(function (tab) {
        tab.addEventListener("click", function () {
            var alvo = this.dataset.tab;
            document.querySelectorAll(".comp-tab").forEach(t => t.classList.remove("active"));
            document.querySelectorAll(".comp-painel").forEach(p => p.classList.remove("active"));
            this.classList.add("active");
            document.getElementById("painel-" + alvo).classList.add("active");
        });
    });
}


function atualizarEstacoes() {
    estado.estacoes = [];
    ["ufra", "82191", "a201"].forEach(function (id) {
        if (document.getElementById("check-" + id).checked) {
            estado.estacoes.push(id);
        }
    });
}


async function carregarTudo() {
    if (!estado.ano || estado.estacoes.length === 0) {
        return;
    }
    await carregarDiario();
    await carregarMensal();
    renderizarGrafico();
    renderizarTabelaDiaria();
    renderizarTabelaMensal();
    renderizarAvisos();
    renderizarResumoCards();
}


// ==========================================================
// Fetch dos dados
// ==========================================================
async function carregarDiario() {
    var url = "/api/comparacao/" + estado.ano + "/" + estado.variavel;
    url += "?estacoes=" + estado.estacoes.join(",");

    try {
        var resp = await fetch(url);
        if (!resp.ok) {
            estado.dados = null;
            return;
        }
        estado.dados = await resp.json();
    } catch (e) {
        console.error("Erro ao carregar diário:", e);
        estado.dados = null;
    }
}


async function carregarMensal() {
    var url = "/api/comparacao/mensal/" + estado.ano + "/" + estado.variavel;
    url += "?estacoes=" + estado.estacoes.join(",");

    try {
        var resp = await fetch(url);
        if (!resp.ok) {
            estado.mensal = null;
            return;
        }
        estado.mensal = await resp.json();
    } catch (e) {
        console.error("Erro ao carregar mensal:", e);
        estado.mensal = null;
    }
}


// ==========================================================
// Gráfico
// ==========================================================
function renderizarGrafico() {
    if (!estado.dados || !estado.dados.dados) {
        if (estado.chart) {
            estado.chart.destroy();
            estado.chart = null;
        }
        return;
    }

    var registros = estado.dados.dados;
    var labels = registros.map(r => formatarDataCurta(r.data));

    var cores = {
        ufra:   { borda: "#2e86c1", fundo: "rgba(46, 134, 193, 0.1)" },
        "82191": { borda: "#c0392b", fundo: "rgba(192, 57, 43, 0.1)" },
        a201:   { borda: "#27ae60", fundo: "rgba(39, 174, 96, 0.1)" }
    };

    var labels_estacoes = {
        ufra:   "UFRA-BEL",
        "82191": "INMET 82191",
        a201:   "INMET A201"
    };

    var datasets = [];
    estado.estacoes.forEach(function (id) {
        if (!estado.dados.estacoes_disponiveis.includes(id)) return;
        var valores = registros.map(r => r[id] != null ? r[id] : null);
        datasets.push({
            label: labels_estacoes[id],
            data: valores,
            borderColor: cores[id].borda,
            backgroundColor: cores[id].fundo,
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.2,
            spanGaps: false
        });
    });

    var ctx = document.getElementById("grafico-comparacao").getContext("2d");
    if (estado.chart) {
        estado.chart.destroy();
    }

    estado.chart = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: "index" },
            plugins: {
                legend: {
                    position: "top",
                    labels: { boxWidth: 14, padding: 12, font: { size: 12 } }
                },
                tooltip: {
                    callbacks: {
                        label: function (item) {
                            if (item.parsed.y == null) return null;
                            return item.dataset.label + ": " + item.parsed.y.toFixed(2) + " °C";
                        }
                    }
                },
                title: {
                    display: true,
                    text: (estado.variavel === "tmax" ? "Temperatura Máxima" : "Temperatura Mínima") + " — " + estado.ano,
                    font: { size: 14, weight: "bold" },
                    color: "#1a3a5c",
                    padding: { bottom: 10 }
                }
            },
            scales: {
                y: {
                    title: { display: true, text: "Temperatura (°C)", font: { size: 12 } },
                    grid: { color: "rgba(0,0,0,0.05)" }
                },
                x: {
                    grid: { display: false },
                    ticks: { maxTicksLimit: 12, font: { size: 10 } }
                }
            }
        }
    });
}


// ==========================================================
// Tabela Diária
// ==========================================================
function renderizarTabelaDiaria() {
    var tbody = document.querySelector("#tabela-diaria tbody");
    tbody.innerHTML = "";

    if (!estado.dados || !estado.dados.dados) {
        tbody.innerHTML = '<tr><td colspan="6" class="comp-tabela-vazia">Sem dados</td></tr>';
        return;
    }

    var registros = estado.dados.dados;

    registros.forEach(function (r) {
        var ufra = r.ufra;
        var ref1 = r["82191"];
        var ref2 = r.a201;

        var v1 = (ufra != null && ref1 != null) ? (ufra - ref1) : null;
        var v2 = (ufra != null && ref2 != null) ? (ufra - ref2) : null;

        var tr = document.createElement("tr");
        tr.innerHTML =
            "<td>" + formatarDataCompleta(r.data) + "</td>" +
            "<td>" + formatarValor(ufra) + "</td>" +
            "<td>" + formatarValor(ref1) + "</td>" +
            "<td>" + formatarValor(ref2) + "</td>" +
            "<td>" + formatarVies(v1) + "</td>" +
            "<td>" + formatarVies(v2) + "</td>";
        tbody.appendChild(tr);
    });
}


// ==========================================================
// Tabela Mensal
// ==========================================================
function renderizarTabelaMensal() {
    var tbody = document.querySelector("#tabela-mensal tbody");
    tbody.innerHTML = "";

    if (!estado.mensal || !estado.mensal.mensal) {
        tbody.innerHTML = '<tr><td colspan="7" class="comp-tabela-vazia">Sem dados</td></tr>';
        return;
    }

    var nomes_mes = ["", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                     "Jul", "Ago", "Set", "Out", "Nov", "Dez"];

    estado.mensal.mensal.forEach(function (r) {
        var tr = document.createElement("tr");
        tr.innerHTML =
            "<td>" + nomes_mes[r.mes] + "</td>" +
            "<td>" + formatarValor(r.ufra) + "</td>" +
            "<td>" + formatarValor(r["82191"]) + "</td>" +
            "<td>" + formatarValor(r.a201) + "</td>" +
            "<td>" + formatarVies(r.vies_ufra_82191) + "</td>" +
            "<td>" + formatarVies(r.vies_ufra_a201) + "</td>" +
            "<td>" + formatarVies(r.vies_82191_a201) + "</td>";
        tbody.appendChild(tr);
    });
}


// ==========================================================
// Avisos
// ==========================================================
function renderizarAvisos() {
    var el = document.getElementById("comp-avisos");
    if (!estado.dados || !estado.dados.avisos || estado.dados.avisos.length === 0) {
        el.style.display = "none";
        return;
    }

    var html = "<strong><i class='fas fa-exclamation-triangle'></i> Avisos:</strong><ul>";
    estado.dados.avisos.forEach(function (a) {
        html += "<li>" + a + "</li>";
    });
    html += "</ul>";

    el.innerHTML = html;
    el.style.display = "block";
}


// ==========================================================
// Resumo (cards abaixo do gráfico)
// ==========================================================
function renderizarResumoCards() {
    var el = document.getElementById("comp-resumo-cards");
    el.innerHTML = "";

    if (!estado.dados || !estado.dados.resumo) {
        return;
    }

    var resumo = estado.dados.resumo;
    var chaves = Object.keys(resumo);

    chaves.forEach(function (chave) {
        var m = resumo[chave];
        if (!m) return;

        var partes = chave.split("_vs_");
        var nome_a = partes[0].toUpperCase();
        var nome_b = partes[1].toUpperCase();

        var card = document.createElement("div");
        card.className = "comp-card";
        card.innerHTML =
            "<h4>" + nome_a + " × " + nome_b + "</h4>" +
            "<div class='comp-card-linha'><span>N pareado</span><strong>" + m.n + "</strong></div>" +
            "<div class='comp-card-linha'><span>Viés médio</span><strong>" + m.vies.toFixed(3) + " °C</strong></div>" +
            "<div class='comp-card-linha'><span>IC 95%</span><strong>[" + m.ic_inf.toFixed(3) + ", " + m.ic_sup.toFixed(3) + "]</strong></div>" +
            "<div class='comp-card-linha'><span>RMSE</span><strong>" + m.rmse.toFixed(3) + " °C</strong></div>" +
            "<div class='comp-card-linha'><span>Correlação r</span><strong>" + (m.r != null ? m.r.toFixed(3) : "—") + "</strong></div>" +
            "<div class='comp-card-linha'><span>Willmott d</span><strong>" + (m.d != null ? m.d.toFixed(3) : "—") + "</strong></div>";

        el.appendChild(card);
    });
}


// ==========================================================
// Exportar PDF (via print do navegador por enquanto)
// ==========================================================
function exportarPDF() {
    window.print();
}


// ==========================================================
// Helpers
// ==========================================================
function formatarDataCurta(iso) {
    if (!iso) return "";
    var p = iso.split("-");
    return p[2] + "/" + p[1];
}

function formatarDataCompleta(iso) {
    if (!iso) return "";
    var p = iso.split("-");
    return p[2] + "/" + p[1] + "/" + p[0];
}

function formatarValor(v) {
    if (v == null) return '<span class="comp-nulo">—</span>';
    return v.toFixed(2) + " °C";
}

function formatarVies(v) {
    if (v == null) return '<span class="comp-nulo">—</span>';
    var cls = v > 0 ? "comp-vies-positivo" : "comp-vies-negativo";
    var sinal = v > 0 ? "+" : "";
    return '<span class="' + cls + '">' + sinal + v.toFixed(2) + "</span>";
}