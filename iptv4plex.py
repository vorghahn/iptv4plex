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

__version__ = 0.2
# Changelog
# 0.2 - Added tunerlimits and subnets for each m3u8 eg ip:port/1/ the original ip:port/ will return them all merged still
# 0.1 - Initial testing release


opener = requests.build_opener()
opener.addheaders = [('User-agent', 'YAP - %s - %s - %s' % (sys.argv[0], platform.system(), str(__version__)))]
requests.install_opener(opener)
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


class channelinfo:
	epg = ""
	description = ""
	channum = 0
	channame = ""
	url = ""
	active = True


############################################################
# CONFIG
############################################################

# These are just defaults, place your settings in a file called proxysettings.json in the same directory
LISTEN_IP = "127.0.0.1"
LISTEN_PORT = 99
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
	if not os.path.isfile(os.path.join(os.path.dirname(sys.argv[0]), 'proxysettings.json')):
		logger.debug("No config file found.")
	try:
		logger.debug("Parsing settings")
		with open(os.path.join(os.path.dirname(sys.argv[0]), 'proxysettings.json')) as jsonConfig:
			config = {}
			config = load(jsonConfig)
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
			FFMPEGLOC = config["ffmpegloc"]
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
		<serialNumber></serialNumber>
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

		def __init__(self, master):
			tkinter.Frame.__init__(self, master)
			self.labelText = tkinter.StringVar()
			self.labelText.set("Initial Setup")
			label1 = tkinter.Label(master, textvariable=self.labelText, height=2)
			label1.grid(row=1, column=2)

			self.noteText = tkinter.StringVar()
			self.noteText.set("Notes")
			noteText = tkinter.Label(master, textvariable=self.noteText, height=2)
			noteText.grid(row=1, column=3)

			self.labelM3u8 = tkinter.StringVar()
			self.labelM3u8.set("m3u8 url(s)")
			labelM3u8 = tkinter.Label(master, textvariable=self.labelM3u8, height=2)
			labelM3u8.grid(row=2, column=1)
			#
			userM3u8 = tkinter.StringVar()
			userM3u8.set("www.testurl.com/playlist.m3u8")
			self.m3u8 = tkinter.Entry(master, textvariable=userM3u8, width=30)
			self.m3u8.grid(row=2, column=2)
			#
			self.noteM3u8 = tkinter.StringVar()
			self.noteM3u8.set("separate using a ;")
			noteM3u8 = tkinter.Label(master, textvariable=self.noteM3u8, height=2)
			noteM3u8.grid(row=2, column=3)

			self.labelTuner = tkinter.StringVar()
			self.labelTuner.set("Tuner limit(s)")
			labelTuner = tkinter.Label(master, textvariable=self.labelTuner, height=2)
			labelTuner.grid(row=3, column=1)
			#
			userTuner = tkinter.StringVar()
			userTuner.set("6")
			self.Tuner = tkinter.Entry(master, textvariable=userTuner, width=30)
			self.Tuner.grid(row=3, column=2)
			#
			self.noteTuner = tkinter.StringVar()
			self.noteTuner.set("Number of connections allowed to each m3u8, separate using a ;")
			noteTuner = tkinter.Label(master, textvariable=self.noteTuner, height=2)
			noteTuner.grid(row=3, column=3)

			self.labelXml = tkinter.StringVar()
			self.labelXml.set("xmltv url(s)")
			labelXml = tkinter.Label(master, textvariable=self.labelXml, height=2)
			labelXml.grid(row=4, column=1)
			#
			userXml = tkinter.StringVar()
			userXml.set("www.testurl.com/epg.xml")
			self.xml = tkinter.Entry(master, textvariable=userXml, width=30)
			self.xml.grid(row=4, column=2)
			#
			self.noteXml = tkinter.StringVar()
			self.noteXml.set("One xml can serve multiple m3u8s (channels are linked using tvg-id) separate using a ;")
			noteXml = tkinter.Label(master, textvariable=self.noteXml, height=2)
			noteXml.grid(row=4, column=3)

			self.labelFfmpeg = tkinter.StringVar()
			self.labelFfmpeg.set("FFMPEG Location")
			labelFfmpeg = tkinter.Label(master, textvariable=self.labelFfmpeg, height=2)
			labelFfmpeg.grid(row=5, column=1)

			userFfmpeg = tkinter.StringVar()
			userFfmpeg.set('C:\\ffmpeg\\bin\\ffmpeg.exe')
			self.ffmpeg = tkinter.Entry(master, textvariable=userFfmpeg, width=30)
			self.ffmpeg.grid(row=5, column=2)

			self.noteFfmpeg = tkinter.StringVar()
			self.noteFfmpeg.set("Full path to ffmpeg executable")
			noteFfmpeg = tkinter.Label(master, textvariable=self.noteFfmpeg, height=2)
			noteFfmpeg.grid(row=5, column=3)

			self.labelIP = tkinter.StringVar()
			self.labelIP.set("Listen IP")
			labelIP = tkinter.Label(master, textvariable=self.labelIP, height=2)
			labelIP.grid(row=6, column=1)

			userIP = tkinter.StringVar()
			userIP.set(LISTEN_IP)
			self.ip = tkinter.Entry(master, textvariable=userIP, width=30)
			self.ip.grid(row=6, column=2)

			self.noteIP = tkinter.StringVar()
			self.noteIP.set("If using on other machines then set a static IP and use that.")
			noteIP = tkinter.Label(master, textvariable=self.noteIP, height=2)
			noteIP.grid(row=6, column=3)

			self.labelPort = tkinter.StringVar()
			self.labelPort.set("Listen Port")
			labelPort = tkinter.Label(master, textvariable=self.labelPort, height=2)
			labelPort.grid(row=7, column=1)

			userPort = tkinter.IntVar()
			userPort.set(LISTEN_PORT)
			self.port = tkinter.Entry(master, textvariable=userPort, width=30)
			self.port.grid(row=7, column=2)

			self.notePort = tkinter.StringVar()
			self.notePort.set("If 80 doesn't work try 6969 (ports under 1024 require elevation in Unix)")
			notePort = tkinter.Label(master, textvariable=self.notePort, height=2)
			notePort.grid(row=7, column=3)

			def gather():
				config = {}
				config["m3u8url"] = userM3u8.get()
				config["tunerlimits"] = userTuner.get()
				config["xmlurl"] = userXml.get()
				config["ffmpegloc"] = userFfmpeg.get()
				config["ip"] = userIP.get()
				config["port"] = userPort.get()
				for widget in master.winfo_children():
					widget.destroy()
				global LISTEN_IP, LISTEN_PORT, SERVER_HOST, XMLURL, M3U8URL, FFMPEGLOC, TUNERLIMITS
				with open(os.path.join(os.path.dirname(sys.argv[0]), 'proxysettings.json'), 'w') as fp:
					dump(config, fp)

				LISTEN_IP = config["ip"]
				LISTEN_PORT = config["port"]
				SERVER_HOST = "http://" + LISTEN_IP + ":" + str(LISTEN_PORT)
				XMLURL = config["xmlurl"]
				M3U8URL = config["m3u8url"]
				FFMPEGLOC = config["ffmpegloc"]
				TUNERLIMITS = config["tunerlimits"].split(';')


				button1 = tkinter.Button(master, text="Launch!!", width=20,
				                         command=lambda: self.client_exit(master))
				button1.grid(row=1)

			button1 = tkinter.Button(master, text="Submit", width=20, command=lambda: gather())
			button1.grid(row=8, column=2)

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
	#todo parses merged m3u8s into a chan_map dict for later use.
	chan_map = {'0':{}}
	obtain_m3u8()
	logger.debug("Loading channel list")
	split = [x for x in m3u8_playlist.split("\n") if x != ""]
	for i in range(0,len(split),2):
		count = len(chan_map['0'])+1
		# print(i)
		retVal = channelinfo()
		meta = split[i].split(',')
		retVal.channame = meta[1][1:]
		retVal.channum = count #int(find_between(meta[0],'channel-id="','"'))
		retVal.epg = find_between(meta[0],'tvg-id="','"')
		m3u8 = find_between(meta[0],'group-title="','"')
		retVal.url = split[i+1].strip()
		chan_map['0'][count] = {}
		chan_map['0'][count] = retVal
		if not m3u8 in chan_map:
			chan_map[m3u8] = {}
		chan_map[m3u8][count] = {}
		chan_map[m3u8][count] = retVal
	return chan_map

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
	global m3u8_playlist
	m3u8_playlist = ''
	urlstring = M3U8URL

	urlstring = urlstring.split(';')
	m3u8_number = 0
	for url in urlstring:
		m3u8_number+=1
		m3u8_merger(url, m3u8_number)


		
