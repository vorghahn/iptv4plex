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
import socket
import struct
import array
from io import StringIO

try:
	import tkinter
	HEADLESS = False
except:
	HEADLESS = True
if 'headless' in sys.argv:
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

__version__ = 0.1
# Changelog
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
NETDISCOVER = True
ignorelist = []  # the tvheadend ip address(es), tvheadend crashes when it discovers the tvhproxy (TODO: Fix this)

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
	global LISTEN_IP, LISTEN_PORT, SERVER_HOST, M3U8URL, XMLURL, FFMPEGLOC, TUNERLIMITS, NETDISCOVER
	if not os.path.isfile(os.path.join(os.path.dirname(sys.argv[0]), 'proxysettings.json')):
		logger.debug("No config file found.")
	try:
		logger.debug("Parsing settings")
		with open(os.path.join(os.path.dirname(sys.argv[0]), 'proxysettings.json')) as jsonConfig:
			config = {}
			config = load(jsonConfig)
			if "discover" in config:
				NETDISCOVER = config["discover"]
			if "ffmpegloc" in config:
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
			os.system('cls' if os.name == 'nt' else 'clear')
			config["discover"] = True if input("Enable Plex Discovery? Y/N(Do not use if TVHeadend is on your network)").lower() == 'y' else False
			LISTEN_IP = config["ip"]
			LISTEN_PORT = config["port"]
			SERVER_HOST = "http://" + LISTEN_IP + ":" + str(LISTEN_PORT)
			XMLURL = config["xmlurl"]
			M3U8URL = config["m3u8url"]
			if platform.system() == 'Windows':
				FFMPEGLOC = config["ffmpegloc"]
			NETDISCOVER = config["discover"]
			TUNERLIMITS = config["tunerlimits"].split(';')
			with open(os.path.join(os.path.dirname(sys.argv[0]), 'proxysettings.json'), 'w') as fp:
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
if "-d" in sys.argv:
	console_handler.setLevel(logging.DEBUG)
else:
	console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)

# Rotating Log Files
if not os.path.isdir(os.path.join(os.path.dirname(sys.argv[0]), 'cache')):
	os.mkdir(os.path.join(os.path.dirname(sys.argv[0]), 'cache'))
file_handler = RotatingFileHandler(os.path.join(os.path.dirname(sys.argv[0]), 'cache', 'status.log'),
								   maxBytes=1024 * 1024 * 2,
								   backupCount=5)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(log_formatter)
logger.addHandler(file_handler)


############################################################
# INSTALL
############################################################

def installer():
	writetemplate()

def writetemplate():
	if not os.path.isdir(os.path.join(os.path.dirname(sys.argv[0]), 'Templates')):
		os.mkdir(os.path.join(os.path.dirname(sys.argv[0]), 'Templates'))
	f = open(os.path.join(os.path.dirname(sys.argv[0]), 'Templates', 'device.xml'), 'w')
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

if not 'headless' in sys.argv:
	class GUI(tkinter.Frame):
		def client_exit(self, root):
			root.destroy()

		def addBox(self, frame):
			# I use len(all_entries) to get number of next free row
			next_row = len(self.all_m3u8)+5+len(self.all_tuners)+len(self.all_xml)


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

			self.labelDiscover = tkinter.StringVar()
			self.labelDiscover.set("Automatic Plex Discovery")
			labelDiscover = tkinter.Label(master, textvariable=self.labelDiscover, height=2)
			labelDiscover.grid(row=5, column=1)

			userDiscover = tkinter.StringVar()
			userDiscover.set("Yes")
			opts = ["No", "Yes"]
			self.Discover = tkinter.OptionMenu(master, userDiscover, *[x for x in opts])
			self.Discover.grid(row=5, column=2)

			self.noteDiscover = tkinter.StringVar()
			self.noteDiscover.set("Do not use if TVHeadend is on your network)")
			noteDiscover = tkinter.Label(master, textvariable=self.noteDiscover, height=2)
			noteDiscover.grid(row=5, column=3)

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
				disc = userDiscover.get()
				config["discover"] = True if disc == "Yes" else False
				for widget in master.winfo_children():
					widget.destroy()
				global LISTEN_IP, LISTEN_PORT, SERVER_HOST, XMLURL, M3U8URL, FFMPEGLOC, TUNERLIMITS, NETDISCOVER
				with open(os.path.join(os.path.dirname(sys.argv[0]), 'proxysettings.json'), 'w') as fp:
					dump(config, fp)

				LISTEN_IP = config["ip"]
				LISTEN_PORT = config["port"]
				SERVER_HOST = "http://" + LISTEN_IP + ":" + str(LISTEN_PORT)
				XMLURL = config["xmlurl"]
				M3U8URL = config["m3u8url"]
				if platform.system() == 'Windows':
					FFMPEGLOC = config["ffmpegloc"]
				TUNERLIMITS = config["tunerlimits"].split(';')
				NETDISCOVER = config["discover"]


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
			if not os.path.isdir(os.path.join(os.path.dirname(sys.argv[0]), 'updates')):
				os.mkdir(os.path.join(os.path.dirname(sys.argv[0]), 'updates'))
			requests.urlretrieve(latestfile, os.path.join(os.path.dirname(sys.argv[0]), 'updates', newfilename))


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
		print('archive failed')
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
			# try:
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
					print(m3u8_number,retVal.channame)
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


			# except:
			# 	logger.debug("skipped:", inputm3u8[i])
	# formatted_m3u8 = formatted_m3u8.replace("\n\n","\n")


