import datetime
import win32com.client
import ctypes
import pyuac
import os
import sys

SERVER_EXECUTABLE = 'internet_manager_server.exe'
GUI_EXECUTABLE = 'internet_manager.exe'


def show_message(title, text):
    ctypes.windll.user32.MessageBoxW(0, text, title, 0x40)

def create_server_task(scheduler, action_path):
    # Create a new task definition
    task_def = scheduler.NewTask(0)

    # Access the root folder of the Task Scheduler
    root_folder = scheduler.GetFolder('\\')

    # Define the logon trigger
    TASK_TRIGGER_LOGON = 9
    trigger = task_def.Triggers.Create(TASK_TRIGGER_LOGON)
    trigger.StartBoundary = datetime.datetime.now().isoformat()  # Required StartBoundary
    trigger.Enabled = True  # Explicitly enable the trigger

    # Define the action
    TASK_ACTION_EXEC = 0
    action = task_def.Actions.Create(TASK_ACTION_EXEC)
    action.ID = 'StartInternetManagerServer'
    action.Path = action_path

    # Set registration info
    task_def.RegistrationInfo.Description = 'Start Internet Manager Server on user logon'
    task_def.RegistrationInfo.Author = os.getlogin()

    # Set task settings
    task_def.Settings.Enabled = True
    task_def.Settings.AllowDemandStart = True
    task_def.Settings.StartWhenAvailable = True
    task_def.Settings.DisallowStartIfOnBatteries = False
    task_def.Settings.StopIfGoingOnBatteries = False
    task_def.Settings.Hidden = False

    # Set the principal
    TASK_LOGON_INTERACTIVE_TOKEN = 3
    principal = task_def.Principal
    principal.UserId = os.getlogin()  # Current user
    principal.LogonType = TASK_LOGON_INTERACTIVE_TOKEN
    principal.RunLevel = 1  # TASK_RUNLEVEL_HIGHEST

    # Register the task
    TASK_CREATE_OR_UPDATE = 6
    TASK_LOGON_INTERACTIVE_TOKEN = 3
    root_folder.RegisterTaskDefinition(
        'Start Internet Manager Server',
        task_def,
        TASK_CREATE_OR_UPDATE,
        None,  # No username required
        None,  # No password required
        TASK_LOGON_INTERACTIVE_TOKEN
    )


def create_gui_task(scheduler, action_path, current_user):
    # Create a new task definition
    task_def = scheduler.NewTask(0)

    # Access the root folder of the Task Scheduler
    root_folder = scheduler.GetFolder('\\')

    # Define the logon trigger
    TASK_TRIGGER_LOGON = 9
    trigger = task_def.Triggers.Create(TASK_TRIGGER_LOGON)

    # Set a one-minute delay after user logs in
    trigger.Delay = 'PT1M'

    # Set the StartBoundary to the current time
    start_time = datetime.datetime.now()
    trigger.StartBoundary = start_time.isoformat()

    # Create the action
    TASK_ACTION_EXEC = 0
    action = task_def.Actions.Create(TASK_ACTION_EXEC)
    action.ID = 'StartInternetManagerGUI'
    action.Path = action_path
    action.Arguments = ''

    # Set task parameters
    task_def.RegistrationInfo.Description = 'Task runs InternetManagers internet_manager.exe 1 minute after logon'
    task_def.Settings.Enabled = True
    task_def.Settings.StopIfGoingOnBatteries = False
    task_def.Settings.StartWhenAvailable = True  # Start the task if missed

    # Set the principal to run the task with highest privileges
    TASK_LOGON_INTERACTIVE_TOKEN = 3
    principal = task_def.Principal
    principal.UserId = current_user
    principal.LogonType = TASK_LOGON_INTERACTIVE_TOKEN
    principal.RunLevel = 1

    # Register the task
    TASK_CREATE_OR_UPDATE = 6

    root_folder.RegisterTaskDefinition(
        'Start Internet Manager GUI',  # Task name
        task_def,
        TASK_CREATE_OR_UPDATE,
        None,  # No username needed for interactive token
        None,  # No password needed for interactive token
        TASK_LOGON_INTERACTIVE_TOKEN
    )

def main():
    # Get the current user
    current_user = os.getlogin()

    # Connect to the Task Scheduler service
    scheduler = win32com.client.Dispatch('Schedule.Service')
    scheduler.Connect()

    # Getting Application Path from .py or .exe - Thanks Max Tet
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))

    server_path = os.path.join(application_path, SERVER_EXECUTABLE)
    gui_path = os.path.join(application_path, GUI_EXECUTABLE)

    if not os.path.isfile(server_path):
        raise FileNotFoundError(f"The server file '{server_path}' does not exist. Please check move this installer into a folder where the file exists")

    if not os.path.isfile(gui_path):
        raise FileNotFoundError(f"The gui file '{gui_path}' does not exist. Please check move this installer into a folder where the file exists")

    create_server_task(scheduler, server_path)
    create_gui_task(scheduler, gui_path, current_user)

    show_message("Success", f"Tasks successfully created or updated for user: {current_user}")

# Ensuring that the program is launched in admin
if __name__ == "__main__":
    if not pyuac.isUserAdmin():
        print("Re-launching as admin!")
        pyuac.runAsAdmin()
    else:        
        main()  # Already an admin here.
