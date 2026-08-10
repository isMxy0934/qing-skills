#!/bin/bash
# 备份 OpenClaw 配置文件
# 用法：./backup-config.sh [备份目录] [保留数量]

BACKUP_DIR="${1:-$HOME/.openclaw/openclaw_backups}"
KEEP_COUNT="${2:-5}"
CONFIG_FILE="$HOME/.openclaw/openclaw.json"
TIMESTAMP=$(date +%Y%m%d%H%M%S)

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 生成备份文件名
BACKUP_FILE="$BACKUP_DIR/openclaw.json.$TIMESTAMP"

# 执行备份
cp "$CONFIG_FILE" "$BACKUP_FILE"

# 删除旧备份，只保留最近的 N 个
cd "$BACKUP_DIR" || exit 1
ls -1t openclaw.json.* 2>/dev/null | tail -n +$((KEEP_COUNT + 1)) | xargs -r rm -f

echo "备份完成：$BACKUP_FILE"
echo "保留最近 $KEEP_COUNT 个备份文件"
