@echo off
REM ==========================================================================
REM  run_packsize.bat  -  Packsize Module daily build
REM  Power Stop LLC / HK1
REM
REM  Double-click, or schedule in Task Scheduler for ~06:45 so the dashboard
REM  is ready before the 7:30 call.
REM
REM  Drop today's files first:
REM    ..\Carton Production File\   <- PackNet carton production export
REM    ..\Error Excel File\         <- PackNet error / availability export
REM ==========================================================================

setlocal
cd /d "%~dp0"

echo.
echo  ===============================================
echo   Packsize Module - building daily dashboard
echo  ===============================================
echo.

REM Prefer the py launcher; fall back to whatever python is on PATH.
where py >nul 2>&1 && (set PY=py -3) || (set PY=python)

%PY% run.py --open
set RC=%ERRORLEVEL%

echo.
if %RC% EQU 0 (
    echo  [ DONE ] Dashboard rebuilt successfully.
) else (
    echo  [ FAILED ] Exit code %RC%.
    echo  Check packsize_run.log in this folder for the full traceback.
    echo  Most common cause: today's file was not dropped in one of the
    echo  two folders, or Excel still has it open ^(~$ lock file^).
)

echo.
echo  Press any key to close.
pause >nul
endlocal
exit /b %RC%
