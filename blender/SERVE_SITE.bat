@echo off
rem Serves the FCi site at http://localhost:8080 using the Python that ships inside Blender.
cd /d "%~dp0site"
set "PY="
for /d %%D in ("%ProgramFiles%\Blender Foundation\Blender*") do for /d %%V in ("%%D\*") do if exist "%%V\python\bin\python.exe" set "PY=%%V\python\bin\python.exe"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY ( echo Could not find Python. & pause & exit /b 1 )
echo Serving the FCi site at http://localhost:8080  (close this window to stop)
start "" http://localhost:8080
"%PY%" -m http.server 8080
