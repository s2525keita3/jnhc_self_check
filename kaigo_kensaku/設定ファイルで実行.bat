@echo off
rem 画面を使わず、settings.ini の設定どおりに取得する（自動実行・定期実行向け）
cd /d "%~dp0"
title 介護事業所情報取得ツール（設定ファイル版）
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
%PY% -m pip install -q -r requirements.txt
%PY% main.py