def m3u8_merger(url, m3u8_number):
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
	global m3u8_playlist
	inputm3u8 = [x for x in inputm3u8 if (x != '' and x != '\n')]
	count = 0
	for i in range(len(inputm3u8)):
		if inputm3u8[i] != "" or inputm3u8[i] != "\n":
			try:
				if inputm3u8[i].startswith("#"):
					count+=1
					grouper = inputm3u8[i]
					grouper = grouper.split(',')
					grouper = grouper[0] + ' channel-id="%s" group-title="%s", %s' % (count, m3u8_number, grouper[1])
					m3u8_playlist += grouper + "\n"
				else:
					m3u8_playlist += inputm3u8[i] + "\n"
			except:
				logger.debug("skipped:", inputm3u8[i])
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
		lineup.append({'GuideNumber': chan_map[tuner][c].channum,
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
# Flask Routes
############################################################
@app.route('/<tuner>/<request_file>')
def tvh(tuner, request_file):
	try:
		t_limit = TUNERLIMITS[int(tuner)-1]
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
		logger.info("Unknown requested %r by %s", request_file, request.environ.get('REMOTE_ADDR'))
		abort(404, "Unknown request")


@app.route('/<request_file>')
def bridge(request_file):
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

	elif request_file.lower() == 'playlist.m3u8':
		# returning Dynamic channels
		if request.args.get('ch'):
			chan = request.args.get('ch')
			url = ""
			response = redirect(url, code=302)
			headers = dict(response.headers)
			headers.update({'Content-Type': 'application/x-mpegURL', "Access-Control-Allow-Origin": "*"})
			response.headers = headers
			logger.info("Channel %s playlist was requested by %s", sanitized_channel,
			            request.environ.get('REMOTE_ADDR'))
			# useful for debugging
			logger.debug("URL returned: %s" % ss_url)
			
			return redirect(ss_url, code=302)
			
		# returning dynamic playlist
		else:
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
		logger.info("Unknown requested %r by %s", request_file, request.environ.get('REMOTE_ADDR'))
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
		global chan_map
		chan_map = build_channel_map()

	except:
		logger.exception("Exception while building initial playlist: ")
		exit(1)

	try:
		thread.start_new_thread(thread_playlist, ())
	except:
		_thread.start_new_thread(thread_playlist, ())

	print("\n##############################################################")
	print("EPG url is %s/epg.xml" % SERVER_HOST)
	print("Plex Live TV url is %s" % SERVER_HOST)
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

	# debug causes it to load twice on initial startup and every time the script is saved, TODO disbale later
	try:
		app.run(host=LISTEN_IP, port=LISTEN_PORT, threaded=True, debug=False)
	except:
		os.system('cls' if os.name == 'nt' else 'clear')
		logger.exception("Proxy failed to launch, try another port")
	logger.info("Finished!")
