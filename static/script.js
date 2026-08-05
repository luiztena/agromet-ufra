// Coordenadas da estação (do Flask via data-attributes)
const body = document.body;
const LAT = parseFloat(body.dataset.lat);
const LNG = parseFloat(body.dataset.lng);
const NOME = body.dataset.nome;

// Inicializar o mapa
const map = L.map('map').setView([LAT, LNG], 15);

// Adicionar camada do OpenStreetMap
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);

// Ícone personalizado para a estação
const icon = L.divIcon({
    className: 'custom-icon',
    html: `<div style="background: #2e86c1; color: white; border-radius: 50%; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; font-size: 18px; border: 3px solid white; box-shadow: 0 2px 10px rgba(0,0,0,0.3);">
            <i class="fas fa-cloud-sun"></i>
          </div>`,
    iconSize: [40, 40],
    iconAnchor: [20, 20],
    popupAnchor: [0, -20]
});

// Variável para o marcador
let marker = null;

// Função para buscar a última observação
async function buscarUltimaObservacao() {
    try {
        const response = await fetch('/api/ultima');
        if (!response.ok) throw new Error('Erro ao buscar dados');
        const dados = await response.json();
        atualizarMapa(dados);
        atualizarLegenda(dados);
        atualizarStatus('Sistema consultado às ' + new Date().toLocaleTimeString());
        document.getElementById('loading').style.display = 'none';
    } catch (error) {
        console.error('Erro:', error);
        document.getElementById('status-texto').textContent = '⚠️ Erro ao carregar dados';
        document.getElementById('loading').innerHTML = `
            <i class="fas fa-exclamation-triangle" style="color: #e74c3c;"></i>
            <p>Erro ao carregar dados. Tente novamente.</p>
            <button onclick="recarregar()" style="margin-top:10px; padding:8px 20px; background:#2e86c1; color:white; border:none; border-radius:5px; cursor:pointer;">
                <i class="fas fa-sync"></i> Recarregar
            </button>
        `;
    }
}

// Função para buscar dados de uma data específica
async function buscarPorData() {
    const data = document.getElementById('data-escolhida').value;
    if (!data) {
        alert('Selecione uma data!');
        return;
    }
    
    document.getElementById('loading').style.display = 'block';
    document.getElementById('loading').innerHTML = `
        <i class="fas fa-spinner"></i>
        <p>Buscando dados de ${formatarData(data)}...</p>
    `;
    
    try {
        const response = await fetch(`/api/data/${data}`);
        if (!response.ok) {
            if (response.status === 404) {
                alert('Sem dados para esta data. Verifique se houve observação neste dia.');
            }
            throw new Error('Erro ao buscar dados');
        }
        const dados = await response.json();
        atualizarMapa(dados);
        atualizarLegenda(dados);
        atualizarStatus('Mostrando dados de: ' + formatarData(data));
        document.getElementById('loading').style.display = 'none';
    } catch (error) {
        console.error('Erro:', error);
        document.getElementById('status-texto').textContent = '⚠️ Data não encontrada';
        document.getElementById('loading').style.display = 'none';
    }
}

// Atualizar dados direto do ISARH/UFRA
async function atualizarDadosEstacao() {
    document.getElementById('loading').style.display = 'block';
    document.getElementById('loading').innerHTML = `
        <i class="fas fa-spinner"></i>
        <p>Atualizando dados do ISARH/UFRA...</p>
    `;
    
    try {
        const response = await fetch('/api/atualizar');
        const resultado = await response.json();
        
        if (resultado.status === 'sucesso') {
            alert(`✅ Dados atualizados!\n\n📅 Data: ${resultado.data}\n🌡️ Temperatura: ${resultado.temperatura}°C\n💧 Umidade: ${resultado.umidade}%\n📊 Total de registros: ${resultado.total_registros}`);
            buscarUltimaObservacao();
        } else {
            alert('❌ Erro: ' + (resultado.mensagem || 'Falha na atualização'));
        }
    } catch (error) {
        console.error('Erro:', error);
        alert('❌ Erro ao conectar com o servidor');
    }
    
    document.getElementById('loading').style.display = 'none';
}

// Voltar para a última observação com dados
function voltarUltima() {
    document.getElementById('data-escolhida').value = '';
    document.getElementById('loading').style.display = 'block';
    document.getElementById('loading').innerHTML = `
        <i class="fas fa-spinner"></i>
        <p>Carregando última observação...</p>
    `;
    buscarUltimaObservacao();
}

// Formatar data para exibição
function formatarData(data) {
    const partes = data.split('-');
    return `${partes[2]}/${partes[1]}/${partes[0]}`;
}

function atualizarMapa(dados) {
    if (!dados) {
        console.warn('Dados não recebidos');
        return;
    }

    // Usar valor padrão '--' se o dado for null
    const temp09 = dados.temperatura_09h || '--';
    const umid09 = dados.umidade_09h || '--';
    const vento09 = dados.vento_09h || '--';
    const precip = dados.precipitacao || '--';
    const tempMin = dados.temp_min || '--';
    const tempMax = dados.temp_max || '--';
    const obs = dados.observadores || '--';

    const popupContent = `
        <div style="text-align: center;">
            <div style="font-size: 16px; font-weight: bold; color: #1a5276;">${NOME}</div>
            <div class="popup-temp">${temp09}°C</div>
            <div style="font-size: 13px; color: #666; margin-bottom: 8px;">${dados.data || 'Data não disponível'}</div>
            <div class="popup-info">
                <div><span class="label">🌡️ Mín/Máx:</span> <span class="value">${tempMin}°C / ${tempMax}°C</span></div>
                <div><span class="label">💧 Umidade:</span> <span class="value">${umid09}%</span></div>
                <div><span class="label">💨 Vento:</span> <span class="value">${vento09} m/s</span></div>
                <div><span class="label">🌧️ Precip.:</span> <span class="value">${precip} mm</span></div>
            </div>
            <div style="font-size: 11px; color: #999; margin-top: 8px; border-top: 1px solid #eee; padding-top: 5px;">
                Observadores: ${obs}
            </div>
        </div>
    `;

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

function atualizarLegenda(dados) {
    document.getElementById('leg-temp').textContent = dados.temperatura_09h || '--';
    document.getElementById('leg-umidade').textContent = dados.umidade_09h || '--';
    document.getElementById('leg-vento').textContent = dados.vento_09h || '--';
    document.getElementById('leg-precip').textContent = dados.precipitacao || '--';
    document.getElementById('leg-data').textContent = dados.data || '--';
}

function atualizarStatus(texto) {
    document.getElementById('status-texto').textContent = texto;
}

function recarregar() {
    document.getElementById('loading').style.display = 'block';
    document.getElementById('loading').innerHTML = `
        <i class="fas fa-spinner"></i>
        <p>Recarregando dados...</p>
    `;
    buscarUltimaObservacao();
}

// Atualizar a cada 5 minutos (300000 ms)
setInterval(buscarUltimaObservacao, 300000);

// Iniciar
buscarUltimaObservacao();

console.log('🌦️ Aplicação meteorológica iniciada!');
console.log(`📍 Estação: ${NOME} (${LAT}, ${LNG})`);