def epg_status():
	if os.path.isfile(os.path.join(os.path.dirname(sys.argv[0]), 'cache', 'combined.xml')):
		existing = os.path.join(os.path.dirname(sys.argv[0]), 'cache', 'combined.xml')
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
	requests.urlretrieve(xml_url, './cache/raw.xml')
	#master = ET.Element('tv')
	#mtree = ET.ElementTree(master)
	#mroot = mtree.getroot()

	tree = ET.parse('./cache/epg.xml')
	treeroot = tree.getroot()

	source = ET.parse('./cache/raw.xml')

	for channel in source.iter('channel'):
		treeroot.append(channel)

	for programme in source.iter('programme'):
		treeroot.append(programme)

	tree.write(os.path.join(os.path.dirname(sys.argv[0]), 'cache', 'epg.xml'))
	with open(os.path.join(os.path.dirname(sys.argv[0]), 'cache', 'epg.xml'), 'r+') as f:
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
# PLEX Discovery
############################################################

crc32c_table = (
	0x00000000, 0x77073096, 0xee0e612c, 0x990951ba,
	0x076dc419, 0x706af48f, 0xe963a535, 0x9e6495a3,
	0x0edb8832, 0x79dcb8a4, 0xe0d5e91e, 0x97d2d988,
	0x09b64c2b, 0x7eb17cbd, 0xe7b82d07, 0x90bf1d91,
	0x1db71064, 0x6ab020f2, 0xf3b97148, 0x84be41de,
	0x1adad47d, 0x6ddde4eb, 0xf4d4b551, 0x83d385c7,
	0x136c9856, 0x646ba8c0, 0xfd62f97a, 0x8a65c9ec,
	0x14015c4f, 0x63066cd9, 0xfa0f3d63, 0x8d080df5,
	0x3b6e20c8, 0x4c69105e, 0xd56041e4, 0xa2677172,
	0x3c03e4d1, 0x4b04d447, 0xd20d85fd, 0xa50ab56b,
	0x35b5a8fa, 0x42b2986c, 0xdbbbc9d6, 0xacbcf940,
	0x32d86ce3, 0x45df5c75, 0xdcd60dcf, 0xabd13d59,
	0x26d930ac, 0x51de003a, 0xc8d75180, 0xbfd06116,
	0x21b4f4b5, 0x56b3c423, 0xcfba9599, 0xb8bda50f,
	0x2802b89e, 0x5f058808, 0xc60cd9b2, 0xb10be924,
	0x2f6f7c87, 0x58684c11, 0xc1611dab, 0xb6662d3d,
	0x76dc4190, 0x01db7106, 0x98d220bc, 0xefd5102a,
	0x71b18589, 0x06b6b51f, 0x9fbfe4a5, 0xe8b8d433,
	0x7807c9a2, 0x0f00f934, 0x9609a88e, 0xe10e9818,
	0x7f6a0dbb, 0x086d3d2d, 0x91646c97, 0xe6635c01,
	0x6b6b51f4, 0x1c6c6162, 0x856530d8, 0xf262004e,
	0x6c0695ed, 0x1b01a57b, 0x8208f4c1, 0xf50fc457,
	0x65b0d9c6, 0x12b7e950, 0x8bbeb8ea, 0xfcb9887c,
	0x62dd1ddf, 0x15da2d49, 0x8cd37cf3, 0xfbd44c65,
	0x4db26158, 0x3ab551ce, 0xa3bc0074, 0xd4bb30e2,
	0x4adfa541, 0x3dd895d7, 0xa4d1c46d, 0xd3d6f4fb,
	0x4369e96a, 0x346ed9fc, 0xad678846, 0xda60b8d0,
	0x44042d73, 0x33031de5, 0xaa0a4c5f, 0xdd0d7cc9,
	0x5005713c, 0x270241aa, 0xbe0b1010, 0xc90c2086,
	0x5768b525, 0x206f85b3, 0xb966d409, 0xce61e49f,
	0x5edef90e, 0x29d9c998, 0xb0d09822, 0xc7d7a8b4,
	0x59b33d17, 0x2eb40d81, 0xb7bd5c3b, 0xc0ba6cad,
	0xedb88320, 0x9abfb3b6, 0x03b6e20c, 0x74b1d29a,
	0xead54739, 0x9dd277af, 0x04db2615, 0x73dc1683,
	0xe3630b12, 0x94643b84, 0x0d6d6a3e, 0x7a6a5aa8,
	0xe40ecf0b, 0x9309ff9d, 0x0a00ae27, 0x7d079eb1,
	0xf00f9344, 0x8708a3d2, 0x1e01f268, 0x6906c2fe,
	0xf762575d, 0x806567cb, 0x196c3671, 0x6e6b06e7,
	0xfed41b76, 0x89d32be0, 0x10da7a5a, 0x67dd4acc,
	0xf9b9df6f, 0x8ebeeff9, 0x17b7be43, 0x60b08ed5,
	0xd6d6a3e8, 0xa1d1937e, 0x38d8c2c4, 0x4fdff252,
	0xd1bb67f1, 0xa6bc5767, 0x3fb506dd, 0x48b2364b,
	0xd80d2bda, 0xaf0a1b4c, 0x36034af6, 0x41047a60,
	0xdf60efc3, 0xa867df55, 0x316e8eef, 0x4669be79,
	0xcb61b38c, 0xbc66831a, 0x256fd2a0, 0x5268e236,
	0xcc0c7795, 0xbb0b4703, 0x220216b9, 0x5505262f,
	0xc5ba3bbe, 0xb2bd0b28, 0x2bb45a92, 0x5cb36a04,
	0xc2d7ffa7, 0xb5d0cf31, 0x2cd99e8b, 0x5bdeae1d,
	0x9b64c2b0, 0xec63f226, 0x756aa39c, 0x026d930a,
	0x9c0906a9, 0xeb0e363f, 0x72076785, 0x05005713,
	0x95bf4a82, 0xe2b87a14, 0x7bb12bae, 0x0cb61b38,
	0x92d28e9b, 0xe5d5be0d, 0x7cdcefb7, 0x0bdbdf21,
	0x86d3d2d4, 0xf1d4e242, 0x68ddb3f8, 0x1fda836e,
	0x81be16cd, 0xf6b9265b, 0x6fb077e1, 0x18b74777,
	0x88085ae6, 0xff0f6a70, 0x66063bca, 0x11010b5c,
	0x8f659eff, 0xf862ae69, 0x616bffd3, 0x166ccf45,
	0xa00ae278, 0xd70dd2ee, 0x4e048354, 0x3903b3c2,
	0xa7672661, 0xd06016f7, 0x4969474d, 0x3e6e77db,
	0xaed16a4a, 0xd9d65adc, 0x40df0b66, 0x37d83bf0,
	0xa9bcae53, 0xdebb9ec5, 0x47b2cf7f, 0x30b5ffe9,
	0xbdbdf21c, 0xcabac28a, 0x53b39330, 0x24b4a3a6,
	0xbad03605, 0xcdd70693, 0x54de5729, 0x23d967bf,
	0xb3667a2e, 0xc4614ab8, 0x5d681b02, 0x2a6f2b94,
	0xb40bbe37, 0xc30c8ea1, 0x5a05df1b, 0x2d02ef8d,
)


