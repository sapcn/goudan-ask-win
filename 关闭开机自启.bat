@echo off
title 关闭狗蛋问问开机自启

rem 删除启动文件夹里的快捷方式
powershell -NoProfile -Command "$p = Join-Path ([Environment]::GetFolderPath('Startup')) '狗蛋问问.lnk'; if (Test-Path $p) { Remove-Item $p; Write-Host REMOVED } else { Write-Host NOTFOUND }" > "%TEMP%\goudan-autostart-off.log" 2>&1

findstr /C:"REMOVED" "%TEMP%\goudan-autostart-off.log" >nul
if %errorlevel%==0 (
    echo.
    echo  [成功] 开机自启已关闭，下次开机不再自动运行。
) else (
    echo.
    echo  [提示] 本来就没有开启自启，无需处理。
)
echo.
pause
