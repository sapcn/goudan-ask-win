# -*- coding: utf-8 -*-
"""生成三个 bat（cmd 原生格式：GBK 编码 + CRLF 换行）。

开源版：路径全部用 %~dp0 自适应（bat 所在目录），clone 到任意位置都能用。
改了 bat 内容后重跑本脚本即可：python scripts/fix_bats.py
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

BATS = {
    "启动狗蛋问问.bat": """@echo off
title 狗蛋问问
rem %~dp0 = 本 bat 所在目录（自适应任意安装路径）
cd /d %~dp0
python -m app.main
if errorlevel 1 pause
""",
    "开启开机自启.bat": """@echo off
title 开启狗蛋问问开机自启
cd /d %~dp0

rem 在「启动」文件夹创建最小化快捷方式（开机后台待命，不弹窗打扰）
rem 路径用 %~dp0 展开为本目录，clone 到哪里都能用
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $dir = [Environment]::GetFolderPath('Startup'); $lnk = $ws.CreateShortcut($dir + '\\狗蛋问问.lnk'); $lnk.TargetPath = '%~dp0启动狗蛋问问.bat'; $lnk.WorkingDirectory = '%~dp0'; $lnk.WindowStyle = 7; $lnk.Save(); Write-Host OK" > "%TEMP%\\goudan-autostart.log" 2>&1

findstr /C:"OK" "%TEMP%\\goudan-autostart.log" >nul
if %errorlevel%==0 (
    echo.
    echo  [成功] 开机自启已开启！下次开机狗蛋问问自动在后台待命。
    echo         想退出：任务栏找到最小化的控制台窗口，关掉即可。
    echo         也可在「任务管理器 - 启动应用」里管理。
) else (
    echo.
    echo  [失败] 设置未成功，详情：
    type "%TEMP%\\goudan-autostart.log"
)
echo.
pause
""",
    "关闭开机自启.bat": """@echo off
title 关闭狗蛋问问开机自启

rem 删除启动文件夹里的快捷方式
powershell -NoProfile -Command "$p = Join-Path ([Environment]::GetFolderPath('Startup')) '狗蛋问问.lnk'; if (Test-Path $p) { Remove-Item $p; Write-Host REMOVED } else { Write-Host NOTFOUND }" > "%TEMP%\\goudan-autostart-off.log" 2>&1

findstr /C:"REMOVED" "%TEMP%\\goudan-autostart-off.log" >nul
if %errorlevel%==0 (
    echo.
    echo  [成功] 开机自启已关闭，下次开机不再自动运行。
) else (
    echo.
    echo  [提示] 本来就没有开启自启，无需处理。
)
echo.
pause
""",
}

for name, content in BATS.items():
    # cmd 原生格式：CRLF 换行 + GBK 编码
    data = content.replace("\r\n", "\n").replace("\n", "\r\n").encode("gbk")
    (ROOT / name).write_bytes(data)
    print(f"{name}: {len(data)} bytes (GBK+CRLF, %~dp0 自适应)")
print("全部生成完成")
