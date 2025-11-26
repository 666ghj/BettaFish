>  **注意**：如果您需要使用 PDF 导出功能，请按照以下步骤安装系统依赖。如果不需要 PDF 导出功能，可以跳过此步骤，系统其他功能不受影响。

<details>
<summary><b> Windows 系统安装步骤</b></summary>

```powershell
# 1. 下载并安装 GTK3 Runtime（在宿主机上执行）
# 访问：https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases
# 下载最新版本的 .exe 文件并安装
# 强烈建议安装到默认路径，这可能有助于规避许多未知错误

# 2. 将 GTK 安装目录下的 bin 添加到 PATH（安装后请重新打开终端）
# 默认路径示例（如果安装在其他目录，请替换成你的实际路径）
set PATH=C:\Program Files\GTK3-Runtime Win64\bin;%PATH%

# 可选：永久添加到 PATH
setx PATH "C:\Program Files\GTK3-Runtime Win64\bin;%PATH%"

# 如果安装在自定义目录，请替换为实际路径，或设置环境变量 GTK_BIN_PATH=你的bin路径，再重新打开终端

# 3. 验证（新终端执行）
python -m ReportEngine.utils.dependency_check
# 输出包含 “✓ Pango 依赖检测通过” 表示配置正确
```

</details>

<details>
<summary><b> macOS 系统安装步骤</b></summary>

```bash
# 步骤 1: 安装系统依赖
brew install pango gdk-pixbuf libffi

# 步骤 2: 设置环境变量（⚠️ 必须执行！）
# 方法一：临时设置（仅当前终端会话有效）
# Apple Silicon
export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH
# Intel Mac
export DYLD_LIBRARY_PATH=/usr/local/lib:$DYLD_LIBRARY_PATH

# 方法二：永久设置（推荐）
echo 'export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH' >> ~/.zshrc
# Intel 用户请改为:
# echo 'export DYLD_LIBRARY_PATH=/usr/local/lib:$DYLD_LIBRARY_PATH' >> ~/.zshrc
source ~/.zshrc

# 步骤 3: 验证（请在新终端执行）
python -m ReportEngine.utils.dependency_check
# 输出包含 “✓ Pango 依赖检测通过” 表示配置正确
```

**常见问题**：

- 如果仍然提示找不到库，请确保：
  1. 已执行 `source ~/.zshrc` 重新加载配置
  2. 在新终端中运行应用（确保环境变量已生效）
  3. 使用 `echo $DYLD_LIBRARY_PATH` 验证环境变量已设置

</details>

<details>
<summary><b> Ubuntu/Debian 系统安装步骤</b></summary>

```bash
# 1. 安装系统依赖（在宿主机上执行）
sudo apt-get update
sudo apt-get install -y \
  libpango-1.0-0 \
  libpangoft2-1.0-0 \
  libffi-dev \
  libcairo2

# 优先使用新包名，若仓库缺失则回退
if sudo apt-cache show libgdk-pixbuf-2.0-0 >/dev/null 2>&1; then
  sudo apt-get install -y libgdk-pixbuf-2.0-0
else
  sudo apt-get install -y libgdk-pixbuf2.0-0
fi
```

</details>

<details>
<summary><b> CentOS/RHEL 系统安装步骤</b></summary>

```bash
# 1. 安装系统依赖（在宿主机上执行）
sudo yum install -y pango gdk-pixbuf2 libffi-devel cairo
```

</details>

>  **提示**：如果使用 Docker 部署，无需手动安装这些依赖，Docker 镜像已包含所有必要的系统依赖。
