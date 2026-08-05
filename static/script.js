// Coordenadas da estação (do Flask via data-attributes)
var body = document.body;
var LAT = parseFloat(body.dataset.lat);
var LNG = parseFloat(body.dataset.lng);
var NOME = body.dataset.nome;

// Inicializar o mapa
var map = L.map('map').setView([LAT, LNG], 15);

// Adicionar camada do OpenStreetMap
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);

// Ícone personalizado para a estação
var icon = L.divIcon({
    className: 'custom-icon',
    html: '<div style="background: #2e86c1; color: white; border-radius: 50%; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; font-size: 18px; border: 3px solid white; box-shadow: 0 2px 10px rgba(0,0,0,0.3);"><i class="fas fa-cloud-sun"></i></div>',
    iconSize: [40, 40],
    iconAnchor: [20, 20],
    popupAnchor: [0, -20]
});

// Variável para o marcador
var marker = null;

// Variável do gráfico
var chartInstance = null;

// Cache dos dados atmosféricos
var cacheAtmosfera = null;
var cacheAtmosferaTimestamp = 0;

// Função para obter dados atmosféricos com cache (10 min)
async function obterDadosAtmosfera() {
    var agora = Date.now();
    if (cacheAtmosfera && (agora - cacheAtmosferaTimestamp) < 600000) {
        return cacheAtmosfera;
    }
    try {
        var resp = await fetch('/api/atmosfera');
        if (resp.ok) {
            cacheAtmosfera = await resp.json();
            cacheAtmosferaTimestamp = agora;
            return cacheAtmosfera;
        }
    } catch (e) {
        console.log('Dados atmosfericos indisponiveis');
    }
    return null;
}

// Função para buscar a ultima observacao
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

// Funcao para buscar dados de uma data especifica
async function buscarPorData() {
    var data = document.getElementById('data-escolhida').value;
    if (!data) {
        alert('Selecione uma data!');
        return;
    }
    document.getElementById('loading').style.display = 'block';
    document.getElementById('loading').innerHTML = '<i class="fas fa-spinner"></i><p>Buscando dados de ' + formatarData(data) + '...</p>';
    try {
        var response = await fetch('/api/data/' + data);
        if (!response.ok) {
            if (response.status === 404) {
                alert('Sem dados para esta data.');
            }
            throw new Error('Erro ao buscar dados');
        }
        var dados = await response.json();
        await atualizarMapa(dados);
        atualizarStatus('Mostrando dados de: ' + formatarData(data));
        document.getElementById('loading').style.display = 'none';
    } catch (error) {
        console.error('Erro:', error);
        document.getElementById('status-texto').textContent = 'Data nao encontrada';
        document.getElementById('loading').style.display = 'none';
    }
}

// Atualizar dados direto do ISARH/UFRA
async function atualizarDadosEstacao() {
    document.getElementById('loading').style.display = 'block';
    document.getElementById('loading').innerHTML = '<i class="fas fa-spinner"></i><p>Atualizando dados do ISARH/UFRA...</p>';
    try {
        var response = await fetch('/api/atualizar');
        var resultado = await response.json();
        if (resultado.status === 'sucesso') {
            alert('Dados atualizados!\n\nData: ' + resultado.data + '\nTemperatura: ' + resultado.temperatura + ' C\nUmidade: ' + resultado.umidade + '%\nTotal de registros: ' + resultado.total_registros);
            cacheAtmosfera = null;
            buscarUltimaObservacao();
        } else {
            alert('Erro: ' + (resultado.mensagem || 'Falha na atualizacao'));
        }
    } catch (error) {
        console.error('Erro:', error);
        alert('Erro ao conectar com o servidor');
    }
    document.getElementById('loading').style.display = 'none';
}

// Voltar para a ultima observacao com dados
function voltarUltima() {
    document.getElementById('data-escolhida').value = '';
    document.getElementById('loading').style.display = 'block';
    document.getElementById('loading').innerHTML = '<i class="fas fa-spinner"></i><p>Carregando ultima observacao...</p>';
    buscarUltimaObservacao();
}

// Formatar data para exibicao
function formatarData(data) {
    var partes = data.split('-');
    return partes[2] + '/' + partes[1] + '/' + partes[0];
}

// Formatar hora atual como HH:MM
function agoraFormatado() {
    var d = new Date();
    var hh = String(d.getHours()).padStart(2, '0');
    var mm = String(d.getMinutes()).padStart(2, '0');
    return hh + ':' + mm;
}

