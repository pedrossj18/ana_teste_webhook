import pandas as pd
import json
from datetime import datetime, timedelta
from pytz import timezone
from influxdb_client import InfluxDBClient
import requests
import smtplib
from email.message import EmailMessage
import os

# === CONFIGURAÇÕES ===

# InfluxDB
URL_INFLUX = "https://exemplo.influxdb.com:8086"
TOKEN = os.getenv("TOKEN_INFLUX", "SEU_TOKEN_DE_EXEMPLO_AQUI")
ORG = "sua-organizacao"
BUCKET = "SeuBucketDeDados"

# Webhook
URL_ENVIO = "https://webhook.site/seu-codigo-de-teste"

# E-mail
EMAIL_REMETENTE = "email.remetente@exemplo.com"
SENHA_APP = os.getenv("SENHA_EMAIL_APP", "senha_app_exemplo")
EMAIL_DESTINO = "email.destinatario@exemplo.com"

# Arquivos
CAMINHO_SAIDA = "saida_bomba.json"
CAMINHO_TXT = "confirmacao_envio.txt"
CAMINHO_LOG = "log_execucao.txt"

# BIBLIOTECA PARA AJUSTAR HORARIOS DE (AMERICA / SÃO PAULO)
br_tz = timezone("America/Sao_Paulo") 
datetime.now(br_tz).strftime('%Y-%m-%d %H:%M:%S')

# === CONSULTA INFLUX E PROCESSAMENTO ===

query = f"""
from(bucket: "{BUCKET}")
  |> range(start: -7d)
  |> filter(fn: (r) => r["_measurement"] == "ChirpStack_Params")
  |> filter(fn: (r) => r["_field"] == "mainVar")
  |> filter(fn: (r) => r["_applicationName"] == "APLIFLOW")
  |> filter(fn: (r) => r["_deviceName"] == "eui-0000000000000000")
  |> keep(columns: ["_time", "_value"])
"""


try:
    with InfluxDBClient(url=URL_INFLUX, token=TOKEN, org=ORG) as client:
        df = client.query_api().query_data_frame(query)
except Exception as e:
    print(f"❌ Erro ao consultar InfluxDB: {e}")
    exit()

if df.empty:
    print("❌ Nenhum dado retornado do InfluxDB.")
    exit()

df = df[["_time", "_value"]]
df["_time"] = pd.to_datetime(df["_time"]).dt.tz_convert("America/Sao_Paulo")
df.sort_values(by="_time", inplace=True)

# Expansão minuto a minuto
expanded = []
for i in range(1, len(df)):
    t0 = df.iloc[i-1]["_time"]
    t1 = df.iloc[i]["_time"]
    v0 = df.iloc[i-1]["_value"]
    v1 = df.iloc[i]["_value"]
    minutos = int((t1 - t0).total_seconds() / 60)
    delta_total = v1 - v0
    if minutos <= 0:
        continue
    if delta_total == 0:
        for m in range(1, minutos + 1):
            expanded.append({
                "timestamp": (t0 + timedelta(minutes=m)).strftime('%Y-%m-%dT%H:%M:%S-03:00'),
                "volume": int(v0),
                "duracao": 0
            })
    else:
        incremento_inteiro = delta_total // minutos
        restante = delta_total % minutos
        valor = v0
        for m in range(1, minutos + 1):
            valor += incremento_inteiro
            if m == minutos:
                valor += restante
            expanded.append({
                "timestamp": (t0 + timedelta(minutes=m)).strftime('%Y-%m-%dT%H:%M:%S-03:00'),
                "volume": int(valor),
                "duracao": 60
            })

# Agrupar em 15min
df_exp = pd.DataFrame(expanded)
df_exp['timestamp'] = pd.to_datetime(df_exp['timestamp'])
df_15min = df_exp.resample('15min', on='timestamp').agg({
    'volume': 'last',
    'duracao': 'sum'
}).reset_index()

# Vazão
df_15min['volume_anterior'] = df_15min['volume'].shift(1)
df_15min['delta_volume'] = df_15min['volume'] - df_15min['volume_anterior']
df_15min['vazao'] = df_15min.apply(lambda x: (x['delta_volume'] / x['duracao']) if x['duracao'] > 0 else 0, axis=1)

# Monta JSON
leituras = []
for _, row in df_15min.iterrows():
    if pd.isna(row["vazao"]):
        continue
    leituras.append({
        "horario": row["timestamp"].strftime('%Y-%m-%dT%H:%M:%S-03:00'),
        "vazao": round(row["vazao"], 2),
        "duracao": int(row["duracao"]),
        "volume": int(row["volume"]),
        "codigoTransmissao" : 100
    })

saida_json = {
    "intervencao": "SFR_016",
    "leituras": leituras
}

# Salva arquivos
with open(CAMINHO_SAIDA, "w") as f:
    json.dump(saida_json, f, indent=4)
print(f"[{datetime.now(br_tz).isoformat()}] ✅ JSON salvo em: {CAMINHO_SAIDA}")

with open(CAMINHO_TXT, "w", encoding="utf-8") as f:
    f.write("✅ Confirmação de geração de dados para ANA\n")
    f.write(f"Data: {datetime.now(br_tz).strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"Intervenção: {saida_json['intervencao']}\n")
    f.write(f"Número de leituras: {len(leituras)}\n")
    f.write(f"codigoTransmissao")
print(f"[{datetime.now(br_tz).isoformat()}] 📄 Confirmação salva em: {CAMINHO_TXT}")

# === ENVIO PARA WEBHOOK ===
try:
    print(f"📡 Enviando JSON para: {URL_ENVIO}")
    resposta = requests.post(URL_ENVIO, json=saida_json)
    if resposta.ok:
        print("📡 JSON enviado com sucesso!")
    else:
        print(f"⚠️ Erro no envio: {resposta.status_code} - {resposta.text}")
except Exception as e:
    print(f"❌ Erro ao enviar JSON: {e}")

# === ENVIO DE E-MAIL ===
try:
    with open(CAMINHO_TXT, "r", encoding="utf-8") as f:
        conteudo_txt = f.read()

    msg = EmailMessage()
    msg["Subject"] = "Confirmação de envio para ANA"
    msg["From"] = EMAIL_REMETENTE
    msg["To"] = EMAIL_DESTINO
    msg.set_content(conteudo_txt)

    with open(CAMINHO_SAIDA, "rb") as f:
        conteudo_json = f.read()
        msg.add_attachment(conteudo_json, maintype="application", subtype="json", filename=CAMINHO_SAIDA)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_REMETENTE, SENHA_APP)
        smtp.send_message(msg)

    print("📧 E-mail enviado com sucesso!")
except Exception as e:
    print(f"❌ Erro ao enviar e-mail: {e}")

# === LOG DE EXECUÇÃO ===
with open(CAMINHO_LOG, "a", encoding="utf-8") as f:
    f.write(f"[{datetime.now(br_tz).strftime('%Y-%m-%d %H:%M:%S')}] Execução concluída com {len(leituras)} leituras.")