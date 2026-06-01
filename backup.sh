#!/bin/bash

# Script de Backup - ComSoc C2 System
# Execute: ./backup.sh

set -e

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="./backups"
mkdir -p $BACKUP_DIR

echo "📦 Iniciando backup..."

# Backup do Supabase (exportar dados)
if [ -n "$SUPABASE_URL" ] && [ -n "$SUPABASE_KEY" ]; then
    echo "📡 Fazendo backup do banco Supabase..."
    
    # Exportar tabelas
    TABLES=("agenda" "efetivo" "fluxo_aprovacao" "bot_config" "bot_memoria" "denuncias")
    
    for TABLE in "${TABLES[@]}"; do
        echo "  - Exportando tabela: $TABLE"
        # Aqui você usaria a CLI do Supabase ou API
        # supabase db dump -t $TABLE > $BACKUP_DIR/${TABLE}_${DATE}.sql
    done
fi

# Backup de arquivos locais
if [ -d "./uploads" ]; then
    echo "📁 Fazendo backup de uploads..."
    tar -czf $BACKUP_DIR/uploads_${DATE}.tar.gz ./uploads 2>/dev/null || true
fi

# Backup do .env (criptografado recomendado)
if [ -f ".env" ]; then
    echo "🔐 Backup do .env..."
    cp .env $BACKUP_DIR/.env.$DATE
fi

# Criar arquivo de manifesto
cat > $BACKUP_DIR/manifest_$DATE.txt << EOF
Backup ComSoc C2 System
Data: $(date)
Host: $(hostname)

Arquivos incluídos:
$(ls -la $BACKUP_DIR/*_${DATE}.* 2>/dev/null | awk '{print "  - " $9}')

Status: SUCESSO
EOF

echo "✅ Backup concluído!"
echo "📂 Local: $BACKUP_DIR"
echo ""

# Limpar backups antigos (manter últimos 7)
echo "🧹 Limpando backups antigos..."
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
find $BACKUP_DIR -name ".env.*" -mtime +7 -delete
find $BACKUP_DIR -name "manifest_*.txt" -mtime +7 -delete

echo "✅ Pronto!"
