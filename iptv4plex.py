#!/usr/bin/env python3


import logging
import os
import sys
from datetime import datetime, timedelta
import json
from json import load, dump
from logging.handlers import RotatingFileHandler
from xml.etree import ElementTree as ET
import urllib.request as requests
import gzip
import base64
import platform
import threading
import subprocess
import time
import ntpath
import requests as req
import pickle
import argparse

parser = argparse.ArgumentParser()

parser.add_argument("-d", "--debug", action='store_true', help="Console Debugging Enable")
parser.add_argument("-hl", "--headless", action='store_true', help="Force Headless mode")

args = parser.parse_args()


try:
	import tkinter
	HEADLESS = False
except:
	HEADLESS = True
if args.headless:
	HEADLESS = True

try:
	from urlparse import urljoin
	import thread
except ImportError:
	from urllib.parse import urljoin
	import _thread

from flask import Flask, redirect, abort, request, Response, send_from_directory, jsonify, render_template, \
	stream_with_context, url_for

app = Flask(__name__, static_url_path='')

__version__ = 0.21
# Changelog
# 0.21 - Misc bug fixes
# 0.2 - Added support for GZip epg and changed epg parsing to utf-8, added command arguments properly, refer -h (help)
# 0.12 - Added more detail to channel parsing log
# 0.11 - Changed archive failed print to a debug log. Reenabled try/except for m3u8 parsing.
# 0.1 - Initial public release

type = ""
latestfile = "https://raw.githubusercontent.com/vorghahn/iptv4plex/master/iptv4plex.py"
if not sys.argv[0].endswith('.py'):
	if platform.system() == 'Linux':
		type = "Linux/"
		latestfile = "https://raw.githubusercontent.com/vorghahn/iptv4plex/master/Linux/iptv4plex"
	elif platform.system() == 'Windows':
		type = "Windows/"
		latestfile = "https://raw.githubusercontent.com/vorghahn/iptv4plex/master/Windows/iptv4plex.exe"
	elif platform.system() == 'Darwin':
		type = "Macintosh/"
		latestfile = "https://raw.githubusercontent.com/vorghahn/iptv4plex/master/Macintosh/iptv4plex"
url = "https://raw.githubusercontent.com/vorghahn/iptv4plex/master/%sversion.txt" % type
latest_ver = float(json.loads(requests.urlopen(url).read().decode('utf-8'))['Version'])


m3u8_playlist = ""
group_list = {}
language_list = {'en':True}

class channelinfo:
	epg = ""
	description = ""
	channum = 0
	channame = ""
	url = ""
	active = True
	icon = ""
	group = ''
	playlist = ''
	language = 'en'


############################################################
# CONFIG
############################################################

# These are just defaults, place your settings in a file called proxysettings.json in the same directory
LISTEN_IP = "127.0.0.1"
LISTEN_PORT = 80
SERVER_HOST = "http://" + LISTEN_IP + ":" + str(LISTEN_PORT)
M3U8URL = ''
XMLURL = ''
TUNERLIMITS = []


# LINUX/WINDOWS
if platform.system() == 'Linux':
	FFMPEGLOC = '/usr/bin/ffmpeg'

elif platform.system() == 'Windows':
	FFMPEGLOC = os.path.join('C:\FFMPEG', 'bin', 'ffmpeg.exe')

elif platform.system() == 'Darwin':
	FFMPEGLOC = '/usr/local/bin/ffmpeg'
else:
	print("Unknown OS detected... proxy may not function correctly")

############################################################
# INIT
############################################################

