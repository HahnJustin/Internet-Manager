# Internet Manager
## What is it and why?
Basically I wanted an automated system that cut-off my internet reliably to enforce a strict bedtime, but also had the flexibility to delay that cut-off on occassion. So, I made this program that has a server and gui componenets. 
When the server is running all the functionality of internet manager is active, aka your internet connection will be cut at the configured times. The gui component allows the user to then visualize when the next cut off is as well as use the built in 'voucher' system to delay their impending cut-off.
Audio also can be configured to play to warn the user that a cut-off/shutdown is imminent. Regardless, the design is meant to be something that keeps the user informed, while allowing for a fairly strict, but slightly lenient internet shutdown experience.
> [!NOTE]
> This is a local internet manager, it only works on the machine its been downloaded onto, this is not like router parental controls
### How to set up
1. Download the server/internet_manager executables from the latest release that is not a pre-release
2. Running the server/internet_manager will create their respective config files (The server will only create the config then close)
3. Modify the configs to what you wish
4. Then open a task scheduling program/method and schedule server.exe to on startup or user log-on ([On Windows I recommend the built-in Windows Task Scheduler](https://www.youtube.com/watch?v=5cOxJDrAXyM))
> [!CAUTION]
> Server must be run using **admin priviledges** and failure to do so will render the program unable to toggle the internet on and off
5. _Optional_ - You can also schedule the internet_manager.exe to automatically open, but remember this needs to run **after** the server or it won't work
6. _Optional_ - Make a shortcut to internet_manager.exe or run it once and pin it on your hotbar
You're done! Now it should automatically run in the background everytime you use your computer