def add(crc, buf):
	buf = array.array('B', buf)
	for b in buf:
		crc = (crc >> 8) ^ crc32c_table[(crc ^ b) & 0xff]
	return crc


def done(crc):
	tmp = ~crc & 0xffffffff
	b0 = tmp & 0xff
	b1 = (tmp >> 8) & 0xff
	b2 = (tmp >> 16) & 0xff
	b3 = (tmp >> 24) & 0xff
	crc = (b0 << 24) | (b1 << 16) | (b2 << 8) | b3
	return crc


def cksum(buf):
	"""Return computed CRC-32c checksum."""
	return done(add(0xffffffff, buf))

HDHOMERUN_DISCOVER_UDP_PORT = 65001
HDHOMERUN_CONTROL_TCP_PORT = 65001
HDHOMERUN_MAX_PACKET_SIZE = 1460
HDHOMERUN_MAX_PAYLOAD_SIZE = 1452

HDHOMERUN_TYPE_DISCOVER_REQ = 0x0002
HDHOMERUN_TYPE_DISCOVER_RPY = 0x0003
HDHOMERUN_TYPE_GETSET_REQ = 0x0004
HDHOMERUN_TYPE_GETSET_RPY = 0x0005
HDHOMERUN_TAG_DEVICE_TYPE = 0x01
HDHOMERUN_TAG_DEVICE_ID = 0x02
HDHOMERUN_TAG_GETSET_NAME = 0x03
HDHOMERUN_TAG_GETSET_VALUE = 0x04
HDHOMERUN_TAG_GETSET_LOCKKEY = 0x15
HDHOMERUN_TAG_ERROR_MESSAGE = 0x05
HDHOMERUN_TAG_TUNER_COUNT = 0x10
HDHOMERUN_TAG_DEVICE_AUTH_BIN = 0x29
HDHOMERUN_TAG_BASE_URL = 0x2A
HDHOMERUN_TAG_DEVICE_AUTH_STR = 0x2B