def load_settings():
	global LISTEN_IP, LISTEN_PORT, SERVER_HOST, M3U8URL, XMLURL, FFMPEGLOC, TUNERLIMITS
	if not os.path.isfile('./proxysettings.json'):
		logger.debug("No config file found.")
	try:
		logger.debug("Parsing settings")
		with open('./proxysettings.json') as jsonConfig:
			config = {}
			config = load(jsonConfig)
			if "ffmpegloc" in config and platform.system() == 'Windows':
				FFMPEGLOC = config["ffmpegloc"]
			if "m3u8url" in config:
				M3U8URL = config["m3u8url"]
			if "xmlurl" in config:
				XMLURL = config["xmlurl"]
			if "tunerlimits" in config:
				TUNERLIMITS = config["tunerlimits"].split(';')
			if "ip" in config and "port" in config:
				LISTEN_IP = config["ip"]
				LISTEN_PORT = config["port"]
				SERVER_HOST = "http://" + LISTEN_IP + ":" + str(LISTEN_PORT)
			logger.debug("Using config file.")

	except:
		if HEADLESS:
			config = {}
			config["ip"] = input("Listening IP address?(ie recommend 127.0.0.1 for beginners)")
			config["port"] = int(input("and port?(ie 6969, Unix require elevation for a number greater than 1024)"))
			os.system('cls' if os.name == 'nt' else 'clear')
			if platform.system() == 'Windows':
				config["ffmpegloc"] = input("FFMPEG install location (full path to ffmpeg executable)") #todo os.walk detection
				os.system('cls' if os.name == 'nt' else 'clear')
			config["m3u8url"] = input("Copy paste in m3u8 URL, seperate multiple using ;")
			os.system('cls' if os.name == 'nt' else 'clear')
			config["tunerlimits"] = input("Enter the maximum number of connections each m3u8 allows (same order as m3u8 was entered), seperate multiple using ;")
			os.system('cls' if os.name == 'nt' else 'clear')
			config["xmlurl"] = input("Copy paste in xml URL, seperate multiple using ;")
			LISTEN_IP = config["ip"]
			LISTEN_PORT = config["port"]
			SERVER_HOST = "http://" + LISTEN_IP + ":" + str(LISTEN_PORT)
			XMLURL = config["xmlurl"]
			M3U8URL = config["m3u8url"]
			if platform.system() == 'Windows':
				FFMPEGLOC = config["ffmpegloc"]
			TUNERLIMITS = config["tunerlimits"].split(';')
			with open('./proxysettings.json', 'w') as fp:
				dump(config, fp)
		else:
			root = tkinter.Tk()
			root.title("IPTV4PLEX Setup")
			app = GUI(root)  # calling the class to run
			root.mainloop()
		installer()
	# if 'install' in sys.argv:
	installer()


############################################################
# Logging
############################################################

# Setup logging
log_formatter = logging.Formatter(
	'%(asctime)s - %(levelname)-10s - %(name)-10s -  %(funcName)-25s- %(message)s')

logger = logging.getLogger('iptv4plex')
logger.setLevel(logging.DEBUG)
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# Console logging
console_handler = logging.StreamHandler()
if args.debug:
	console_handler.setLevel(logging.DEBUG)
else:
	console_handler.setLevel(logging.INFO)
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)

# Rotating Log Files
if not os.path.isdir('./cache'):
	os.mkdir('./cache')
file_handler = RotatingFileHandler('./cache/status.log', maxBytes=1024 * 1024 * 2, backupCount=5)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(log_formatter)
logger.addHandler(file_handler)


############################################################
# INSTALL
############################################################

def installer():
	writetemplate()

def writetemplate():
	if not os.path.isdir('./templates'):
		os.mkdir('./templates')
	f = open('./templates/device.xml', 'w')
	xmldata = """<root xmlns="urn:schemas-upnp-org:device-1-0">
	<specVersion>
		<major>1</major>
		<minor>0</minor>
	</specVersion>
	<URLBase>{{ data.BaseURL }}</URLBase>
	<device>
		<deviceType>urn:schemas-upnp-org:device:MediaServer:1</deviceType>
		<friendlyName>{{ data.FriendlyName }}</friendlyName>
		<manufacturer>{{ data.Manufacturer }}</manufacturer>
		<modelName>{{ data.ModelNumber }}</modelName>
		<modelNumber>{{ data.ModelNumber }}</modelNumber>
		<serialNumber>{{ data.DeviceID }}</serialNumber>
		<UDN>uuid:{{ data.DeviceID }}</UDN>
	</device>
</root>"""
	f.write(xmldata)
	f.close()


############################################################
# INSTALL GUI
############################################################

