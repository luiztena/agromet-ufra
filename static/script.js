// Coordenadas da estação (do Flask via data-attributes)
var body = document.body;
var LAT = parseFloat(body.dataset.lat);
var LNG = parseFloat(body.dataset.lng);
var NOME = body.dataset.nome;


// ============ OVERRIDE DO POPUP DO LEAFLET ============
// O Leaflet limita a largura do popup em ~300px por padrão, o que faz o
// conteúdo com min-width: 820px vazar pra fora da div. Aqui liberamos a
// largura e reduzimos o padding interno. Injetado uma vez só no <head>.
(function liberarPopupLeaflet() {
    var styleEl = document.createElement('style');
    styleEl.id = 'leaflet-popup-override';
    styleEl.textContent = `
        .leaflet-popup-content {
            width: auto !important;
            max-width: none !important;
            margin: 13px 19px !important;
        }
        .leaflet-popup-content-wrapper {
            max-width: none !important;
            border-radius: 12px;
        }
        @media (max-width: 960px) {
            .leaflet-popup-content > div > div[style*="display: flex"] {
                flex-direction: column !important;
            }
        }
    `;
    document.head.appendChild(styleEl);
})();


// Inicializar o mapa
var map = L.map('map').setView([LAT, LNG], 15);

L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community',
    maxZoom: 19
}).addTo(map);

// Ícone personalizado
var icon = L.divIcon({
    className: 'custom-icon',
    html: '<div style="background: #2e86c1; color: white; border-radius: 50%; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; font-size: 18px; border: 3px solid white; box-shadow: 0 2px 10px rgba(0,0,0,0.3);"><i class="fas fa-cloud-sun"></i></div>',
    iconSize: [40, 40],
    iconAnchor: [20, 20],
    popupAnchor: [0, -20]
});

var marker = null;
var chartInstance = null;


// ============ HELPERS DE FORMATO DE DATA ============

/**
 * Aceita 'YYYY-MM-DD' (input HTML) ou 'DD/MM' ou 'DD/MM/AAAA' (resposta da API).
 * Sempre retorna 'DD/MM' (curto, para eixos de gráfico).
 */
function formatarDataCurta(data) {
    if (!data) return '--';
    if (data.indexOf('-') > -1) {
        // 'YYYY-MM-DD'
        var p = data.split('-');
        return p[2] + '/' + p[1];
    }
    // 'DD/MM' ou 'DD/MM/AAAA'
    var p2 = data.split('/');
    return p2[0] + '/' + p2[1];
}

/**
 * Aceita 'YYYY-MM-DD', 'DD/MM' ou 'DD/MM/AAAA' e retorna 'DD/MM/AAAA'.
 * - Se for 'DD/MM' sem ano, usa o ano selecionado no <select> (ou o atual).
 * - Se já vier com ano, usa o próprio.
 */
function formatarDataCompleta(data, anoFallback) {
    if (!data) return '--';

    // 'YYYY-MM-DD'
    if (data.indexOf('-') > -1) {
        var p = data.split('-');
        return p[2] + '/' + p[1] + '/' + p[0];
    }

    var p2 = data.split('/');

    // 'DD/MM/AAAA' — já tem ano
    if (p2.length === 3) {
        return p2[0] + '/' + p2[1] + '/' + p2[2];
    }

    // 'DD/MM' — usa fallback
    var ano = anoFallback
        || parseInt(document.getElementById('ano-escolhido').value, 10)
        || new Date().getFullYear();
    return p2[0] + '/' + p2[1] + '/' + ano;
}

/**
 * Converte 'YYYY-MM-DD' (input HTML) em 'DD/MM/AAAA' (formato que a API aceita).
 * Mandar com ano garante que o backend pegue a data exata, não a de outro ano.
 */
function isoParaDDMM(iso) {
    if (!iso) return null;
    var p = iso.split('-');           // ["2025","10","14"]
    if (p.length !== 3) return null;
    return p[2] + '/' + p[1] + '/' + p[0];   // "14/10/2025"
}


// ============ BUSCA PRINCIPAL ============

