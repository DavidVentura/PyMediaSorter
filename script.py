#!/usr/bin/python
#TODO soporte para comprimidos, 
#TODO ignored folders
import sqlite3 
import re 
import sys 
import subprocess 
import os
import datetime
import shutil

video_extension = [ 'mkv', 'avi', 'ogm', 'mp4' ]
compressed_ext = [ 'rar', 'tar', 'zip', '7z' ]
ignored_folders = [ 'sample' ]

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
	torrentName = os.getenv('TR_TORRENT_NAME')
	if torrentName == None : 
		die("No arg")
	try:
		torrent_dir = os.getenv('TR_TORRENT_DIR')
		torrent_id = os.getenv('TR_TORRENT_ID')
		#logger(torrent_dir+" - "+torrent_id+" - "+torrentName)
	except KeyError:
		die("Setea bien los parametros de ambiente")

	if os.path.isdir(os.path.join(torrent_dir,torrentName)):
		isDir = True
	else:
		isDir = False

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
	close()
	sys.exit()
def logger(val):
	localtime = datetime.datetime.now()
	log.write(localtime.strftime("%Y-%m-%d %H:%M:%S") + " - " + val+"\n")
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
			if (fb.returncode != 0) die('Error obteniendo el video con non-strict.')
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
		for file in files:
			if getExtension(file) in video_extension: paths.append(os.path.join(root,file))
	return paths

initialize()
logger("Procesando archivo: "+originalname)
pauseTorrent()
if isDir:
	for video in findVideos(os.path.join(torrent_dir,originalname)):
		processVideo(video)
else:
	if isVideo():
		processVideo()
	else:
		if isCompressed():
			logger("compressed")
		else:
			logger("what is this")

resumeTorrent()
close()