if not args.headless:
	class GUI(tkinter.Frame):
		def client_exit(self, root):
			root.destroy()

		def addBox(self, frame):
			# I use len(all_entries) to get number of next free row
			next_row = len(self.all_m3u8)+4+len(self.all_tuners)+len(self.all_xml)


			self.labelM3u8 = tkinter.StringVar()
			self.labelM3u8.set("m3u8 url")
			labelM3u8 = tkinter.Label(frame, textvariable=self.labelM3u8, height=2)
			labelM3u8.grid(row=next_row+1, column=1)
			#
			userM3u8 = tkinter.StringVar()
			userM3u8.set("www.testurl.com/playlist.m3u8")
			self.m3u8 = tkinter.Entry(frame, textvariable=userM3u8, width=30)
			self.m3u8.grid(row=next_row+1, column=2)

			self.all_m3u8.append(self.m3u8)

			self.labelTuner = tkinter.StringVar()
			self.labelTuner.set("Tuner limit")
			labelTuner = tkinter.Label(frame, textvariable=self.labelTuner, height=2)
			labelTuner.grid(row=next_row+2, column=1)
			#
			userTuner = tkinter.StringVar()
			userTuner.set("6")
			self.Tuner = tkinter.Entry(frame, textvariable=userTuner, width=30)
			self.Tuner.grid(row=next_row+2, column=2)

			self.all_tuners.append(self.Tuner)

			self.labelXml = tkinter.StringVar()
			self.labelXml.set("xmltv url")
			labelXml = tkinter.Label(frame, textvariable=self.labelXml, height=2)
			labelXml.grid(row=next_row+3, column=1)
			#
			userXml = tkinter.StringVar()
			userXml.set("www.testurl.com/epg.xml")
			self.xml = tkinter.Entry(frame, textvariable=userXml, width=30)
			self.xml.grid(row=next_row+3, column=2)
			#
			self.noteXml = tkinter.StringVar()
			self.noteXml.set("One xml can serve multiple m3u8s (channels are linked using tvg-id) separate using a ;")
			noteXml = tkinter.Label(frame, textvariable=self.noteXml, height=2)
			noteXml.grid(row=next_row+3, column=3)

			self.all_xml.append(self.xml)

		# ------------------------------------

		def __init__(self, master):
			self.all_m3u8 = []
			self.all_tuners = []
			self.all_xml = []
			tkinter.Frame.__init__(self, master)
			self.labelText = tkinter.StringVar()
			self.labelText.set("Initial Setup")
			label1 = tkinter.Label(master, textvariable=self.labelText, height=2)
			label1.grid(row=1, column=2)

			self.noteText = tkinter.StringVar()
			self.noteText.set("Notes")
			noteText = tkinter.Label(master, textvariable=self.noteText, height=2)
			noteText.grid(row=1, column=3)

			if platform.system() == 'Windows':
				self.labelFfmpeg = tkinter.StringVar()
				self.labelFfmpeg.set("FFMPEG Location")
				labelFfmpeg = tkinter.Label(master, textvariable=self.labelFfmpeg, height=2)
				labelFfmpeg.grid(row=2, column=1)

				userFfmpeg = tkinter.StringVar()
				userFfmpeg.set('C:\\ffmpeg\\bin\\ffmpeg.exe')
				self.ffmpeg = tkinter.Entry(master, textvariable=userFfmpeg, width=30)
				self.ffmpeg.grid(row=2, column=2)

				self.noteFfmpeg = tkinter.StringVar()
				self.noteFfmpeg.set("Full path to ffmpeg executable")
				noteFfmpeg = tkinter.Label(master, textvariable=self.noteFfmpeg, height=2)
				noteFfmpeg.grid(row=2, column=3)

			self.labelIP = tkinter.StringVar()
			self.labelIP.set("Listen IP")
			labelIP = tkinter.Label(master, textvariable=self.labelIP, height=2)
			labelIP.grid(row=3, column=1)

			userIP = tkinter.StringVar()
			userIP.set(LISTEN_IP)
			self.ip = tkinter.Entry(master, textvariable=userIP, width=30)
			self.ip.grid(row=3, column=2)

			self.noteIP = tkinter.StringVar()
			self.noteIP.set("If using on other machines then set a static IP and use that.")
			noteIP = tkinter.Label(master, textvariable=self.noteIP, height=2)
			noteIP.grid(row=3, column=3)

			self.labelPort = tkinter.StringVar()
			self.labelPort.set("Listen Port")
			labelPort = tkinter.Label(master, textvariable=self.labelPort, height=2)
			labelPort.grid(row=4, column=1)

			userPort = tkinter.IntVar()
			userPort.set(LISTEN_PORT)
			self.port = tkinter.Entry(master, textvariable=userPort, width=30)
			self.port.grid(row=4, column=2)

			self.notePort = tkinter.StringVar()
			self.notePort.set("If 80 doesn't work try 5004 (ports under 1024 require elevation in Unix)")
			notePort = tkinter.Label(master, textvariable=self.notePort, height=2)
			notePort.grid(row=4, column=3)

			self.addBox(frame=master)

			addboxButton = tkinter.Button(master, text='Add another source', command=lambda: self.addBox(frame=master))
			addboxButton.grid(row=99, column=2)

			def gather():
				config = {}
				config["m3u8url"] = ";".join([ent.get() for number, ent in enumerate(self.all_m3u8)])
				config["tunerlimits"] = ";".join([ent.get() for number, ent in enumerate(self.all_tuners)])
				config["xmlurl"] = ";".join([ent.get() for number, ent in enumerate(self.all_xml)])
				if platform.system() == 'Windows':
					config["ffmpegloc"] = userFfmpeg.get()
				config["ip"] = userIP.get()
				config["port"] = userPort.get()
				for widget in master.winfo_children():
					widget.destroy()
				global LISTEN_IP, LISTEN_PORT, SERVER_HOST, XMLURL, M3U8URL, FFMPEGLOC, TUNERLIMITS
				with open('./proxysettings.json', 'w') as fp:
					dump(config, fp)

				LISTEN_IP = config["ip"]
				LISTEN_PORT = config["port"]
				SERVER_HOST = "http://" + LISTEN_IP + ":" + str(LISTEN_PORT)
				XMLURL = config["xmlurl"]
				M3U8URL = config["m3u8url"]
				if platform.system() == 'Windows':
					FFMPEGLOC = config["ffmpegloc"]
				TUNERLIMITS = config["tunerlimits"].split(';')


				button1 = tkinter.Button(master, text="Launch!!", width=20,
										 command=lambda: self.client_exit(master))
				button1.grid(row=1)

			button1 = tkinter.Button(master, text="Submit", width=20, command=lambda: gather())
			button1.grid(row=100, column=2)