async function buscarUltimaObservacao() {
    try {
        var response = await fetch('/api/ultima');
        if (!response.ok) throw new Error('Erro ao buscar dados');
        var dados = await response.json();
        await atualizarMapa(dados);
        atualizarStatus('Sistema consultado as ' + new Date().toLocaleTimeString());
        document.getElementById('loading').style.display = 'none';
    } catch (error) {
        console.error('Erro:', error);
        document.getElementById('status-texto').textContent = 'Erro ao carregar dados';
        document.getElementById('loading').innerHTML = '<i class="fas fa-exclamation-triangle" style="color: #e74c3c;"></i><p>Erro ao carregar dados. Tente novamente.</p><button onclick="recarregar()" style="margin-top:10px; padding:8px 20px; background:#2e86c1; color:white; border:none; border-radius:5px; cursor:pointer;"><i class="fas fa-sync"></i> Recarregar</button>';
    }
}

async function buscarPorData() {
    var dataISO = document.getElementById('data-escolhida').value;
    if (!dataISO) {
        alert('Selecione uma data!');
        return;
    }

    // Converte YYYY-MM-DD -> DD/MM/AAAA (formato que a API aceita)
    var dataDDMM = isoParaDDMM(dataISO);

    document.getElementById('loading').style.display = 'block';
    document.getElementById('loading').innerHTML = '<i class="fas fa-spinner"></i><p>Buscando dados de ' + formatarDataCompleta(dataISO) + '...</p>';

    try {
        var response = await fetch('/api/data/' + dataDDMM);
        if (!response.ok) {
            if (response.status === 404) {
                alert('Sem dados para esta data.');
            }
            throw new Error('Erro ao buscar dados');
        }
        var dados = await response.json();
        await atualizarMapa(dados);

        // Prefere data_iso (Opção B) para mostrar a data completa
        var dataExibida = dados.data_iso || dados.data;
        atualizarStatus('Mostrando dados de: ' + formatarDataCompleta(dataExibida));

        document.getElementById('loading').style.display = 'none';
    } catch (error) {
        console.error('Erro:', error);
        document.getElementById('status-texto').textContent = 'Data nao encontrada';
        document.getElementById('loading').style.display = 'none';
    }
}

function voltarUltima() {
    document.getElementById('data-escolhida').value = '';
    document.getElementById('loading').style.display = 'block';
    document.getElementById('loading').innerHTML = '<i class="fas fa-spinner"></i><p>Carregando ultima observacao...</p>';
    buscarUltimaObservacao();
}


// ============ GRÁFICO ============

async function abrirGrafico() {
    document.getElementById('grafico-container').style.display = 'block';
    await carregarGrafico(7);
}

function fecharGrafico() {
    document.getElementById('grafico-container').style.display = 'none';
    if (chartInstance) {
        chartInstance.destroy();
        chartInstance = null;
    }
}

function anoSelecionado() {
    var el = document.getElementById('ano-escolhido');
    var v = el ? el.value : '';
    return v ? parseInt(v, 10) : null;
}

