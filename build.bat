start pip install --upgrade pyinstaller
start pip install --upgrade pywin32
start pyinstaller %~dp0\src\server.spec --clean --log-level=DEBUG
start pyinstaller %~dp0\src\internet_manager.spec --clean 
start pyinstaller %~dp0\src\create_tasks.spec --clean
start pyinstaller %~dp0\src\remove_tasks.spec --clean
start pyinstaller %~dp0\src\kill_server.spec --clean