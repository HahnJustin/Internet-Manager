import win32com.client
import pyuac
import ctypes

def show_message(title, text):
    ctypes.windll.user32.MessageBoxW(0, text, title, 0x40)

def remove_task(task_name, scheduler):
    try:
        # Connect to the Task Scheduler root folder
        root_folder = scheduler.GetFolder('\\')

        # Delete the task
        root_folder.DeleteTask(task_name, 0)
        return f"Task '{task_name}' successfully deleted."
    except Exception as e:
        return f"Failed to delete task '{task_name}': {e}"

def main():
    scheduler = win32com.client.Dispatch('Schedule.Service')
    scheduler.Connect()

    # Task names to delete
    task_names = [
        'Start Internet Manager Server',
        'Start Internet Manager GUI'  # Add any other task names here
    ]

    # Remove each task
    outcome = ''
    for task_name in task_names:
        outcome += remove_task(task_name, scheduler) + '\n'

    show_message("Remove Tasks", outcome)

# Ensuring that the program is launched in admin
if __name__ == "__main__":
    if not pyuac.isUserAdmin():
        print("Re-launching as admin!")
        pyuac.runAsAdmin()
    else:        
        main() 