async function carregarGrafico(dias) {
    try {
        var ano = anoSelecionado();

        // Pega total de dias (com filtro de ano)
        var urlEstacao = '/api/estacao' + (ano ? '?ano=' + ano : '');
        var respInfo = await fetch(urlEstacao);
        var info = await respInfo.json();
        var totalDias = info.total_dias || 0;

        // Calcula offset para pegar os últimos `dias`
        var offset = Math.max(0, totalDias - dias);
        var urlTodas = '/api/todas?limite=' + dias + '&offset=' + offset;
        if (ano) urlTodas += '&ano=' + ano;

        var resp = await fetch(urlTodas);
        var dados = await resp.json();
        var registros = dados.dados || [];

        var labels = [];
        var temps09 = [];
        var tempsMin = [];
        var tempsMax = [];

        for (var i = 0; i < registros.length; i++) {
            var d = registros[i];
            labels.push(formatarDataCurta(d.data));
            temps09.push(d.temperatura_09h != null ? d.temperatura_09h : null);
            tempsMin.push(d.temp_min != null ? d.temp_min : null);
            tempsMax.push(d.temp_max != null ? d.temp_max : null);
        }

        var ctx = document.getElementById('grafico-temperatura').getContext('2d');
        if (chartInstance) chartInstance.destroy();

        chartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Temp. 09h',
                        data: temps09,
                        borderColor: '#e74c3c',
                        backgroundColor: 'rgba(231, 76, 60, 0.05)',
                        borderWidth: 2,
                        tension: 0.3,
                        pointRadius: dias > 30 ? 0 : 3,
                        pointBackgroundColor: '#e74c3c'
                    },
                    {
                        label: 'Temp. Mínima',
                        data: tempsMin,
                        borderColor: '#3498db',
                        backgroundColor: 'rgba(52, 152, 219, 0.05)',
                        borderWidth: 1.5,
                        tension: 0.3,
                        pointRadius: dias > 30 ? 0 : 2,
                        pointBackgroundColor: '#3498db'
                    },
                    {
                        label: 'Temp. Máxima (dia anterior)',
                        data: tempsMax,
                        borderColor: '#e67e22',
                        backgroundColor: 'rgba(230, 126, 34, 0.05)',
                        borderWidth: 1.5,
                        tension: 0.3,
                        pointRadius: dias > 30 ? 0 : 2,
                        pointBackgroundColor: '#e67e22'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                interaction: { intersect: false, mode: 'index' },
                plugins: {
                    legend: { position: 'bottom', labels: { boxWidth: 12, padding: 10, font: { size: 11 } } },
                    tooltip: { callbacks: { title: function (items) { return items[0].label; } } }
                },
                scales: {
                    y: {
                        title: { display: true, text: 'Temperatura (°C)', font: { size: 11 } },
                        grid: { color: 'rgba(0,0,0,0.05)' }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { maxTicksLimit: dias > 90 ? 12 : dias > 30 ? 10 : 7, font: { size: 10 } }
                    }
                }
            }
        });
    } catch (error) {
        console.error('Erro ao carregar gráfico:', error);
    }
}

/**
 * Chamado quando o usuário troca o ano no <select>.
 * Atualiza o range de data e recarrega o mapa/gráfico.
 */
function aoTrocarAno() {
    var ano = anoSelecionado();
    if (!ano) return;

    // Ajusta limites do input de data
    var input = document.getElementById('data-escolhida');
    input.min = ano + '-01-01';
    input.max = ano + '-12-31';
    input.value = '';

    // Recarrega o mapa com a última observação disponível
    buscarUltimaObservacao();

    // Se o gráfico estiver aberto, recarrega com o novo ano
    var gc = document.getElementById('grafico-container');
    if (gc && gc.style.display === 'block') {
        carregarGrafico(7);
    }
}


// ============ MAPA E POPUP ============

