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
        atualizarLegenda(dados);
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
        atualizarLegenda(dados);
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
    
    if (dadosAtmosfera && dadosAtmosfera.status === 'sucesso') {
        tempAtual = dadosAtmosfera.temperatura.atual || '--';
        umidAtual = dadosAtmosfera.temperatura.umidade || '--';
        ceuAtual = dadosAtmosfera.ceu.descricao || '--';
        ventoAtual = dadosAtmosfera.vento.velocidade + ' m/s (' + dadosAtmosfera.vento.direcao_cardeal + ')';
        chuvaAtual = dadosAtmosfera.chuva.chovendo ? 'Chovendo' : 'Sem chuva';
        precipAtual = dadosAtmosfera.chuva.precipitacao_mm + ' mm';
        if (tempAtual !== '--' && umidAtual !== '--') {
            sensacaoAtual = calcularSensacaoLocal(tempAtual, umidAtual);
        }
    }

    var popupContent = '' +
        '<div style="font-family: Segoe UI, sans-serif; min-width: 260px; padding: 4px;">' +
        
        // TITULO
        '<div style="text-align: center; font-size: 15px; font-weight: 700; color: #1a3a5c; margin-bottom: 12px; letter-spacing: 0.5px;">' + NOME + '</div>' +
        
        // ============ ESTACAO (09:00) ============
        '<div style="background: linear-gradient(135deg, #e8f4fd, #d4eafc); border-radius: 10px; padding: 14px; margin-bottom: 10px; border-left: 4px solid #2e86c1;">' +
        '<div style="font-size: 11px; font-weight: 700; color: #1a5276; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 2px;">Estacao &bull; 09:00</div>' +
        '<div style="font-size: 12px; font-weight: 700; color: #1a5276; margin-bottom: 8px;">' + dataObs + '</div>' +
        '<div style="display: flex; align-items: baseline; gap: 8px; margin-bottom: 6px;">' +
        '<span style="font-size: 28px; font-weight: 700; color: #c0392b;">' + temp09 + '</span>' +
        '<span style="font-size: 14px; color: #555;">C</span>' +
        '</div>' +
        (sensacao09 ? '<div style="font-size: 13px; color: #e67e22; margin-bottom: 8px; font-weight: 500;">Sensacao: ' + sensacao09 + ' C</div>' : '') +
        '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px 12px; font-size: 12px;">' +
        '<div><span style="color: #777;">Umidade:</span> <span style="font-weight: 600; color: #333;">' + umid09 + '%</span></div>' +
        '<div><span style="color: #777;">Vento:</span> <span style="font-weight: 600; color: #333;">--</span></div>' +
        '<div><span style="color: #777;">Precip.:</span> <span style="font-weight: 600; color: #333;">' + precip09 + ' mm</span></div>' +
        '<div><span style="color: #777;">Min/Max:</span> <span style="font-weight: 600; color: #333;">' + tempMin + '/' + tempMax + ' C</span></div>' +
        '</div>' +
        '<div style="font-size: 9px; color: #999; margin-top: 8px; text-align: right;"><b>ISARH</b></div>' +
        '<div style="font-size: 10px; color: #777; margin-top: 4px; text-align: right; font-weight: 600;">' + obs + '</div>' +
        '</div>' +
        
        // ============ AGORA (ECMWF) ============
        (dadosAtmosfera && dadosAtmosfera.status === 'sucesso' ? 
        '<div style="background: linear-gradient(135deg, #f0e8f8, #e2d4f0); border-radius: 10px; padding: 14px; border-left: 4px solid #7b4fa0;">' +
        '<div style="font-size: 11px; font-weight: 700; color: #5a3478; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px;">Agora &bull; Modelo</div>' +
        '<div style="display: flex; align-items: baseline; gap: 8px; margin-bottom: 6px;">' +
        '<span style="font-size: 28px; font-weight: 700; color: #6c3fa0;">' + tempAtual + '</span>' +
        '<span style="font-size: 14px; color: #555;">C</span>' +
        '</div>' +
        (sensacaoAtual !== '--' ? '<div style="font-size: 13px; color: #e67e22; margin-bottom: 8px; font-weight: 500;">Sensacao: ' + sensacaoAtual + ' C</div>' : '') +
        '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px 12px; font-size: 12px;">' +
        '<div><span style="color: #777;">Umidade:</span> <span style="font-weight: 600; color: #333;">' + umidAtual + '%</span></div>' +
        '<div><span style="color: #777;">Vento:</span> <span style="font-weight: 600; color: #333;">' + ventoAtual + '</span></div>' +
        '<div><span style="color: #777;">Precip.:</span> <span style="font-weight: 600; color: #333;">' + precipAtual + '</span></div>' +
        '<div><span style="color: #777;">Ceu:</span> <span style="font-weight: 600; color: #333;">' + ceuAtual + '</span></div>' +
        '</div>' +
        '<div style="font-size: 12px; margin-top: 6px; font-weight: 500; color: #555;">' + chuvaAtual + '</div>' +
        '<div style="font-size: 9px; color: #999; margin-top: 6px; text-align: right;"><b>ECMWF</b></div>' +
        '</div>' : '') +
        
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

async function atualizarLegenda(dados) {
    document.getElementById('leg-temp').textContent = dados.temperatura_09h || '--';
    document.getElementById('leg-umidade').textContent = dados.umidade_09h || '--';
    document.getElementById('leg-vento').textContent = '--';
    var precip = dados.precipitacao;
    if (!precip) {
        var atm = await obterDadosAtmosfera();
        if (atm && atm.status === 'sucesso') {
            precip = atm.chuva.precipitacao_mm;
        }
    }
    document.getElementById('leg-precip').textContent = precip || '--';
    document.getElementById('leg-data').textContent = dados.data || '--';
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