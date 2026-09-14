@echo off
cd /d "%~dp0"
title ログをまとめる
if exist "%~dp0logs_送信用.zip" del "%~dp0logs_送信用.zip"
powershell -NoProfile -Command "Compress-Archive -Path '%~dp0logs\*' -DestinationPath '%~dp0logs_送信用.zip' -Force"
if errorlevel 1 goto FAIL
echo.
echo ------------------------------------------------------------
echo  logs_送信用.zip を作りました。
echo  このフォルダの中にあります。
echo  %~dp0
echo  このファイルをチャットに貼り付けて送ってください。
echo ------------------------------------------------------------
echo.
explorer /select,"%~dp0logs_送信用.zip"
pause
exit /b 0

:FAIL
echo.
echo まとめに失敗しました。logs フォルダをそのまま圧縮して送ってください。
pause
exit /b 1
