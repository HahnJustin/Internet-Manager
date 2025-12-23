# utilities/tasks.py
from __future__ import annotations

import datetime
import os
import ctypes
import win32com.client


TASK_SERVER_NAME = "Start Internet Manager Server"
TASK_GUI_NAME = "Start Internet Manager GUI"

TASK_TRIGGER_LOGON = 9
TASK_ACTION_EXEC = 0
TASK_CREATE_OR_UPDATE = 6
TASK_LOGON_INTERACTIVE_TOKEN = 3


def show_message(title: str, text: str) -> None:
    ctypes.windll.user32.MessageBoxW(0, text, title, 0x40)


def create_server_task(scheduler, action_path: str) -> None:
    task_def = scheduler.NewTask(0)
    root_folder = scheduler.GetFolder("\\")

    trigger = task_def.Triggers.Create(TASK_TRIGGER_LOGON)
    trigger.StartBoundary = datetime.datetime.now().isoformat()
    trigger.Enabled = True

    action = task_def.Actions.Create(TASK_ACTION_EXEC)
    action.ID = "StartInternetManagerServer"
    action.Path = action_path

    task_def.RegistrationInfo.Description = "Start Internet Manager Server on user logon"
    task_def.RegistrationInfo.Author = os.getlogin()

    s = task_def.Settings
    s.Enabled = True
    s.AllowDemandStart = True
    s.StartWhenAvailable = True
    s.DisallowStartIfOnBatteries = False
    s.StopIfGoingOnBatteries = False
    s.Hidden = False

    principal = task_def.Principal
    principal.UserId = os.getlogin()
    principal.LogonType = TASK_LOGON_INTERACTIVE_TOKEN
    principal.RunLevel = 1  # highest

    root_folder.RegisterTaskDefinition(
        TASK_SERVER_NAME,
        task_def,
        TASK_CREATE_OR_UPDATE,
        None,
        None,
        TASK_LOGON_INTERACTIVE_TOKEN,
    )


def create_gui_task(scheduler, action_path: str, current_user: str, delay_seconds: int = 60) -> None:
    task_def = scheduler.NewTask(0)
    root_folder = scheduler.GetFolder("\\")

    trigger = task_def.Triggers.Create(TASK_TRIGGER_LOGON)
    trigger.Delay = f"PT{max(0, int(delay_seconds))}S"
    trigger.StartBoundary = datetime.datetime.now().isoformat()
    trigger.Enabled = True

    action = task_def.Actions.Create(TASK_ACTION_EXEC)
    action.ID = "StartInternetManagerGUI"
    action.Path = action_path
    action.Arguments = ""

    task_def.RegistrationInfo.Description = "Run Internet Manager GUI after logon"
    s = task_def.Settings
    s.Enabled = True
    s.StopIfGoingOnBatteries = False
    s.StartWhenAvailable = True

    principal = task_def.Principal
    principal.UserId = current_user
    principal.LogonType = TASK_LOGON_INTERACTIVE_TOKEN
    principal.RunLevel = 1

    root_folder.RegisterTaskDefinition(
        TASK_GUI_NAME,
        task_def,
        TASK_CREATE_OR_UPDATE,
        None,
        None,
        TASK_LOGON_INTERACTIVE_TOKEN,
    )


def install_tasks(server_exe_path: str, gui_exe_path: str, delay_seconds: int = 60) -> None:
    current_user = os.getlogin()
    scheduler = win32com.client.Dispatch("Schedule.Service")
    scheduler.Connect()

    if not os.path.isfile(server_exe_path):
        raise FileNotFoundError(f"Server exe not found: {server_exe_path}")
    if not os.path.isfile(gui_exe_path):
        raise FileNotFoundError(f"GUI exe not found: {gui_exe_path}")

    create_server_task(scheduler, server_exe_path)
    create_gui_task(scheduler, gui_exe_path, current_user, delay_seconds=delay_seconds)

    show_message("Success", f"Tasks successfully created/updated for user: {current_user}")


def remove_task(task_name: str, scheduler) -> str:
    try:
        root_folder = scheduler.GetFolder("\\")
        root_folder.DeleteTask(task_name, 0)
        return f"Task '{task_name}' successfully deleted."
    except Exception as e:
        return f"Failed to delete task '{task_name}': {e}"


def uninstall_tasks() -> None:
    scheduler = win32com.client.Dispatch("Schedule.Service")
    scheduler.Connect()

    outcome = []
    outcome.append(remove_task(TASK_SERVER_NAME, scheduler))
    outcome.append(remove_task(TASK_GUI_NAME, scheduler))

    show_message("Remove Tasks", "\n".join(outcome))
