import customtkinter

app = customtkinter.CTk()

def open_popup():
    popup = customtkinter.CTkToplevel(app)
    popup.geometry("300x200")
    popup.title("Popup")
    label = customtkinter.CTkLabel(popup, text="This is a popup window.")
    label.pack(pady=20)
    popup.grab_set()  # Prevent interaction with the main window

button = customtkinter.CTkButton(app, text="Open Popup", command=open_popup)
button.pack(pady=50, padx=50)

app.mainloop()