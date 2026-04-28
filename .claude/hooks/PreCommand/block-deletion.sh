#!/bin/bash
# ============================================================
# PreCommand Hook: 阻止文件/目录删除命令
# 在 dangerouslyDisableSandbox 模式下提供额外的安全层
# ============================================================

INPUT="$1"

# ---- 删除命令检测 -------------------------------------------------
# 匹配: rm, del, erase, rmdir, rd, Remove-Item, deltree
if echo "$INPUT" | grep -qiE '(^|;|\s|&|\|)(rm|del|erase|rmdir|rd|deltree|Remove-Item|delete-item)(\s|$|/|")'; then
  echo ""
  echo "  ==============================================="
  echo "  [HOOK 阻断] 检测到删除命令，已被阻止执行"
  echo "  命令: $INPUT"
  echo "  如需删除文件，请手动操作"
  echo "  ==============================================="
  echo ""
  exit 1
fi

# ---- 危险 git 操作检测 -------------------------------------------
# 阻止 git clean, git reset --hard, git checkout -- (丢弃修改)
if echo "$INPUT" | grep -qiE '(git\s+clean|git\s+reset\s+--hard|git\s+checkout\s+--\s)'; then
  echo ""
  echo "  ==============================================="
  echo "  [HOOK 阻断] 检测到破坏性 Git 操作，已被阻止执行"
  echo "  命令: $INPUT"
  echo "  ==============================================="
  echo ""
  exit 1
fi

# ---- 磁盘/分区危险操作 -------------------------------------------
if echo "$INPUT" | grep -qiE '(^|;|\s|&|\|)(diskpart|format\s|dd\s|shred|wipe)(\s|$|/)'; then
  echo ""
  echo "  ==============================================="
  echo "  [HOOK 阻断] 检测到磁盘级危险操作，已被阻止执行"
  echo "  命令: $INPUT"
  echo "  ==============================================="
  echo ""
  exit 1
fi

exit 0