############################################################
# MISC Functions
############################################################

def find_between(s, first, last):
	try:
		start = s.index(first) + len(first)
		end = s.index(last, start)
		return s[start:end]
	except ValueError:
		return ""


def thread_updater():
	while True:
		time.sleep(21600)
		if __version__ < latest_ver:
			logger.info(
				"Your version (%s%s) is out of date, the latest is %s, which has now be downloaded for you into the 'updates' subdirectory." % (
					type, __version__, latest_ver))
			newfilename = ntpath.basename(latestfile)
			if not os.path.isdir('updates'):
				os.mkdir('updates')
			requests.urlretrieve(latestfile, os.path.join('updates', newfilename))

			
############################################################
# playlist tools
############################################################

def build_channel_map():
	obtain_m3u8()
	logger.debug("Loading channel list")
	return

def build_playlist(SERVER_HOST):
	return True

def thread_playlist():
	global playlist

	while True:
		time.sleep(86400)
		logger.info("Updating playlist...")
		try:
			tmp_playlist = build_playlist(SERVER_HOST)
			playlist = tmp_playlist
			logger.info("Updated playlist!")
		except:
			logger.exception("Exception while updating playlist: ")



############################################################
# merging tools
############################################################

def obtain_m3u8():
	global m3u8_playlist, chan_map, temp_chan_map
	try:
		with open('./cache/channels.json', 'rb') as f:
			chan_map = pickle.load(f)
	except:
		logger.debug('Loading of archive failed')
		chan_map = {'0': {}}
	m3u8_playlist = ''
	urlstring = M3U8URL
	temp_chan_map = {'0': {}}
	urlstring = urlstring.split(';')
	m3u8_number = 0
	for url in urlstring:
		m3u8_number+=1
		m3u8_merger(url, str(m3u8_number))
	chan_map = temp_chan_map
	with open('./cache/channels.json', 'wb') as f:
		pickle.dump(chan_map, f)


		