// Formatar a data de hoje como DD/MM/AAAA
function hojeFormatado() {
    var d = new Date();
    var dd = String(d.getDate()).padStart(2, '0');
    var mm = String(d.getMonth() + 1).padStart(2, '0');
    var yyyy = d.getFullYear();
    return dd + '/' + mm + '/' + yyyy;
}

// Funcoes auxiliares de sensacao termica
function calcularSensacaoLocal(temp, umidade) {
    if (temp === '--' || umidade === '--') return '--';
    var T = parseFloat(temp);
    var U = parseFloat(umidade);
    if (T >= 27) {
        var Tf = (T * 9/5) + 32;
        var hi = -42.379 + 2.04901523*Tf + 10.14333127*U - 0.22475541*Tf*U - 0.00683783*Tf*Tf - 0.05481717*U*U + 0.00122874*Tf*Tf*U + 0.00085282*Tf*U*U - 0.00000199*Tf*Tf*U*U;
        var sensacao = (hi - 32) * 5/9;
        return Math.round(sensacao * 10) / 10;
    }
    return T;
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

async function carregarGrafico(dias) {
    try {
        var botoes = document.querySelectorAll('#grafico-container button');
        botoes.forEach(function(btn) {
            if (btn.onclick && btn.onclick.toString().indexOf('fecharGrafico') === -1) {
                btn.style.background = '#e8f4fd';
                btn.style.color = '#333';
                btn.style.fontWeight = 'normal';
            }
        });
        
        var respTotal = await fetch('/api/estacao');
        var info = await respTotal.json();
        var total = info.total_registros;
        var offset = Math.max(0, total - dias);
        
        var resp = await fetch('/api/todas?limite=' + dias + '&offset=' + offset);
        var dados = await resp.json();
        var registros = dados.dados;
        
        var labels = [];
        var temps09 = [];
        var tempsMin = [];
        var tempsMax = [];
        
        for (var i = 0; i < registros.length; i++) {
            var d = registros[i];
            labels.push(formatarData(d.date));
            temps09.push(d.temp_09h || null);
            tempsMin.push(d.temp_min || null);
            tempsMax.push(d.temp_max_previous_day || d.temp_max || null);
        }
        
        var ctx = document.getElementById('grafico-temperatura').getContext('2d');
        
        if (chartInstance) {
            chartInstance.destroy();
        }
        
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
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            boxWidth: 12,
                            padding: 10,
                            font: { size: 11 }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            title: function(items) {
                                return items[0].label;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        title: {
                            display: true,
                            text: 'Temperatura (°C)',
                            font: { size: 11 }
                        },
                        grid: {
                            color: 'rgba(0,0,0,0.05)'
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            maxTicksLimit: dias > 90 ? 12 : dias > 30 ? 10 : 7,
                            font: { size: 10 }
                        }
                    }
                }
            }
        });
        
    } catch (error) {
        console.error('Erro ao carregar gráfico:', error);
    }
}

// ============ MAPA E POPUP ============

