FROM python:3.13-slim

# Diretório de trabalho
WORKDIR /app

# Copiar todos os arquivos para dentro do container
COPY . .

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y cron

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Adicionar crontab
RUN crontab crontab.txt

# Criar arquivo de log
RUN touch /app/log_cron.txt

# Iniciar o cron como processo principal do container
CMD ["cron", "-f"]
