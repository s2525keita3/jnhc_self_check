@echo off
cd /d "%~dp0"
title 介護事業所情報取得ツール
set PY=

python --version >nul 2>&1
if not errorlevel 1 set PY=python
if defined PY goto READY

py --version >nul 2>&1
if not errorlevel 1 set PY=py
if defined PY goto READY

goto NOPYTHON

:READY
echo ============================================================
echo  介護事業所情報取得ツール
echo ============================================================
echo.
echo 必要な部品を確認しています。初回は数分かかります…
%PY% -m pip install -q -r requirements.txt
if errorlevel 1 goto PIPFAIL
echo 確認できました。
echo.
%PY% main.py
goto END

:PIPFAIL
echo.
echo ------------------------------------------------------------
echo 必要な部品のインストールに失敗しました。
echo インターネットに接続されているか確認してください。
echo 社内ネットワークの場合は、管理者に確認が必要な場合があります。
echo ------------------------------------------------------------
echo.
pause
exit /b 1

:NOPYTHON
echo ------------------------------------------------------------
echo Python がインストールされていません。
echo.
echo このあとブラウザで配布サイトを開きます。
echo   1. 黄色い「Download Python」ボタンを押す
echo   2. ダウンロードしたファイルを実行する
echo   3. ★最初の画面の下にある
echo      「Add python.exe to PATH」に必ずチェックを入れる★
echo   4. 「Install Now」を押す
echo.
echo インストールが終わったら、もう一度このファイルを
echo ダブルクリックしてください。
echo ------------------------------------------------------------
echo.
pause
start https://www.python.org/downloads/
exit /b 1

:END
echo.
pause
