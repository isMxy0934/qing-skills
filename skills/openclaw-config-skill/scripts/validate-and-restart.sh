#!/bin/bash
# 验证配置并重启 Gateway
# 用法：./validate-and-restart.sh

echo "正在验证配置..."
openclaw doctor --non-interactive
RESULT=$?

if [ $RESULT -eq 0 ]; then
    echo "验证通过，正在重启 Gateway..."
    openclaw gateway restart
    echo "Gateway 重启完成"
    exit 0
else
    echo "⚠️ 验证失败，请人工检查配置"
    exit 1
fi