async function atualizarMapa(dados) {
    if (!dados) {
        console.warn('Dados nao recebidos');
        return;
    }

    var temp09 = dados.temperatura_09h != null ? dados.temperatura_09h : '--';
    var umid09 = dados.umidade_09h != null ? dados.umidade_09h : '--';
    var precip09 = dados.precipitacao != null ? dados.precipitacao : '--';
    var tempMin = dados.temp_min != null ? dados.temp_min : '--';
    var tempMax = dados.temp_max != null ? dados.temp_max : '--';
    var sensacao09 = dados.sensacao_termica || '';
    var obs = dados.observadores || 'Membros do Grupo ISPAAm';

    // Data para exibir: prefere data_iso (Opção B); fallback para data (dd/mm)
    var dataObs = dados.data_iso || dados.data || '--';

    // Balanço de energia (rota aceita <path:data>)
    var balancoEnergia = null;
    try {
        // A rota /api/balanco/<path:data> aceita dd/mm ou dd/mm/aaaa.
        // Mandamos no formato dd/mm/aaaa para garantir a data exata.
        var dataParaBalanco = dados.data_iso
            ? (dados.data_iso.split('-')[2] + '/' + dados.data_iso.split('-')[1] + '/' + dados.data_iso.split('-')[0])
            : (dados.data || null);

        if (dataParaBalanco) {
            var respBalanco = await fetch('/api/balanco/' + dataParaBalanco);
            if (respBalanco.ok) {
                balancoEnergia = await respBalanco.json();
            }
        }
    } catch (e) {
        console.log('Modulo agrometeorologico indisponivel');
    }

    // Conteúdo do popup: 3 cards (Estação / Agromet / Balanço de Energia)
    var popupContent = '' +
        '<div style="font-family: Segoe UI, sans-serif; min-width: 820px; padding: 4px;">' +

        '<div style="text-align: center; font-size: 15px; font-weight: 700; color: #1a3a5c; margin-bottom: 10px; letter-spacing: 0.5px;">' + NOME + '</div>' +

        '<div style="display: flex; gap: 8px; align-items: stretch;">' +

        // ============ CARD 1: ESTAÇÃO (09:00) ============
        '<div style="flex: 1; background: linear-gradient(135deg, #e8f4fd, #d4eafc); border-radius: 10px; padding: 12px; border-top: 4px solid #2e86c1;">' +
        '<div style="font-size: 10px; font-weight: 700; color: #1a5276; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 2px;">Estacao &bull; 09:00</div>' +
        '<div style="display: flex; align-items: baseline; gap: 6px; margin-bottom: 4px;">' +
        '<span style="font-size: 26px; font-weight: 700; color: #c0392b;">' + temp09 + '</span>' +
        '<span style="font-size: 23px; color: #c0392b;">°C</span>' +
        '</div>' +
        '<div style="font-size: 11px; color: #666; margin-bottom: 4px;">' + (dataObs !== '--' ? formatarDataCompleta(dataObs) : dataObs) + '</div>' +
        (sensacao09 ? '<div style="font-size: 12px; color: #e67e22; margin-bottom: 6px; font-weight: 500;">Sensacao: ' + sensacao09 + ' C</div>' : '') +
        '<div style="font-size: 11px; line-height: 1.6;">' +
        '<div><span style="color: #777;">Umidade:</span> <span style="font-weight: 600; color: #333;">' + umid09 + '%</span></div>' +
        '<div><span style="color: #777;">Vento:</span> <span style="font-weight: 600; color: #333;">--</span></div>' +
        '<div><span style="color: #777;">Precip.:</span> <span style="font-weight: 600; color: #333;">' + precip09 + ' mm</span></div>' +
        '<div><span style="color: #777;">Máxima:</span> <span style="font-weight: 600; color: #e67e22;">' + tempMax + ' °C</span><span style="font-size: 9px; color: #999;"> (dia anterior)</span></div>' +
        '<div><span style="color: #777;">Mínima:</span> <span style="font-weight: 600; color: #3498db;">' + tempMin + ' °C</span></div>' +
        '</div>' +
        '<div style="font-size: 8px; color: #999; margin-top: 6px; text-align: right;"><b>ISPAAM</b></div>' +
        '<div style="font-size: 9px; color: #777; margin-top: 2px; text-align: right; font-weight: 600;">' + obs + '</div>' +
        '</div>' +

        // ============ CARD 2: MÓDULO AGROMETEOROLÓGICO ============
        (balancoEnergia && !balancoEnergia.erro ?
        '<div style="flex: 1; background: linear-gradient(135deg, #e8f8e8, #d4f0d4); border-radius: 10px; padding: 12px; border-top: 4px solid #27ae60;">' +
        '<div style="font-size: 10px; font-weight: 700; color: #1e7e34; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px;">Modulo Agrometeorologico</div>' +
        '<div style="display: grid; grid-template-columns: auto 1fr; gap: 2px 6px; font-size: 11px;">' +
        '<div><span style="color: #777;">Ra (Q0):</span></div> <div><span style="font-weight: 600; color: #333; white-space: nowrap;">' + balancoEnergia.Ra_Q0.valor + ' MJ/m²/dia</span></div>' +
        '<div><span style="color: #777;">Rs:</span></div> <div><span style="font-weight: 600; color: #333; white-space: nowrap;">' + balancoEnergia.Rs.valor + ' MJ/m²/dia</span></div>' +
        '<div><span style="color: #777;">PAR:</span></div> <div><span style="font-weight: 600; color: #333; white-space: nowrap;">' + balancoEnergia.PAR.valor + ' MJ/m²/dia</span></div>' +
        '<div><span style="color: #777;">Kt:</span></div> <div><span style="font-weight: 600; color: #333; white-space: nowrap;">' + balancoEnergia.Kt.valor + '</span></div>' +
        '<div><span style="color: #777;">Fotoperiodo:</span></div> <div><span style="font-weight: 600; color: #333; white-space: nowrap;">' + balancoEnergia.fotoperiodo.valor + '</span></div>' +
        '<div><span style="color: #777;">Graus-dia:</span></div> <div><span style="font-weight: 600; color: #333; white-space: nowrap;">' + balancoEnergia.graus_dia.valor + ' °C (Tb=' + balancoEnergia.graus_dia.Tbase + ' °C)</span></div>' +
        '<div><span style="color: #777;">ETo:</span></div> <div><span style="font-weight: 600; color: #333; white-space: nowrap;">' + balancoEnergia.ETo.valor + ' mm/dia</span></div>' +
        '<div><span style="color: #777; font-size: 10px;">u₂ adotado:</span></div> <div><span style="font-weight: 600; color: #999; font-size: 10px; white-space: nowrap;">2,0 m/s <i>(padrão FAO)</i></span></div>' +
        '</div>' +
        '<div style="font-size: 8px; color: #999; margin-top: 4px; text-align: right; line-height: 1.4;">' +
        'Penman-Monteith (FAO-56) · G ≈ 0<br>' +
        'u₂ = 2,0 m/s <b>(valor padrão, não medido)</b>' +
        '</div>' +
        '</div>' : '') +

        // ============ CARD 3: BALANÇO DE ENERGIA ============
        (balancoEnergia && !balancoEnergia.erro ?
        '<div style="flex: 1; background: linear-gradient(135deg, #fdf4e3, #fbecd2); border-radius: 10px; padding: 12px; border-top: 4px solid #e67e22;">' +
        '<div style="font-size: 10px; font-weight: 700; color: #a0522d; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px;">Balanco de Energia</div>' +
        '<div style="display: grid; grid-template-columns: auto 1fr; gap: 2px 6px; font-size: 11px;">' +
        '<div><span style="color: #777;">☀ Ondas Curtas (Rns):</span></div> <div><span style="font-weight: 600; color: #c0392b; white-space: nowrap;">' + balancoEnergia.Rns.valor + ' MJ/m²/dia</span></div>' +
        '<div><span style="color: #777;">🌙 Ondas Longas (Rnl) ↓:</span></div> <div><span style="font-weight: 600; color: #6c3fa0; white-space: nowrap;">- ' + balancoEnergia.Rnl.valor + ' MJ/m²/dia</span></div>' +
        '<div style="border-top: 1px dashed #ccc; grid-column: 1 / -1; margin: 3px 0;"></div>' +
        '<div><span style="color: #777;">⚖ Saldo (Rn):</span></div> <div><span style="font-weight: 700; color: #1e7e34; white-space: nowrap;">' + balancoEnergia.Rn.valor + ' MJ/m²/dia</span></div>' +
        '</div>' +
        '<div style="font-size: 9px; color: #999; margin-top: 6px; padding-top: 4px; border-top: 1px dotted #ddd; line-height: 1.4;">' +
        'Rso (céu claro): <b>' + balancoEnergia.Rso.valor + '</b> MJ/m²/dia<br>' +
        'Kt (claridade): <b>' + balancoEnergia.Kt.valor + '</b> ' +
        '<span style="color: #bbb;">(0 = nublado, 0.75+ = limpo)</span>' +
        '</div>' +
        '<div style="font-size: 8px; color: #999; margin-top: 4px; text-align: right;">FAO-56: Rn = Rns − Rnl</div>' +
        '</div>' : '') +

        '</div>' +   // fecha a linha flex
        '</div>';    // fecha o container externo

    if (marker) {
        marker.setLatLng([LAT, LNG]);
        marker.setPopupContent(popupContent);
    } else {
        marker = L.marker([LAT, LNG], { icon: icon })
            .addTo(map)
            .bindPopup(popupContent)
            .openPopup();
    }
}

function atualizarStatus(texto) {
    document.getElementById('status-texto').textContent = texto;
}

function recarregar() {
    document.getElementById('loading').style.display = 'block';
    document.getElementById('loading').innerHTML = '<i class="fas fa-spinner"></i><p>Recarregando dados...</p>';
    buscarUltimaObservacao();
}

setInterval(buscarUltimaObservacao, 300000);
buscarUltimaObservacao();
console.log('Aplicacao meteorologica iniciada!');
console.log('Estacao: ' + NOME + ' (' + LAT + ', ' + LNG + ')');