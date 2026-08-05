# 🌦️ Estação Meteorológica - UFRA

Sistema de monitoramento agrometeorológico com visualização geoespacial interativa.

## 📊 Descrição

Aplicação web que consome dados meteorológicos históricos e em tempo real da estação da UFRA, disponibilizando via API REST com mapa interativo.

## 🚀 Funcionalidades

- 🗺️ Mapa interativo com Leaflet
- 📅 Busca de dados por data (2019-2026)
- 🔄 Atualização automática do site ISARH/UFRA
- 📡 API REST com 6 endpoints
- 📊 2.389 registros meteorológicos
- 📱 Design responsivo

## 🛠️ Tecnologias

- **Backend:** Python 3.x, Flask, BeautifulSoup4, Requests
- **Frontend:** HTML5, CSS3, JavaScript (Vanilla), Leaflet.js
- **Dados:** JSON, Excel (openpyxl)

## 📦 Instalação

```bash
git clone https://github.com/seu-usuario/agromet-2000.git
cd agromet-2000
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
python app.py
