# 数据安全最高准则

## 一、核心

**任何数据文件都是用户资产。覆盖、清空、丢失数据是不可接受的。**

本规则优先级为系统最高级，任何其他规则不得冲突。

## 二、git操作安全

### 执行任何git操作前，必须检查：

- `git status` — 确认所有modified文件是否包含数据文件
- `git diff --stat` — 确认改动范围
- 如果有未追踪的数据文件被修改，**先备份**

### 禁止行为：

- ❌ 不检查就 `git checkout` 文件
- ❌ `git reset --hard` 清空工作区
- ❌ 不加思索地 `git add` 大量数据文件

### 同步远端前：

1. `git stash` 保存当前工作区
2. `git pull --rebase` 拉取远端
3. `git stash pop` 恢复工作区
4. 如有冲突，逐文件解决，**优先保护本地数据**

## 三、数据文件保护

- 所有映射数据（constituent_map、stock_sectors、etf_names等）**必须在git中追踪**，作为项目资产
- 每次生成新数据前，**先备份旧数据**：`cp file.json file.json.bak.$(date +%Y%m%d_%H%M%S)`
- 写入文件前，**先验证内容不为空**：`len(content) > 100`
- 被.gitignore排除的关键数据文件，用 `git add -f` 强制追踪

## 四、API调用节制

- 东方财富/akshare等公开API**有频率限制**
- 失败后**禁止立即重试**，最少等30秒
- 同一接口失败3次后**停止尝试**，等30分钟再试
- 批量下载时加随机间隔（1-5秒）
- 被封后**不要换参数再试**，等冷却

## 五、数据恢复

- 数据文件丢失时，首先检查：
  1. git历史：`git log -- <file>`
  2. 本地备份：`ls *.bak*`
  3. 从其他文件反向重建（如dashboard_data → constituent_map）
- 确认无法恢复后，才重新拉取