HDHOMERUN_DEVICE_TYPE_WILDCARD = 0xFFFFFFFF
HDHOMERUN_DEVICE_TYPE_TUNER = 0x00000001
HDHOMERUN_DEVICE_ID_WILDCARD = 0xFFFFFFFF

def retrieveTypeAndPayload(packet):
	header = packet[:4]
	checksum = packet[-4:]
	payload = packet[4:-4]

	packetType, payloadLength = struct.unpack('>HH', header)
	if payloadLength != len(payload):
		logger.debug('Bad packet payload length')
		return False

	if checksum != struct.pack('>I', cksum(header + payload)):
		logger.debug('Bad checksum')
		return False

	return (packetType, payload)


def createPacket(packetType, payload):
	header = struct.pack('>HH', packetType, len(payload))
	data = header + payload
	checksum = cksum(data)
	packet = data + struct.pack('>I', checksum)

	return packet


def processPacket(packet, client, logPrefix=''):
	packetType, requestPayload = retrieveTypeAndPayload(packet)

	if packetType == HDHOMERUN_TYPE_DISCOVER_REQ:
		logger.debug('Discovery request received from ' + client[0])
		responsePayload = struct.pack('>BBI', HDHOMERUN_TAG_DEVICE_TYPE, 0x04,
		                              HDHOMERUN_DEVICE_TYPE_TUNER)  # Device Type Filter (tuner)
		responsePayload += struct.pack('>BBI', HDHOMERUN_TAG_DEVICE_ID, 0x04,
		                               int('12345678', 16))  # Device ID Filter (any)
		responsePayload += struct.pack('>BB', HDHOMERUN_TAG_GETSET_NAME, len(SERVER_HOST)) + str.encode(
			SERVER_HOST)  # Device ID Filter (any)
		responsePayload += struct.pack('>BBB', HDHOMERUN_TAG_TUNER_COUNT, 0x01, 6)  # Device ID Filter (any)

		return createPacket(HDHOMERUN_TYPE_DISCOVER_RPY, responsePayload)

	# TODO: Implement request types
	if packetType == HDHOMERUN_TYPE_GETSET_REQ:
		logger.debug('Get set request received from ' + client[0])
		getSetName = None
		getSetValue = None
		payloadIO = StringIO(requestPayload)
		while True:
			header = payloadIO.read(2)
			if not header: break
			tag, length = struct.unpack('>BB', header)
			# TODO: If the length is larger than 127 the following bit is also needed to determine length
			if length > 127:
				logger.debug(
					'Unable to determine tag length, the correct way to determine a length larger than 127 must still be implemented.')
				return False
			# TODO: Implement other tags
			if tag == HDHOMERUN_TAG_GETSET_NAME:
				getSetName = struct.unpack('>{0}'.format(length), payloadIO.read(length))[0]
			if tag == HDHOMERUN_TAG_GETSET_VALUE:
				getSetValue = struct.unpack('>{0}'.format(length), payloadIO.read(length))[0]

		if getSetName is None:
			return False
		else:
			responsePayload = struct.pack('>BB{0}'.format(len(getSetName)), HDHOMERUN_TAG_GETSET_NAME, len(getSetName),
			                              getSetName)

			if getSetValue is not None:
				responsePayload += struct.pack('>BB{0}'.format(len(getSetValue)), HDHOMERUN_TAG_GETSET_VALUE,
				                               len(getSetValue), getSetValue)

			return createPacket(HDHOMERUN_TYPE_GETSET_RPY, responsePayload)

	return False


