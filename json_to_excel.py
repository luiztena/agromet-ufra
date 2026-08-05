import json
import pandas as pd
from datetime import datetime
import os

def converter_json_para_excel(arquivo_json, arquivo_excel=None):
    """
    Converte um arquivo JSON de dados meteorológicos para Excel.
    """
    
    if arquivo_excel is None:
        nome_base = os.path.splitext(arquivo_json)[0]
        arquivo_excel = f"{nome_base}_planilha.xlsx"
    
    print(f"📂 Lendo arquivo: {arquivo_json}")
    
    with open(arquivo_json, 'r', encoding='utf-8') as f:
        dados = json.load(f)
    
    print(f"📊 Total de registros: {len(dados)}")
    
    df = pd.DataFrame(dados)
    
    print(f"📋 Colunas disponíveis: {list(df.columns)}")
    
    # Reordenar colunas
    colunas_priorizadas = [
        'date', 'temp_09h', 'humidity_09h', 'wind_09h',
        'temp_min', 'temp_max_previous_day',
        'precipitation_24h', 'evaporation_24h',
        'temp_15h', 'humidity_15h', 'wind_15h',
        'responsible_teacher', 'observers', 'note'
    ]
    
    colunas_existentes = [col for col in colunas_priorizadas if col in df.columns]
    colunas_restantes = [col for col in df.columns if col not in colunas_priorizadas]
    colunas_finais = colunas_existentes + colunas_restantes
    
    df = df[colunas_finais]
    
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        df['ano'] = df['date'].dt.year
        df['mes'] = df['date'].dt.month
        df['dia'] = df['date'].dt.day
    
    print(f"✅ DataFrame preparado com {len(df)} registros e {len(df.columns)} colunas")
    
    with pd.ExcelWriter(arquivo_excel, engine='openpyxl', datetime_format='yyyy-mm-dd') as writer:
        
        df.to_excel(writer, sheet_name='Dados_Completos', index=False)
        print(f"📝 Aba 'Dados_Completos' criada")
        
        # Estatísticas
        if 'temp_09h' in df.columns:
            stats_data = {
                'Metrica': ['Média', 'Mínimo', 'Máximo', 'Desvio Padrão', 'Contagem'],
                'Temp_09h': [
                    df['temp_09h'].mean(), df['temp_09h'].min(), 
                    df['temp_09h'].max(), df['temp_09h'].std(),
                    df['temp_09h'].count()
                ]
            }
            if 'temp_min' in df.columns:
                stats_data['Temp_Min'] = [
                    df['temp_min'].mean(), df['temp_min'].min(),
                    df['temp_min'].max(), df['temp_min'].std(),
                    df['temp_min'].count()
                ]
            if 'precipitation_24h' in df.columns:
                stats_data['Precipitacao'] = [
                    df['precipitation_24h'].mean(), df['precipitation_24h'].min(),
                    df['precipitation_24h'].max(), df['precipitation_24h'].std(),
                    df['precipitation_24h'].count()
                ]
            stats_df = pd.DataFrame(stats_data)
            stats_df.to_excel(writer, sheet_name='Estatisticas', index=False)
            print(f"📊 Aba 'Estatisticas' criada")
        
        # Médias mensais
        if 'date' in df.columns and 'temp_09h' in df.columns:
            df['mes_ano'] = df['date'].dt.to_period('M')
            medias = df.groupby('mes_ano').agg({
                'temp_09h': 'mean',
                'temp_min': 'mean' if 'temp_min' in df.columns else None,
            }).reset_index()
            medias['mes_ano'] = medias['mes_ano'].astype(str)
            medias.columns = ['Mes_Ano', 'Temp_Media_09h', 'Temp_Min_Media']
            medias.to_excel(writer, sheet_name='Medias_Mensais', index=False)
            print(f"📈 Aba 'Medias_Mensais' criada")
        
        # Contagem por ano
        if 'date' in df.columns:
            contagem = df.groupby(df['date'].dt.year).size().reset_index()
            contagem.columns = ['Ano', 'Quantidade_Registros']
            contagem.to_excel(writer, sheet_name='Contagem_por_Ano', index=False)
            print(f"📅 Aba 'Contagem_por_Ano' criada")
    
    print(f"\n✅ Planilha criada: {arquivo_excel}")
    return arquivo_excel


def verificar_dados_faltantes(df):
    faltantes = df.isnull().sum()
    faltantes = faltantes[faltantes > 0]
    if len(faltantes) > 0:
        print("\n⚠️ Dados faltantes:")
        for col, qtd in faltantes.items():
            pct = (qtd / len(df)) * 100
            print(f"   {col}: {qtd} ({pct:.1f}%)")
    else:
        print("\n✅ Sem dados faltantes!")


if __name__ == "__main__":
    # Tenta usar Agromet.json primeiro
    arquivo_json = "Agromet.json"
    
    if not os.path.exists(arquivo_json):
        print(f"❌ Arquivo '{arquivo_json}' não encontrado!")
        arquivos_json = [f for f in os.listdir('.') if f.endswith('.json')]
        if arquivos_json:
            print(f"\n📁 Arquivos JSON encontrados: {arquivos_json}")
            escolha = input("Digite o nome do arquivo para usar: ")
            if escolha.strip():
                arquivo_json = escolha.strip()
        else:
            print("❌ Nenhum arquivo JSON encontrado!")
            exit()
    
    try:
        arquivo_saida = converter_json_para_excel(arquivo_json)
        df_temp = pd.read_excel(arquivo_saida, sheet_name='Dados_Completos')
        verificar_dados_faltantes(df_temp)
        print("\n🎉 Processo concluído com sucesso!")
    except Exception as e:
        print(f"❌ Erro: {e}")