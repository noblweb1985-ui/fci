@echo off
cd /d "%~dp0"
set "B="
for /d %%D in ("%ProgramFiles%\Blender Foundation\Blender*") do if exist "%%D\blender.exe" set "B=%%D\blender.exe"
if not defined B for /d %%D in ("%ProgramFiles(x86)%\Steam\steamapps\common\Blender") do if exist "%%D\blender.exe" set "B=%%D\blender.exe"
if not defined B where blender >nul 2>nul && set "B=blender"
if not defined B (
  echo Blender not found. Edit RUN_BUILD.bat and set the path to blender.exe.
  pause
  exit /b 1
)
echo Building the FCi tower with "%B%" ... (about 1-3 minutes)
"%B%" -b -P "%~dp0build_tower.py" > "%~dp0build_log.txt" 2>&1
findstr /c:"FCI_BUILD_OK" "%~dp0build_log.txt" && echo Done! || (echo Something went wrong - see build_log.txt & pause)
