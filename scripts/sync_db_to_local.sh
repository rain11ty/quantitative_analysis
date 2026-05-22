#!/bin/bash
# 数据库同步脚本 - 将服务器端数据库导出供本地使用
# 用法: ./scripts/sync_db_to_local.sh

set -e

# 配置
BACKUP_DIR="/tmp"
BACKUP_FILE="stock_cursor_backup_$(date +%Y%m%d_%H%M%S).sql"
COMPRESSED_FILE="${BACKUP_FILE}.gz"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== A股量化分析系统 - 数据库同步工具 ===${NC}"
echo ""

# 检查 Docker 容器是否运行
if ! docker ps | grep -q "stock-analysis-mysql"; then
    echo -e "${RED}错误: MySQL 容器未运行${NC}"
    echo "请先启动服务: docker compose up -d mysql"
    exit 1
fi

# 获取数据库密码
DB_PASSWORD=$(grep DB_PASSWORD .env | cut -d'=' -f2)
if [ -z "$DB_PASSWORD" ]; then
    echo -e "${RED}错误: 无法从 .env 读取数据库密码${NC}"
    exit 1
fi

# 导出数据库
echo -e "${YELLOW}正在导出数据库...${NC}"
docker exec stock-analysis-mysql mysqldump \
    -u root \
    -p"${DB_PASSWORD}" \
    --single-transaction \
    --quick \
    --routines \
    --triggers \
    stock_cursor > "${BACKUP_DIR}/${BACKUP_FILE}"

echo -e "${GREEN}导出完成: ${BACKUP_DIR}/${BACKUP_FILE}${NC}"

# 压缩文件
echo -e "${YELLOW}正在压缩...${NC}"
gzip "${BACKUP_DIR}/${BACKUP_FILE}"
echo -e "${GREEN}压缩完成: ${BACKUP_DIR}/${COMPRESSED_FILE}${NC}"

# 显示文件大小
FILE_SIZE=$(du -h "${BACKUP_DIR}/${COMPRESSED_FILE}" | cut -f1)
echo -e "${GREEN}文件大小: ${FILE_SIZE}${NC}"

echo ""
echo -e "${GREEN}=== 导出完成 ===${NC}"
echo ""
echo "下一步操作："
echo "1. 将文件下载到本地:"
echo "   scp root@服务器IP:${BACKUP_DIR}/${COMPRESSED_FILE} ./"
echo ""
echo "2. 在本地导入数据库:"
echo "   docker compose up -d mysql"
echo "   sleep 30  # 等待 MySQL 就绪"
echo "   gunzip -c ${COMPRESSED_FILE} | docker exec -i stock-analysis-mysql mysql -u root -p密码 stock_cursor"
echo ""
