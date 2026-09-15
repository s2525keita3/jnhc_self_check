@echo off
rem ---- .exe を作る（初回のみ: pip install pyinstaller）----
chcp 65001 > nul
pyinstaller --noconfirm --onefile --windowed ^
  --name itakukaigokensaku ^
  --add-data "config;config" ^
  gui.py
echo.
echo dist\itakukaigokensaku.exe が出来ました。
echo settings.ini と config フォルダを同じ場所に置いて実行してください。
pause
