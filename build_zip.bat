@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "OUTPUT_ZIP=%SCRIPT_DIR%blender_cam_BGImg.zip"
set "TEMP_PS1=%TEMP%\build_blender_cam_BGImg_%RANDOM%%RANDOM%.ps1"

> "%TEMP_PS1%" echo $ErrorActionPreference = 'Stop'
>> "%TEMP_PS1%" echo $root = '%SCRIPT_DIR%'
>> "%TEMP_PS1%" echo $zip = '%OUTPUT_ZIP%'
>> "%TEMP_PS1%" echo $stage = Join-Path ([IO.Path]::GetTempPath()) ('blender_cam_BGImg_' + [guid]::NewGuid().ToString('N'))
>> "%TEMP_PS1%" echo $stageRoot = Join-Path $stage 'blender_cam_BGImg'
>> "%TEMP_PS1%" echo if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
>> "%TEMP_PS1%" echo New-Item -ItemType Directory -Path $stageRoot -Force ^| Out-Null
>> "%TEMP_PS1%" echo Copy-Item -LiteralPath (Join-Path $root '__init__.py') -Destination $stageRoot
>> "%TEMP_PS1%" echo if (Test-Path -LiteralPath (Join-Path $root 'README.md')) { Copy-Item -LiteralPath (Join-Path $root 'README.md') -Destination $stageRoot }
>> "%TEMP_PS1%" echo Compress-Archive -LiteralPath $stageRoot -DestinationPath $zip -Force
>> "%TEMP_PS1%" echo Remove-Item -LiteralPath $stage -Recurse -Force

powershell -NoProfile -ExecutionPolicy Bypass -File "%TEMP_PS1%"
set "EXIT_CODE=%ERRORLEVEL%"
del /f /q "%TEMP_PS1%" >nul 2>nul

if not "%EXIT_CODE%"=="0" (
  echo ZIP creation failed.
  exit /b %EXIT_CODE%
)

echo Created: %OUTPUT_ZIP%
endlocal
