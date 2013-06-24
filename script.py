#!/usr/bin/python
#Copyright 2013 David Ventura
#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.
#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.
#You should have received a copy of the GNU General Public License
#along with this program.  If not, see <http://www.gnu.org/licenses/>.

#TODO soporte para comprimidos, 
#TODO si el capitulo tiene bien el nombre muere (falla el filebot)

import sqlite3 
import re 
import sys 
import subprocess 
import os
import datetime
import shutil

iso_extension = [ 'iso' ]
video_extension = [ 'mkv', 'avi', 'ogm', 'mp4' ]
compressed_ext = [ 'rar', 'tar', 'zip', '7z' ]
ignored_folders = [ 'sample', "Sample", "samples","Samples","SAMPLE","SAMPLES","extra","Extra","EXTRA" ]
SSH_notifications = True
SSH_user = 'david'
SSH_target = '192.168.1.200'
SSH_command = 'notify-send -t 3000 -i /usr/share/icons/hicolor/48x48/apps/transmission.png "%t% finished downloading"' #%t% will be replaced with torrent's name


basepath = '/storage/'
moviePath=basepath+'Movies/'
database =basepath+'sickbeard.db'
logfile =basepath+'log.log'
log=open(logfile,'a')
dbOpen = False
user='david'
password='transmission'
host='localhost'
baseCommand=['transmission-remote', host, '-n '+user+':'+password]

def initialize():
	global log,conn,c,originalname, torrent_id, torrent_dir, isDir
	logger("-------------------------------")
	if not os.path.isfile(database):
		die("No database")
	torrentName = os.getenv('TR_TORRENT_NAME')
	if torrentName == None : 
		die("No arg")
	try:
		torrent_dir = os.getenv('TR_TORRENT_DIR')
		torrent_id = os.getenv('TR_TORRENT_ID')
		#logger(torrent_dir+" - "+torrent_id+" - "+torrentName)
	except KeyError:
		die("Setea bien los parametros de ambiente")

	isDir = False
	if os.path.isdir(os.path.join(torrent_dir,torrentName)):
		isDir = True

	originalname=torrentName #esto es valido? No tengo que leer la lista de arhivos?
	conn = sqlite3.connect(database)
	c = conn.cursor()
	dbOpen = True
def close():
	if dbOpen: c.close()
	logger("Finalizo con exito")
	log.close()
def die(reason):
	logger("Script died. Reason: " + reason)
	resumeTorrent()
	close()
	sys.exit()
def logger(val):
	localtime = datetime.datetime.now()
	log.write(localtime.strftime("%Y-%m-%d %H:%M:%S") + " - " + val+"\n")
def isIso(f):
	if getExtension(f) in iso_extension: return True
	return False
def isVideo(f):
	if getExtension(f) in video_extension: return True	
	return False
def isCompressed(f):
	if getExtension(f) in compressed_ext: return True
	return False
def isFromTV(f):
	seriesname = f.split("-")[0].strip()
	c.execute("SELECT show_name, location FROM tv_shows;")
	for row in c:
		if row[0] == seriesname:
			logger("El archivo es de la serie: " + row[0])
			return row[1]+"/"
	return ''
def pauseTorrent():
	logger('Pausando torrent con id '+torrent_id)
	subprocess.Popen(['transmission-remote', host, '-n', user+':'+password, '-t', torrent_id, '-S'],stdout=subprocess.PIPE)

def resumeTorrent():
	logger('Resumiendo torrent con id '+torrent_id)
	subprocess.Popen(['transmission-remote', host, '-n', user+':'+password, '-t',torrent_id, '-s'],stdout=subprocess.PIPE) #START

def renameFile(originalname):
	logger('Llamando a filebot con: '+originalname)
	fb=subprocess.Popen(['filebot','-rename',originalname],stdout=subprocess.PIPE) #filebot
	fb.wait()
	if fb.returncode != 0:
		if fb.returncode == 255:
			logger('ERROR AL OBTENER EL NOMBRE -> probando non strict')
			fb=subprocess.Popen(['filebot','-rename',originalname, '-non-strict'],stdout=subprocess.PIPE) #filebot
			fb.wait()
			if (fb.returncode != 0): die('Error obteniendo el video con non-strict.')
	newfilename=""
	regex = re.compile("Rename.*to\s+\[(?P<g>.*?)\]")
	for line in fb.stdout:
		logger(line)
		r = regex.search(line)
		if 'Rename' in line:
			if not r: continue
			if len(r.groups()) > 0:
				newfilename=r.groups()[0]
				break
		if 'Skipped' in line:
			logger("skipped mang")
			break
	
	if len(newfilename) < 1:
		die("falle al intentar encontrar el nombre del capitulo")
	return newfilename
	
def getExtension(f):
	lista=f.split(".")
	if len(lista) < 2: die('Archivo '+f+' sin extension')
	return lista[len(lista)-1]

def processIso(iso):
	path=isopath
	newfile=os.path.join(path,iso)
	logger("Moviendo archivo " + renamedfile + " a  "+newfile)
	shutil.move(renamedfile, newfile) #MUEVO EL ARCHIVO
	logger("Linkeando "+newfile+" a "+ originalfile)
	os.symlink(newfile, originalfile) #SYMLINK

def processVideo(originalname):
	newfilename=renameFile(originalname)
	filedir=os.path.dirname(originalname)
	path=isFromTV(newfilename)
	if len(path) == 0: path = moviePath #TV OR MOVIE?
	renamedfile=os.path.join(filedir,newfilename)
	newfile=os.path.join(path,newfilename)
	originalfile=os.path.join(filedir,originalname)

	logger("Moviendo archivo " + renamedfile + " a  "+newfile)
	shutil.move(renamedfile, newfile) #MUEVO EL ARCHIVO
	logger("Linkeando "+newfile+" a "+ originalfile)
	os.symlink(newfile, originalfile) #SYMLINK

def findVideos(f):
	logger('Buscando archivos en ' + f)
	paths = []
	for root, dirs, files in os.walk(f):
		for ignored in ignored_folders:
			for d in dirs:
				if ignored in d:
					dirs.remove(d)
		for file in files:
			if getExtension(file) in video_extension: paths.append(os.path.join(root,file))
	return paths

initialize()
if SSH_notifications:
	SSH_command = SSH_command.replace("%t%", originalname)
	print SSH_command
	os.system("ssh -o ConnectTimeout=1 " + SSH_user + "@" + SSH_target + " ' export DISPLAY=:0; " + SSH_command + "'")
	
logger("Procesando archivo: "+originalname)
if isDir:
	files = findVideos(os.path.join(torrent_dir,originalname))
	if len(files) == 0:
		logger("No encontre nada util en la carpeta")
		close()
	
	pauseTorrent()
	for video in files:
		processVideo(video)
else:
	pauseTorrent()
	if isVideo(originalname):
		processVideo(originalname)
	else:
		if isCompressed(originalname):
			logger("compressed")
		else:
			if isIso(originalname):
				processIso(originalname)
			else:
				logger("what is this")

resumeTorrent()
close()
