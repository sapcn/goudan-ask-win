@echo off
title 开启狗蛋问问开机自启
cd /d %~dp0

rem 在「启动」文件夹创建最小化快捷方式（开机后台待命，不弹窗打扰）
rem 路径用 %~dp0 展开为本目录，clone 到哪里都能用
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $dir = [Environment]::GetFolderPath('Startup'); $lnk = $ws.CreateShortcut($dir + '\狗蛋问问.lnk'); $lnk.TargetPath = '%~dp0启动狗蛋问问.bat'; $lnk.WorkingDirectory = '%~dp0'; $lnk.WindowStyle = 7; $lnk.Save(); Write-Host OK" > "%TEMP%\goudan-autostart.log" 2>&1

findstr /C:"OK" "%TEMP%\goudan-autostart.log" >nul
if %errorlevel%==0 (
    echo.
    echo  [成功] 开机自启已开启！下次开机狗蛋问问自动在后台待命。
    echo         想退出：任务栏找到最小化的控制台窗口，关掉即可。
    echo         也可在「任务管理器 - 启动应用」里管理。
) else (
    echo.
    echo  [失败] 设置未成功，详情：
    type "%TEMP%\goudan-autostart.log"
)
echo.
pause
