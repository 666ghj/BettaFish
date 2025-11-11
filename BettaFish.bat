@echo off

REM 切换到当前 bat 文件所在目录（不怕有中文路径）
cd /d "%~dp0"

REM 激活虚拟环境（注意：是 activate.bat，不是 Activate.ps1）
call .\myenv\Scripts\activate.bat

REM 运行你的程序
python app.py

REM 防止双击后窗口一闪而过（如果不需要可以删掉这一行）
pause
