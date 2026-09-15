@echo off
cd /d "%~dp0"
title 詳細ページを調べる
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
echo  詳細ページを1件だけ取得して中身を調べます
echo  （データの取得はしません。1分ほどで終わります）
echo ============================================================
echo.
%PY% main.py --diagnose-detail
echo.
echo このフォルダの「詳細ページ.html」と、logs フォルダの
echo 「詳細ページ診断.txt」を送ってください。
echo.
explorer "%~dp0"
pause
