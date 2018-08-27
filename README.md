# iptv4plex
IPTV m3u8 Proxy for Plex Live TV &amp; DVR

# Install Instructions:
FFMPEG is required:
Linux: "sudo apt install ffmpeg jq"
Win/Mac: https://ffmpeg.zeranoe.com/builds/

There are two versions of the same thing, one in .py and one in .exe (Mac/Linux exeutables to follow). The executables are simple compiled versions of the python and have no requirements.
The python version requires python 3.5. There is a pip isntaller for it though to install the requirements "pip install iptv4plex --no-cache-dir" or you may need to use "pip3 install iptv4plex --no-cache-dir"
The pip installer will place the .py file into your user folder ie 'c:/users/username/iptv4plex/iptv4plex.py'.

For Linux Python only:
Do not install if you plan on running as headless
Run this to install the GUI dependency "sudo apt-get install python3-tk"

# Operation Instructions:
Run the version of the file you want, you will be prompted with a GUI or otherwise a series of terminal prompts.

You will need to enter an IP address, I recommend using a static IP on your Pc that is running this ie 192.168.1.10, google how to do this if you don't know. Plex doesn't seem to like 127.0.0.1!
You will need to enter a port number, use 80 or 5004 only.

You will need to tell the proxy where FFMPEG is installed if on Windows, it should be the full path to the exe ie c:\ffmpeg\ffmpeg.exe

You are able to add more than one m3u8/xmltv by using the add another source button in the GUI or concatenating the strings with a semicolon if using terminal (ie http://www.1.m3u8;http://www.2.m3u8).
For each m3u8 you can determine the maximum number of connections to that particular IPTV source at once, if in doubt enter 6.
M3u8 can be local files or URLs.
If you only have one EPG url then leave the others as blank, do not just put the same one in multiple times. Ensure you delete the sample url though!

Main calls to it are:
ip:port/                   *Combined output for plex THIS IS THE URL YOU PUT INTO PLEX NORMALLY
ip:port/playlist.m3u8      *Combined m3u8 output for other uses
ip:port/epg.xml            *Combined xml output for Plex and other uses
ip:port/ or ip:port/channels.html  #Web page menu

Plex setup guide: https://imgur.com/a/BA6a2Q8
The first is what plex will take, the second is a bonus and will go into kodi or cigaras iptv.bundle for plex channels (handy for sharing to friends). The third is the epg output.

Each m3u8 you enter also has it's own individual tuner:
ip:port/0                  *The combined output and is the same as ip:port/
ip:port/1                  *Output of first m3u8 source only
ip:port/2                  *Output of second m3u8 source only
ip:port/3                  *Output of third m3u8 source only
This way you can add each IPTV source to Plex as a separate tuner and it will then utilise the Max Tuner Limits. Max Tuner Limits ONLY affect individual tuners and NOT the master/combined tuner.

Proxy urls that you can use are posted in the terminal once the proxy is running.

There is a web page that allows for filtering of channels from the Plex outputs. You can filter by Groups and individual channels.

Notes:
All settings are saved into proxysettings.json and can be edited later or if deleted will prompt the GUI again on next start up.
Channel filtering is saved in cache/channels.json.

Command line arguments:
-h help
-d debug
-hl headless, will disable the GUI