def tcpServer():
	logger.info('Starting tcp server')
	controlSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	controlSocket.bind((LISTEN_IP, HDHOMERUN_CONTROL_TCP_PORT))
	controlSocket.listen(1)

	logger.info('Listening...')
	try:
		while True:
			connection, client = controlSocket.accept()
			try:
				packet = connection.recv(HDHOMERUN_MAX_PACKET_SIZE)
				if not packet:
					logger.debug('No packet received')
					break
				if client[0] not in ignorelist:
					responsePacket = processPacket(packet, client)
					if responsePacket:
						logger.debug('Sending control reply over tcp')
						connection.send(responsePacket)
					else:
						logger.debug('No known control request received, nothing to send to client')
				else:
					logger.debug('Ignoring tcp client %s' % client[0])
			finally:
				connection.close()
	except:
		logger.debug('Exception occured')

	logger.info('Stopping tcp server')
	controlSocket.close()


def udpServer():
	logger.info('Starting udp server')
	discoverySocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	discoverySocket.bind(('0.0.0.0', HDHOMERUN_DISCOVER_UDP_PORT))
	logger.info('Listening...')
	while True:
		packet, client = discoverySocket.recvfrom(HDHOMERUN_MAX_PACKET_SIZE)
		if not packet:
			logger.debug('No packet received')
			break
		if client[0] not in ignorelist:
			responsePacket = processPacket(packet, client)
			if responsePacket:
				logger.debug('Sending discovery reply over udp')
				discoverySocket.sendto(responsePacket, client)
			else:
				logger.debug('No discovery request received, nothing to send to client')
		else:
			logger.debug('Ignoring udp client %s' % client[0])
	logger.info('Stopping udp server')
	discoverySocket.close()

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
				print(lang)
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
		with open(os.path.join(os.path.dirname(sys.argv[0]), 'cache', 'epg.xml'), 'r+') as f:
			content = f.read()
		response = Response(content, mimetype='text/xml')
		headers = dict(response.headers)
		headers.update(
			{"Access-Control-Expose-Headers": "Accept-Ranges, Content-Encoding, Content-Length, Content-Range",
			 "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "Range",
			 "Access-Control-Allow-Methods": "GET, POST, OPTIONS, HEAD"})
		response.headers = headers
		return response

		#xmltv_merger()
		#return send_from_directory(os.path.join(os.path.dirname(sys.argv[0]), 'cache'), 'combined.xml')

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
		if not os.path.isdir(os.path.join(os.path.dirname(sys.argv[0]), 'updates')):
			os.mkdir(os.path.join(os.path.dirname(sys.argv[0]), 'updates'))
		requests.urlretrieve(latestfile, os.path.join(os.path.dirname(sys.argv[0]), 'updates', newfilename))
	else:
		logger.info("Your version (%s) is up to date." % (__version__))
	logger.info("Listening on %s:%d at %s/", LISTEN_IP, LISTEN_PORT, SERVER_HOST)
	try:
		a = threading.Thread(target=thread_updater)
		a.setDaemon(True)
		a.start()
	except (KeyboardInterrupt, SystemExit):
		sys.exit()

	if NETDISCOVER:
		try:
			a = threading.Thread(target=udpServer)
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
