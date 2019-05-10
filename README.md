# iptv4plex
IPTV m3u8 Proxy for Plex Live TV &amp; DVR

# Requirements:

**Python 3**:

Linux: `sudo apt install python3-pip python3-tk`

Mac: `brew install python` (https://brew.sh/)

Windows: https://www.python.org/downloads/windows/

**FFMPEG**:

Linux: `sudo apt install ffmpeg jq`

Mac: `brew install ffmpeg jq` ([brew install](https://brew.sh/))

Windows: https://ffmpeg.zeranoe.com/builds/ (You will need to tell the proxy where FFMPEG is installed, it should be the full path to the exe ie. `c:\ffmpeg\ffmpeg.exe`).

# Installation:

**Note:** You need apply any auto-start strategy depending your operating system and setup.

Linux: **via PIP**: `pip3 install iptv4plex --no-cache-dir`

Linux/Mac:

```bash
cd ~/
git clone --depth 1 https://github.com/vorghahn/iptv4plex.git iptv4plex
python3 iptv4plex.py
```

Windows: **via Powershell**:

```powershell
cd $ENV:UserProfile
git clone --depth 1 https://github.com/vorghahn/iptv4plex.git iptv4plex
cd iptv4plex
Start-Process -argument "python ./iptv4plex.py" -Wait
```


# Contents:

There are two versions of the app, one written in `.py` and one in `.exe`. The executable is a simple compiled version of the python source and has no requirements.

# Operation Instructions:

On first execution you will be prompted with a GUI or otherwise a series of terminal prompts. Alternatively you can generate a `proxysettings.json` file for automation purposes.

Linux: `Execute .py`

Mac: `Execute .py`

Windows: `Execute .py`


# Comments:

You will need to enter an IP address, Is recommended to use a `static IP on your server there the app is running`, ie. 192.168.X.X, this is required because Plex doesn't seem to like 127.0.0.1!

You will need to enter a port number, use `5004` or alternatively `80` only.

You are able to add more than one m3u8/xmltv by using the add another source button in the GUI or concatenating the strings with a semicolon if using terminal (ie `http://www.1.m3u8;http://www.2.m3u8`).
For each m3u8 you can determine the maximum number of connections to that particular IPTV source at once, if in doubt enter 6.
M3u8 can be local files or URLs.
If you only have one EPG url then leave the others as blank, do not just put the same one in multiple times. Ensure you delete the sample url though!

ENDPOINTS:
```
1- ip:port/                   Combined output for Plex.
2- ip:port/playlist.m3u8      Combined m3u8 output for other uses.
3- ip:port/epg.xml            Combined xml output for Plex and other uses.
4- ip:port/channels.html      Web page menu.
```

**Plex setup guide**: [imgur link](https://imgur.com/a/BA6a2Q8)

![Plex Setup part1](/docs/plex_setup1.png)

![Plex Setup part2](/docs/plex_setup2.png)

![Plex Setup part3](/docs/plex_setup3.png)

![Plex Setup part4](/docs/plex_setup4.png)

![Plex Setup part5](/docs/plex_setup5.png)

![Plex Setup part6](/docs/plex_setup6.png)

![Plex Setup part7](/docs/plex_setup7.png)

![Plex Setup part8](/docs/plex_setup8.png)


Each m3u8 (entered by comma separated values) you enter also has it's own individual tuner as described next:
```
ip:port/0                  *The combined output and is the same as ip:port/
ip:port/1                  *Output of first m3u8 source only
ip:port/2                  *Output of second m3u8 source only
ip:port/3                  *Output of third m3u8 source only
```
This way you can add each IPTV source to Plex as a separate tuner and it will then utilise the Max Tuner Limits. Max Tuner Limits ONLY affect individual tuners and NOT the master/combined tuner.


Notes:
All settings are saved into `proxysettings.json` and can be edited later or if deleted will prompt the GUI again on next start up.
Channel filtering is saved in `cache/channels.json`.

Command line arguments:
```
-h help
-d debug
-hl headless, will disable the GUI
```

# Running as Daemon

Flask can't run easily as daemon root but you can specify the user
```
pip3 install flask
sudo cp -R iptv4plex /usr/iptv4plex.service
sudo chmod +x /usr/iptv4plex.service/iptv4plex.daemon
sudo nano /etc/systemd/system/iptv4plex.service
```
copy/edit as bellow
```
[Unit]
Description=iptv4plex daemon

[Service]
User=YOUR-USERNAME
ExecStart=/usr/iptv4plex.service/iptv4plex.daemon
TimeoutSec=600
Restart=on-failure
RuntimeDirectoryMode=755

[Install]
WantedBy=multi-user.target
```

# Donations:

PayPal - vorghahn.sstv@gmail.com

BTC - `19qvdk7JYgFruie73jE4VvW7ZJBv8uGtFb`