async function atualizarMapa(dados) {
    if (!dados) {
        console.warn('Dados nao recebidos');
        return;
    }
    var dadosAtmosfera = await obterDadosAtmosfera();
    
    // DADOS DA ESTACAO (ISARH - 09:00)
    var temp09 = dados.temperatura_09h || '--';
    var umid09 = dados.umidade_09h || '--';
    var precip09 = dados.precipitacao || '--';
    var tempMin = dados.temp_min || '--';
    var tempMax = dados.temp_max || '--';
    var sensacao09 = dados.sensacao_termica || '';
    var obs = dados.observadores || 'Membros do Grupo ISPAAm';
    var dataObs = dados.data || '--';
    
    // DADOS ATUAIS (ECMWF)
    var tempAtual = '--';
    var umidAtual = '--';
    var sensacaoAtual = '--';
    var ceuAtual = '--';
    var ventoAtual = '--';
    var chuvaAtual = '--';
    var precipAtual = '--';
    var tempMaxAtual = '--';
    var tempMinAtual = '--';
    
    if (dadosAtmosfera && dadosAtmosfera.status === 'sucesso') {
        tempAtual = dadosAtmosfera.temperatura.atual || '--';
        umidAtual = dadosAtmosfera.temperatura.umidade || '--';
        ceuAtual = dadosAtmosfera.ceu.descricao || '--';
        ventoAtual = dadosAtmosfera.vento.velocidade + ' m/s (' + dadosAtmosfera.vento.direcao_cardeal + ')';
        chuvaAtual = dadosAtmosfera.chuva.chovendo ? 'Chovendo' : 'Sem chuva';
        precipAtual = dadosAtmosfera.chuva.precipitacao_mm + ' mm';
        tempMaxAtual = dadosAtmosfera.temperatura.maxima || '--';
        tempMinAtual = dadosAtmosfera.temperatura.minima || '--';
        if (tempAtual !== '--' && umidAtual !== '--') {
            sensacaoAtual = calcularSensacaoLocal(tempAtual, umidAtual);
        }
    }

    // MODULO AGROMETEOROLOGICO
    var balancoEnergia = null;
    try {
        var respBalanco = await fetch('/api/balanco/' + (dados.data || dataObs));
        if (respBalanco.ok) {
            balancoEnergia = await respBalanco.json();
        }
    } catch (e) {
        console.log('Modulo agrometeorologico indisponivel');
    }

    var popupContent = '' +
        '<div style="font-family: Segoe UI, sans-serif; min-width: 680px; padding: 4px;">' +
        
        // TITULO
        '<div style="text-align: center; font-size: 15px; font-weight: 700; color: #1a3a5c; margin-bottom: 10px; letter-spacing: 0.5px;">' + NOME + '</div>' +
        
        // ============ CARDS LADO A LADO ============
        '<div style="display: flex; gap: 8px; align-items: stretch;">' +
        
        // ============ ESTACAO (09:00) ============
        '<div style="flex: 1; background: linear-gradient(135deg, #e8f4fd, #d4eafc); border-radius: 10px; padding: 12px; border-top: 4px solid #2e86c1;">' +
        '<div style="font-size: 10px; font-weight: 700; color: #1a5276; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 2px;">Estacao &bull; 09:00</div>' +
        '<div style="display: flex; align-items: baseline; gap: 6px; margin-bottom: 4px;">' +
        '<span style="font-size: 26px; font-weight: 700; color: #c0392b;">' + temp09 + '</span>' +
        '<span style="font-size: 23px; color: #c0392b;">°C</span>' +
        '</div>' +
        '<div style="font-size: 11px; color: #666; margin-bottom: 4px;">' + (dataObs !== '--' ? formatarData(dataObs) : dataObs) + '</div>' +
        (sensacao09 ? '<div style="font-size: 12px; color: #e67e22; margin-bottom: 6px; font-weight: 500;">Sensacao: ' + sensacao09 + ' C</div>' : '') +
        '<div style="font-size: 11px; line-height: 1.6;">' +
        '<div><span style="color: #777;">Umidade:</span> <span style="font-weight: 600; color: #333;">' + umid09 + '%</span></div>' +
        '<div><span style="color: #777;">Vento:</span> <span style="font-weight: 600; color: #333;">--</span></div>' +
        '<div><span style="color: #777;">Precip.:</span> <span style="font-weight: 600; color: #333;">' + precip09 + ' mm</span></div>' +
        '<div><span style="color: #777;">Máxima:</span> <span style="font-weight: 600; color: #e67e22;">' + tempMax + ' °C</span><span style="font-size: 9px; color: #999;"> (dia anterior)</span></div>' +
        '<div><span style="color: #777;">Mínima:</span> <span style="font-weight: 600; color: #3498db;">' + tempMin + ' °C</span></div>' +
        '</div>' +
        '<div style="font-size: 8px; color: #999; margin-top: 6px; text-align: right;"><b>ISARH</b></div>' +
        '<div style="font-size: 9px; color: #777; margin-top: 2px; text-align: right; font-weight: 600;">' + obs + '</div>' +
        '</div>' +
        
        // ============ AGORA (ECMWF) ============
        (dadosAtmosfera && dadosAtmosfera.status === 'sucesso' ? 
        '<div style="flex: 1; background: linear-gradient(135deg, #f0e8f8, #e2d4f0); border-radius: 10px; padding: 12px; border-top: 4px solid #7b4fa0;">' +
        '<div style="font-size: 10px; font-weight: 700; color: #5a3478; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 2px;">Agora &bull; ' + agoraFormatado() + '</div>' +
        '<div style="display: flex; align-items: baseline; gap: 6px; margin-bottom: 4px;">' +
        '<span style="font-size: 26px; font-weight: 700; color: #6c3fa0;">' + tempAtual + '</span>' +
        '<span style="font-size: 23px; color: #6c3fa0;">°C</span>' +
        '</div>' +
        '<div style="font-size: 11px; color: #666; margin-bottom: 4px;">' + hojeFormatado() + '</div>' +
        (sensacaoAtual !== '--' ? '<div style="font-size: 12px; color: #e67e22; margin-bottom: 6px; font-weight: 500;">Sensacao: ' + sensacaoAtual + ' C</div>' : '') +
        '<div style="font-size: 11px; line-height: 1.6;">' +
        '<div><span style="color: #777;">Umidade:</span> <span style="font-weight: 600; color: #333;">' + umidAtual + '%</span></div>' +
        '<div><span style="color: #777;">Vento:</span> <span style="font-weight: 600; color: #333;">' + ventoAtual + '</span></div>' +
        '<div><span style="color: #777;">Precip.:</span> <span style="font-weight: 600; color: #333;">' + precipAtual + '</span></div>' +
        '<div><span style="color: #777;">Ceu:</span> <span style="font-weight: 600; color: #333;">' + ceuAtual + '</span></div>' +
        '<div><span style="color: #777;">Máxima:</span> <span style="font-weight: 600; color: #e67e22;">' + tempMaxAtual + ' °C</span><span style="font-size: 9px; color: #999;"> (previsão)</span></div>' +
        '<div><span style="color: #777;">Mínima:</span> <span style="font-weight: 600; color: #3498db;">' + tempMinAtual + ' °C</span></div>' +
        '</div>' +
        '<div style="font-size: 11px; margin-top: 4px; font-weight: 500; color: #555;">' + chuvaAtual + '</div>' +
        '<div style="font-size: 8px; color: #999; margin-top: 6px; text-align: right;"><b>ECMWF</b></div>' +
        '</div>' : '') +
        
        // ============ MODULO AGROMETEOROLOGICO ============
        (balancoEnergia && !balancoEnergia.erro ? 
        '<div style="flex: 1; background: linear-gradient(135deg, #e8f8e8, #d4f0d4); border-radius: 10px; padding: 12px; border-top: 4px solid #27ae60;">' +
        '<div style="font-size: 10px; font-weight: 700; color: #1e7e34; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px;">Modulo Agrometeorologico</div>' +
        '<div style="display: grid; grid-template-columns: auto 1fr; gap: 2px 6px; font-size: 11px;">' +
        '<div><span style="color: #777;">Ra (Q0):</span></div> <div><span style="font-weight: 600; color: #333; white-space: nowrap;">' + balancoEnergia.Ra_Q0.valor + ' MJ/m²/dia</span></div>' +
        '<div><span style="color: #777;">Rs:</span></div> <div><span style="font-weight: 600; color: #333; white-space: nowrap;">' + balancoEnergia.Rs.valor + ' MJ/m²/dia</span></div>' +
        '<div><span style="color: #777;">PAR:</span></div> <div><span style="font-weight: 600; color: #333; white-space: nowrap;">' + balancoEnergia.PAR.valor + ' MJ/m²/dia</span></div>' +
        '<div><span style="color: #777;">Rn:</span></div> <div><span style="font-weight: 600; color: #333; white-space: nowrap;">' + balancoEnergia.Rn.valor + ' MJ/m²/dia *</span></div>' +
        '<div><span style="color: #777;">Kt:</span></div> <div><span style="font-weight: 600; color: #333; white-space: nowrap;">' + balancoEnergia.Kt.valor + '</span></div>' +
        '<div><span style="color: #777;">Fotoperiodo:</span></div> <div><span style="font-weight: 600; color: #333; white-space: nowrap;">' + balancoEnergia.fotoperiodo.valor + '</span></div>' +
        '<div><span style="color: #777;">Graus-dia:</span></div> <div><span style="font-weight: 600; color: #333; white-space: nowrap;">' + balancoEnergia.graus_dia.valor + ' °C (Tb=' + balancoEnergia.graus_dia.Tbase + ' °C)</span></div>' +
        '<div><span style="color: #777;">ETo:</span></div> <div><span style="font-weight: 600; color: #333; white-space: nowrap;">' + balancoEnergia.ETo.valor + ' mm/dia</span></div>' +
        '</div>' +
        '<div style="font-size: 8px; color: #999; margin-top: 4px; text-align: right;">* Rn estimado para fins didaticos</div>' +
        '</div>' : '') +
        
        '</div>' +  // FIM DOS CARDS
        
        '</div>';

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
    cacheAtmosfera = null;
    document.getElementById('loading').style.display = 'block';
    document.getElementById('loading').innerHTML = '<i class="fas fa-spinner"></i><p>Recarregando dados...</p>';
    buscarUltimaObservacao();
}

setInterval(buscarUltimaObservacao, 300000);
buscarUltimaObservacao();
console.log('Aplicacao meteorologica iniciada!');
console.log('Estacao: ' + NOME + ' (' + LAT + ', ' + LNG + ')');