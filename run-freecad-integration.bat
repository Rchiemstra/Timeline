@echo off
setlocal EnableExtensions

rem Run TipTrack's FreeCAD GUI integration smoke test in Docker.
rem Artifacts are written to the local artifacts\ directory.

cd /d "%~dp0"

where docker >nul 2>nul
if errorlevel 1 (
    echo ERROR: Docker was not found on PATH.
    exit /b 1
)

set "IMAGE=lscr.io/linuxserver/freecad:1.0.2"
set "ARTIFACTS=%CD%\artifacts"

if not exist "%ARTIFACTS%" mkdir "%ARTIFACTS%"

echo Cleaning old integration artifacts...
del /q "%ARTIFACTS%\freecad_tiptrack_frame_*.png" 2>nul
del /q "%ARTIFACTS%\record_frame_*.png" 2>nul
del /q "%ARTIFACTS%\freecad-tiptrack-integration.mp4" 2>nul
del /q "%ARTIFACTS%\freecad-tiptrack-integration.gif" 2>nul
del /q "%ARTIFACTS%\tiptrack_integration.FCStd" 2>nul
del /q "%ARTIFACTS%\tiptrack_integration.*.FCBak" 2>nul
del /q "%ARTIFACTS%\tiptrack_integration_summary.json" 2>nul
del /q "%ARTIFACTS%\tiptrack_integration_failure.txt" 2>nul

echo Running FreeCAD Docker GUI smoke test...
docker run --rm ^
  -v "%CD%:/work" ^
  -w /work ^
  --entrypoint /bin/bash ^
  %IMAGE% ^
  -lc "TIPTRACK_REPO_ROOT=/work TIPTRACK_ARTIFACT_DIR=/work/artifacts timeout 120s xvfb-run -a /opt/freecad/usr/bin/freecad /work/tests/integration/freecad_tiptrack_gui_smoke.py"

if errorlevel 1 (
    echo.
    echo ERROR: FreeCAD integration test failed.
    if exist "%ARTIFACTS%\tiptrack_integration_failure.txt" (
        echo Failure details:
        type "%ARTIFACTS%\tiptrack_integration_failure.txt"
    )
    exit /b 1
)

if exist "%ARTIFACTS%\tiptrack_integration_summary.json" (
    echo.
    echo Integration summary:
    type "%ARTIFACTS%\tiptrack_integration_summary.json"
)

where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo.
    echo ffmpeg was not found on PATH; skipping MP4/GIF generation.
    echo Screenshots and the FCStd model are available in artifacts\.
    exit /b 0
)

echo.
echo Building recording artifacts with ffmpeg...
copy /y "%ARTIFACTS%\freecad_tiptrack_frame_00_initial.png" "%ARTIFACTS%\record_frame_00.png" >nul
copy /y "%ARTIFACTS%\freecad_tiptrack_frame_01_scrub_sketch.png" "%ARTIFACTS%\record_frame_01.png" >nul
copy /y "%ARTIFACTS%\freecad_tiptrack_frame_02_scrub_pad.png" "%ARTIFACTS%\record_frame_02.png" >nul
copy /y "%ARTIFACTS%\freecad_tiptrack_frame_03_two_pads_no_hole.png" "%ARTIFACTS%\record_frame_03.png" >nul
copy /y "%ARTIFACTS%\freecad_tiptrack_frame_04_full_with_hole.png" "%ARTIFACTS%\record_frame_04.png" >nul
copy /y "%ARTIFACTS%\freecad_tiptrack_frame_05_playback_done.png" "%ARTIFACTS%\record_frame_05.png" >nul

ffmpeg -y -framerate 1 -i "%ARTIFACTS%\record_frame_%%02d.png" -vf "fps=10,scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p" "%ARTIFACTS%\freecad-tiptrack-integration.mp4"
if errorlevel 1 exit /b 1

ffmpeg -y -framerate 1 -i "%ARTIFACTS%\record_frame_%%02d.png" -vf "fps=5,scale=960:-2:flags=lanczos" "%ARTIFACTS%\freecad-tiptrack-integration.gif"
if errorlevel 1 exit /b 1

del /q "%ARTIFACTS%\record_frame_*.png" 2>nul

echo.
echo Done. Artifacts are in:
echo %ARTIFACTS%

endlocal
