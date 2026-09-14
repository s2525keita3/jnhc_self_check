@echo off
cd /d "%~dp0"
title 画面の作りを調べる（診断）
set PY=

python --version >nul 2>&1
if not errorlevel 1 set PY=python
if defined PY goto READY
py --version >nul 2>&1
if not errorlevel 1 set PY=py
if defined PY goto READY
echo Python が見つかりません。先に「ツールを実行.bat」を試してください。
pause
exit /b 1

:READY
echo ============================================================
echo  検索画面の作りを調べます（データは取得しません）
echo ============================================================
echo.
%PY% main.py --diagnose
echo.
echo 続けて、送信用のログをまとめます…
call "%~dp0ログをまとめる.bat"
