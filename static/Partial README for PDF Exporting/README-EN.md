>  **Note**: If you need to use the PDF export function, please install system dependencies following the steps below. If you don't need PDF export, you can skip this step, and other system functions will not be affected.

<details>
<summary><b> Windows Installation Steps</b></summary>

```powershell
# 1. Download and install GTK3 Runtime (execute on host machine)
# Visit: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases
# Download the latest .exe file and install
# Installing it in the default path is strongly advised, as it may help prevent various unforeseen errors.

# 2. Add the GTK installation bin directory to PATH (open a new terminal afterwards)
# Default path example (replace with your custom install path if different)
set PATH=C:\Program Files\GTK3-Runtime Win64\bin;%PATH%

# Optional: persist the setting
setx PATH "C:\Program Files\GTK3-Runtime Win64\bin;%PATH%"

# If installed to a custom path, replace with your actual path, or set GTK_BIN_PATH=<your-bin-path>, then reopen the terminal

# 3. Verify in a new terminal
python -m ReportEngine.utils.dependency_check
# You should see “✓ Pango dependency check passed”
```

</details>

<details>
<summary><b> macOS Installation Steps</b></summary>

```bash
# 1. Install system dependencies (execute on host machine)
brew install pango gdk-pixbuf libffi

# 2. Set environment variable (required)
# Apple Silicon
export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH
# Intel Mac
export DYLD_LIBRARY_PATH=/usr/local/lib:$DYLD_LIBRARY_PATH

# Or permanently add to ~/.zshrc
echo 'export DYLD_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_LIBRARY_PATH' >> ~/.zshrc
# Intel users: echo 'export DYLD_LIBRARY_PATH=/usr/local/lib:$DYLD_LIBRARY_PATH' >> ~/.zshrc
source ~/.zshrc

# 3. Verify in a new terminal
python -m ReportEngine.utils.dependency_check
# You should see “✓ Pango dependency check passed”
```

</details>

<details>
<summary><b> Ubuntu/Debian Installation Steps</b></summary>

```bash
# 1. Install system dependencies (execute on host machine)
sudo apt-get update
sudo apt-get install -y \
  libpango-1.0-0 \
  libpangoft2-1.0-0 \
  libffi-dev \
  libcairo2

# Prefer the newer package name; fall back if your repo doesn't provide it
if sudo apt-cache show libgdk-pixbuf-2.0-0 >/dev/null 2>&1; then
  sudo apt-get install -y libgdk-pixbuf-2.0-0
else
  sudo apt-get install -y libgdk-pixbuf2.0-0
fi
```

</details>

<details>
<summary><b> CentOS/RHEL Installation Steps</b></summary>

```bash
# 1. Install system dependencies (execute on host machine)
sudo yum install -y pango gdk-pixbuf2 libffi-devel cairo
```

</details>


>  **Tip**: If using Docker deployment, no need to manually install these dependencies, the Docker image already contains all necessary system dependencies.
