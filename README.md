# Teste de Envio de Dados para Webhook

Este projeto realiza a coleta, processamento e envio de dados de volume de água da aplicação, utilizando o banco de dados InfluxDB. Os dados processados são estruturados no formato exigido pela **ANA (Agência Nacional de Águas)**, salvos localmente em JSON, enviados para um Webhook de testes e também encaminhados por e-mail como confirmação.

---

## Funcionalidades

- 🔎 Consulta dados no InfluxDB.
- ⏱️ Expande medições minuto a minuto.
- 📊 Agrega em blocos de 15 minutos.
- 💾 Gera arquivo JSON com:
  - Horário
  - Vazão
  - Duração
  - Volume
  - `codigoTransmissao = 100`
- 📫 Envia os dados para Webhook de testes.
- 📧 Envia e-mail de confirmação com o JSON em anexo.
- 🧾 Gera arquivos de log e confirmação.

---

## 🛠️ Tecnologias Utilizadas

- Python 3.10+
- InfluxDB Client
- Pandas
- Requests
- smtplib (e-mail)
- `pytz` para timezone
- Webhook.site para testes

---

## Estrutura de Arquivos

| Arquivo              | Função                                                |
|----------------------|--------------------------------------------------------|
| `main.py`            | Script principal de execução                          |
| `saida_bomba.json`   | Arquivo JSON gerado com os dados processados          |
| `confirmacao_envio.txt` | Arquivo de confirmação com resumo do envio        |
| `log_execucao.txt`   | Log da execução com horário e quantidade de leituras  |

---