def m3u8_merger(url, m3u8_number):
	global chan_map, m3u8_playlist, group_list, temp_chan_map
	if url != '':
		if url.startswith('http'):
			logger.debug("m3u8 url")
			inputm3u8 = requests.urlopen(url).read().decode('utf-8')
			inputm3u8 = inputm3u8.split("\n")[1:]
		else:
			logger.debug("m3u8 file")
			f = open(url, 'r')
			inputm3u8 = f.readlines()
			inputm3u8 = inputm3u8[1:]
			inputm3u8 = [x.strip("\n") for x in inputm3u8]
	else:
		logger.debug("extra m3u8 nothing")
		return
	inputm3u8 = [x for x in inputm3u8 if (x != '' and x != '\n')]
	count = len(temp_chan_map['0'])
	temp_chan_map[m3u8_number] = {}
	for i in range(len(inputm3u8)):
		if inputm3u8[i] != "" or inputm3u8[i] != "\n":
			try:
				if inputm3u8[i].startswith("#"):
					retVal = channelinfo()
					count+=1
					grouper = inputm3u8[i]
					grouper = grouper.split(',')
					retVal.channame = grouper[1]
					retVal.epg = find_between(grouper[0], 'tvg-id="', '"')
					retVal.icon = find_between(grouper[0],'tvg-logo="','"')
					retVal.group = find_between(grouper[0],'group-title="','"')
					if not retVal.group.lower() in group_list:
						group_list[retVal.group.lower()] = True
					retVal.language = find_between(grouper[0],'language="','"')
					if not retVal.language.lower() in language_list and retVal.language != '':
						language_list[retVal.language.lower()] = True
						# print(m3u8_number,retVal.channame)
					retVal.playlist = m3u8_number
					grouper = grouper[0] + ' channel-id="%s", %s' % (count, grouper[1])

					m3u8_playlist += grouper + "\n"
					retVal.url = inputm3u8[i+1].strip()
					retVal.channum = count  # int(find_between(meta[0],'channel-id="','"'))
					retVal.active = True
					for value in chan_map['0'].values():
						if value.epg == retVal.epg:
							retVal.active = value.active
							if not retVal.active:
								logger.debug('Channel %s/%s is disabled by user.' % (retVal.channum, retVal.channame))
							break
					temp_chan_map['0'][count] = {}
					temp_chan_map['0'][count] = retVal

					temp_chan_map[m3u8_number][count] = {}
					temp_chan_map[m3u8_number][count] = retVal
				else:
					m3u8_playlist += inputm3u8[i] + "\n"


			except:
				logger.debug("skipped line %s in m3u8 %s due to: %s" %(i, m3u8_number, inputm3u8[i]))
	# formatted_m3u8 = formatted_m3u8.replace("\n\n","\n")


