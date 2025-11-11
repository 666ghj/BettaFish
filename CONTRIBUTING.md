# 贡献指南

感谢你愿意为本项目做出贡献！
为了保持代码质量和版本管理的清晰，请按照以下步骤提交你的修改。

# 🪄 提交 Pull Request（PR）步骤

## 1️⃣ Fork 仓库

将本仓库 Fork 到你的 GitHub 账户。

## 2️⃣ 克隆到本地

```bash
git clone https://github.com/<你的用户名>/<仓库名>.git
cd <仓库名>
```

## 3️⃣ 创建功能分支

```bash
git checkout -b feature/你的功能名
```

> 建议分支命名规范：`feature/xxx` 或 `fix/xxx`，便于识别功能或修复类型。

## 4️⃣ 开发与测试

* 进行代码修改，保持项目代码风格一致。
* 确保新增功能或修复通过测试。

## 5️⃣ 提交修改

```bash
git add .
git commit -m "类型: 简短描述"
```

> 推荐遵循 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/)，保持提交记录清晰。

## 6️⃣ 推送到远程仓库

```bash
git push origin feature/你的功能名
```

## 7️⃣ 发起 Pull Request

1. 在 GitHub 上点击 **New Pull Request**。
2. **目标分支必须是本仓库的 `main` 分支**。
3. 填写 PR 描述：

   * 说明主要改动内容
   * 如有相关 issue，请在 PR 中关联
