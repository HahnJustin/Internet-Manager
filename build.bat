start pip install --upgrade pyinstaller
start pip install --upgrade pywin32
start pyinstaller %~dp0\src\server.spec --clean
start pyinstaller %~dp0\src\internet_manager.spec --clean 
start pyinstaller %~dp0\src\internet_manager_utility.spec --clean 