def epg_status():
	if os.path.isfile('./cache/combined.xml'):
		existing = './cache/combined.xml'
		cur_utc_hr = datetime.utcnow().replace(microsecond=0, second=0, minute=0).hour
		target_utc_hr = (cur_utc_hr // 3) * 3
		target_utc_datetime = datetime.utcnow().replace(microsecond=0, second=0, minute=0, hour=target_utc_hr)
		logger.debug("utc time is: %s,    utc target time is: %s,    file time is: %s" % (
		datetime.utcnow(), target_utc_datetime, datetime.utcfromtimestamp(os.stat(existing).st_mtime)))
		if os.path.isfile(existing) and os.stat(existing).st_mtime > target_utc_datetime.timestamp():
			logger.debug("Skipping download of epg")
			return
	obtain_epg()
	
def obtain_epg():
	#clear epg file
	f = open('./cache/epg.xml','w')
	f.write('<?xml version="1.0" encoding="UTF-8"?>'.rstrip('\r\n'))
	f.write('''<tv></tv>''')
	f.close()
	list_of_xmltv = XMLURL.split(';')
	for i in list_of_xmltv:
		if i != '' and i != 'www.testurl.com/epg.xml':
			xmltv_merger(i)

def xmltv_merger(xml_url):
	#todo download each xmltv
	if xml_url.endswith('.gz'):
		requests.urlretrieve(xml_url, './cache/raw.xml.gz')
		opened = gzip.open('./cache/raw.xml.gz')
	else:
		requests.urlretrieve(xml_url, './cache/raw.xml')
		opened = open('./cache/raw.xml', encoding="UTF-8")


	tree = ET.parse('./cache/epg.xml')
	treeroot = tree.getroot()

	source = ET.parse(opened)
	
	for channel in source.iter('channel'):
		treeroot.append(channel)
		
	for programme in source.iter('programme'):
		treeroot.append(programme)
		
	tree.write('./cache/epg.xml')
	with open('./cache/epg.xml', 'r+') as f:
		content = f.read()
		f.seek(0, 0)
		f.write('<?xml version="1.0" encoding="UTF-8"?>'.rstrip('\r\n') + content)
	return



############################################################
# PLEX Live
############################################################

def discover(tunerLimit=6,tunerNumber=""):
	discoverData = {
		'FriendlyName': 'iptv4plex%s' % tunerNumber,
		'Manufacturer': 'Silicondust',
		'ModelNumber': 'HDTC-2US',
		'FirmwareName': 'hdhomeruntc_atsc',
		'TunerCount': tunerLimit,
		'FirmwareVersion': '20150826',
		'DeviceID': '12345678%s' % tunerNumber,
		'DeviceAuth': 'test1234%s' % tunerNumber,
		'BaseURL': SERVER_HOST if tunerNumber == "" else SERVER_HOST + '/' + tunerNumber,
		'LineupURL': '%s/lineup.json' % (SERVER_HOST if tunerNumber == "" else SERVER_HOST + '/' + tunerNumber)
	}
	return jsonify(discoverData)


def status():
	return jsonify({
		'ScanInProgress': 0,
		'ScanPossible': 1,
		'Source': "Cable",
		'SourceList': ['Cable']
	})


def lineup(tuner='0'):
	global chan_map
	lineup = []
	for c in chan_map[tuner]:
		template = "{0}/auto/v{1}"
		url = template.format(SERVER_HOST, chan_map[tuner][c].channum)
		if chan_map[tuner][c].active:
			lineup.append({'GuideNumber': str(chan_map[tuner][c].channum),
						   'GuideName': chan_map[tuner][c].channame,
						   'URL': url
						   })

	return jsonify(lineup)

def lineup_post():
	return ''


def device(tunerLimit=6, tunerNumber=""):
	discoverData = {
		'FriendlyName': 'iptv4plex%s' % tunerNumber,
		'Manufacturer': 'Silicondust',
		'ModelNumber': 'HDTC-2US',
		'FirmwareName': 'hdhomeruntc_atsc',
		'TunerCount': tunerLimit,
		'FirmwareVersion': '20150826',
		'DeviceID': '12345678%s' % tunerNumber,
		'DeviceAuth': 'test1234%s' % tunerNumber,
		'BaseURL': SERVER_HOST if tunerNumber == "" else SERVER_HOST + '/' + tunerNumber,
		'LineupURL': '%s/lineup.json' % (SERVER_HOST if tunerNumber == "" else SERVER_HOST + '/' + tunerNumber)
	}
	return render_template('device.xml', data=discoverData), {'Content-Type': 'application/xml'}


############################################################
# Html
############################################################


# Change this to change the style of the web page generated
style = """
<style type="text/css">
	body { background: white url("") no-repeat fixed center center; background-size: 500px 500px; color: black; }
	h1 { color: white; background-color: black; padding: 0.5ex }
	h2 { color: white; background-color: black; padding: 0.3ex }
	.container {display: table; width: 100%;}
	.left-half {position: absolute;  left: 0px;  width: 50%;}
	.right-half {position: absolute;  right: 0px;  width: 50%;}
</style>
"""


def create_menu():
	footer = '<p>Donations: PayPal to vorghahn.sstv@gmail.com  or BTC - 19qvdk7JYgFruie73jE4VvW7ZJBv8uGtFb</p>'

	with open("./cache/channels.html", "w") as html:
		global chan_map
		html.write("""<html><head><title>iptv4plex</title><meta charset="UTF-8">%s</head><body>\n""" % (style,))
		html.write('<form action = "/channels.html" method = "post"><input type="submit" name="reset" value="Reset channel settings" /></form>')
		html.write('<section class="container"><h1>Group List</h1><div><form action="/channels.html" method="post"><table width="300" border="1"><tr><th>Active</th><th>Group</th></tr>')
		template = "<td> <input type='checkbox' name='group' value='{0}'{1}></td><td>{0}<br></td>"
		for group in group_list:
			html.write("<tr>")
			html.write(template.format(group.capitalize(), 'checked' if group_list[group] else ''))
			html.write("</tr>")
		html.write("</table><input type='submit' value='Submit'></form>")
		html.write("</div>")
		if len(language_list) > 1:
			html.write('<h1>Language List</h1><div><form action="/channels.html" method="post"><table width="300" border="1"><tr><th>Active</th><th>Language</th></tr>')
			template = "<td> <input type='checkbox' name='language' value='{0}'{1}></td><td>{0}<br></td>"
			for language in language_list:
				html.write("<tr>")
				html.write(template.format(language.capitalize(), 'checked' if language_list[language] else ''))
				html.write("</tr>")
			html.write("</table><input type='submit' value='Submit'></form>")
			html.write("</div>")
		html.write("<h1>Channel List</h1>")
		html.write('<div><form action="/channels.html" method="post"><table width="300" border="1"><tr><th>#</th><th>Active</th><th>Icon</th><th>#</th><th>Active</th><th>Icon</th><th>#</th><th>Active</th><th>Icon</th></tr>')
		template = "<td>{0}</td><td> <input type='checkbox' name='channel' value='{1}' {5}><br></td><td><a href='{2}'><img src='{3}' height='83' width='270' alt='{4}'></a></td></td>"
		for i in chan_map['0']:
			if i%3 == 1:
				html.write("<tr>")
			html.write(template.format(chan_map['0'][i].channum, chan_map['0'][i].channum, chan_map['0'][i].url,chan_map['0'][i].icon, chan_map['0'][i].channame, 'checked' if chan_map['0'][i].active else ''))
			if i%3 == 0:
				html.write("</tr>")
		html.write("</table><input type='submit' value='Submit'></form>")
		html.write("</br>%s</div>" % footer)
		html.write("</section>")
		html.write("</body></html>\n")

############################################################
# Flask Routes
############################################################
@app.route('/<tuner>/<request_file>')
def sub_tuners(tuner, request_file):
	try:
		t_limit = TUNERLIMITS[int(tuner)-1]
		if int(tuner) == 0:
			t_limit = 6
	except:
		t_limit = 6
		logger.info("Setting tuner limits failed, using 6")
	logger.info("%s/%s was requested by %s" % (tuner, request_file, request.environ.get('REMOTE_ADDR')))
	if request_file.lower() == 'lineup_status.json':
		return status()
	elif request_file.lower() == 'discover.json':
		return discover(t_limit,tuner)
	elif request_file.lower() == 'lineup.json':
		return lineup(tuner)
	elif request_file.lower() == 'lineup.post':
		return lineup_post()
	elif request_file.lower() == 'device.xml':
		return device(t_limit,tuner)
	else:
		logger.info("Unknown requested %s/%s by %s (tuner 404)", tuner, request_file, request.environ.get('REMOTE_ADDR'))
		abort(404, "Unknown request")

# web page
@app.route('/', methods=['GET','POST'])
@app.route('/channels.html', methods=['GET','POST'])
def web_page():
	if request.form:
		global chan_map
		inc_data = dict(request.form)

		for playlist in chan_map:
			for channel in chan_map[playlist]:
				if ('channel' in inc_data and str(channel) not in inc_data['channel']) or ('group' in inc_data and chan_map[playlist][channel].group.capitalize() not in inc_data['group']) or ('language' in inc_data and chan_map[playlist][channel].language.capitalize() not in inc_data['language']):
					chan_map[playlist][channel].active = False
					logger.debug("disabling: %s" % channel)
				else:
					chan_map[playlist][channel].active = True
		if 'group' in inc_data:
			for grp in group_list:
				if grp.capitalize() not in inc_data['group']:
					group_list[grp] = False
		if 'language' in inc_data:
			for lang in language_list:
				if lang.capitalize() not in inc_data['language']:
					language_list[lang] = False
		if 'reset' in inc_data:
			for playlist in chan_map:
				for channel in chan_map[playlist]:
					chan_map[playlist][channel].active = True
			for grp in group_list:
				group_list[grp] = True
			for lang in language_list:
				language_list[lang] = True

		with open('./cache/channels.json', 'wb') as f:
			pickle.dump(chan_map, f)
	create_menu()
	return send_from_directory('./cache','channels.html')

@app.route('/<request_file>', methods=['GET','POST'])
def main_tuner(request_file):
	logger.info("%s was requested by %s" % (request_file, request.environ.get('REMOTE_ADDR')))
	# return epg
	if request_file.lower().startswith('epg.'):
		logger.info("EPG was requested by %s", request.environ.get('REMOTE_ADDR'))
		obtain_epg()
		# with open('./cache/epg.xml'), 'r+') as f:
		# 	content = f.read()
		# response = Response(content, mimetype='text/xml')
		# headers = dict(response.headers)
		# headers.update(
		# 	{"Access-Control-Expose-Headers": "Accept-Ranges, Content-Encoding, Content-Length, Content-Range",
		# 	 "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "Range",
		# 	 "Access-Control-Allow-Methods": "GET, POST, OPTIONS, HEAD"})
		# response.headers = headers
		# return response

		return send_from_directory('./cache', 'epg.xml')

	# Icon for the favourites menu and browser tab
	elif request_file.lower() == 'favicon.ico':
		return redirect("https://assets.materialup.com/uploads/57194301-5bfe-4b2c-9f17-1c1de930c496/avatar.png", 302)

	elif request_file.lower() == 'playlist.m3u8':
		obtain_m3u8()
		logger.info("All channels playlist was requested by %s", request.environ.get('REMOTE_ADDR'))
		output = '#EXTM3U\n' + m3u8_playlist
		return Response(output, mimetype='application/x-mpegURL')



	# HDHomeRun emulated json files for Plex Live tv.
	elif request_file.lower() == 'lineup_status.json':
		return status()
	elif request_file.lower() == 'discover.json':
		return discover()
	elif request_file.lower() == 'lineup.json':
		return lineup()
	elif request_file.lower() == 'lineup.post':
		return lineup_post()
	elif request_file.lower() == 'device.xml':
		return device()
	else:
		logger.info("Unknown requested %r by %s (main 404)", request_file, request.environ.get('REMOTE_ADDR'))
		abort(404, "Unknown request")

@app.route('/auto/<request_file>')
# returns a piped stream, used for TVH/Plex Live TV
def auto(request_file):
	global chan_map
	logger.debug("starting pipe function")
	channel = int(request_file.replace("v", ""))
	logger.info("Channel %s playlist was requested by %s", channel,
				request.environ.get('REMOTE_ADDR'))

	url = chan_map['0'][channel].url
	if request.args.get('url'):
		logger.info("Piping custom URL")
		url = request.args.get('url')
		if '|' in url:
			url = url.split('|')[0]
	logger.debug(url)
	import subprocess

	def generate():
		logger.debug("starting generate function")
		cmdline = list()
		cmdline.append(FFMPEGLOC)
		cmdline.append("-i")
		cmdline.append(url)
		cmdline.append("-vcodec")
		cmdline.append("copy")
		cmdline.append("-acodec")
		cmdline.append("copy")
		cmdline.append("-f")
		cmdline.append("mpegts")
		cmdline.append("pipe:1")
		logger.debug(cmdline)
		FNULL = open(os.devnull, 'w')
		proc = subprocess.Popen(cmdline, stdout=subprocess.PIPE, stderr=FNULL)
		logger.debug("pipe started")
		try:
			f = proc.stdout
			byte = f.read(512)
			while byte:
				yield byte
				byte = f.read(512)

		finally:
			proc.kill()

	return Response(response=generate(), status=200, mimetype='video/mp2t',
					headers={'Access-Control-Allow-Origin': '*', "Content-Type": "video/mp2t",
							 "Content-Disposition": "inline", "Content-Transfer-Enconding": "binary"})


############################################################
# MAIN
############################################################


if __name__ == "__main__":
	logger.info("Initializing")
	load_settings()

	logger.info("Building initial playlist...")
	try:
		obtain_epg()
		build_channel_map()

	except:
		logger.exception("Exception while building initial playlist: ")
		exit(1)

	try:
		thread.start_new_thread(thread_playlist, ())
	except:
		_thread.start_new_thread(thread_playlist, ())

	print("\n##############################################################")
	print("Channels menu is %s" % SERVER_HOST)
	print("Combined m3u8 url is %s/playlist.m3u8" % SERVER_HOST)
	print("EPG url is %s/epg.xml" % SERVER_HOST)
	print("Plex Live TV combined url is %s" % SERVER_HOST)
	for i in M3U8URL.split(";"):
		print("Plex Live TV single tuner url for %s is %s/%s" % (i, SERVER_HOST, M3U8URL.split(";").index(i)+1))
	print("Donations: PayPal to vorghahn.sstv@gmail.com  or BTC - 19qvdk7JYgFruie73jE4VvW7ZJBv8uGtFb")
	print("##############################################################\n")

	if __version__ < latest_ver:
		logger.info(
			"Your version (%s%s) is out of date, the latest is %s, which has now be downloaded for you into the 'updates' subdirectory." % (
			type, __version__, latest_ver))
		newfilename = ntpath.basename(latestfile)
		if not os.path.isdir('updates'):
			os.mkdir('updates')
		requests.urlretrieve(latestfile, os.path.join('./updates', newfilename))
	else:
		logger.info("Your version (%s) is up to date." % (__version__))
	logger.info("Listening on %s:%d at %s/", LISTEN_IP, LISTEN_PORT, SERVER_HOST)
	try:
		a = threading.Thread(target=thread_updater)
		a.setDaemon(True)
		a.start()
	except (KeyboardInterrupt, SystemExit):
		sys.exit()

	# debug causes it to load twice on initial startup and every time the script is saved, TODO disbale later
	try:
		app.run(host=LISTEN_IP, port=LISTEN_PORT, threaded=True, debug=False)
	except:
		os.system('cls' if os.name == 'nt' else 'clear')
		logger.exception("Proxy failed to launch, try another port")
	logger.info("Finished!")
