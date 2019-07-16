#!/usr/bin/python3
#
# adpn-stage-content.py: upload a directory of files for preservation to a staging server
# accessible via FTP, easy-peasy lemon squeezy.
#
# @version 2019.0627

import re
import sys
import os.path
import fileinput
import ftplib
import urllib.parse
import math
import subprocess
import json
from datetime import datetime
from io import BytesIO
from ftplib import FTP
from getpass import getpass
from myLockssScripts import myPyCommandLine, myPyJSON

class FTPStaging :

	def __init__ (self, ftp, user) :
		self.ftp = ftp
		self.user = user
	
	def size (self, file) :
		size=None
		try :
			size=self.ftp.size(file)
		except ftplib.error_perm :
			pass
		return size

	def url_host (self) :
		return ("%(user)s@%(host)s" if self.user else "%(host)s") % {"user": self.user, "host": self.ftp.host}

	def url (self) :
		return "ftp://%(host)s%(path)s" % {"host": self.url_host(), "path": self.ftp.pwd()}
		
	def pwd (self) :
		return self.ftp.pwd()
	
	def mkd (self, dir) :
		self.ftp.mkd(dir)

	def chdir (self, dir, remote=None, make=False) :
		rdir = remote if remote is not None else dir
		rlast = self.cwd(dir=rdir, make=make)

		llast = os.getcwd()

		try :
			os.chdir(dir)
		except FileNotFoundError as e :
			if make :
				os.mkdir(dir)
				os.chdir(dir)
			else :
				raise

		return (llast, rlast)
		
	def cwd (self, dir, make=False) :
		last = self.pwd()

		try :
			self.ftp.cwd(dir)
		except ftplib.error_perm as e :
			if make :
				self.ftp.mkd(dir)
				self.ftp.cwd(dir)
			else :
				raise

		return last
		
	def nlst (self) :
		return self.ftp.nlst()

	def download_file (self, file = None) :
		self.ftp.retrbinary("RETR %(file)s" % {"file": file}, open( file, 'wb' ).write)
		
	def download (self, file = None, exclude = None, notification = None) :
		out = notification if notification is not None else lambda level, type, arg: (level, type, arg) # NOOP
		
		if '.' == file or self.size(file) is None :
			
			if '.' != file :
				(lpwd, rpwd) = self.chdir(dir=file, make=True)
				out(2, "chdir", (os.getcwd(), self.ftp.pwd()))

			for subfile in self.nlst() :
				exclude_this = exclude(subfile) if exclude is not None else False
				if not exclude_this :
					(level, type) = (1, "downloaded")

					self.download(file=subfile, exclude=exclude, notification=notification)					
						
				else :
					(level, type) = (2, "excluded")
					
				out(level, type, subfile)

			if '.' != file :
				self.chdir(dir=lpwd, remote=rpwd, make=False)
				out(2, "chdir", (lpwd, rpwd))
				self.ftp.rmd(file)
				out(1, "rm", file)
				
		else :
			self.download_file(file=file)
			if self.size(file) == os.stat(file).st_size :
				self.ftp.delete(file)
				out(1, "rm", file)

	def upload_file (self, blob = None, file = None) :
		if isinstance(blob, str) :
			blob = blob.encode("utf-8")
			
		stream=BytesIO(bytes(blob)) if blob is not None else open(file, 'rb')
		self.ftp.storbinary("STOR %(filename)s" % {"filename": file}, stream)
		stream.close()	
	
	def upload (self, blob = None, file = None, exclude = None, notification = None) :
		out = notification if notification is not None else lambda level, type, arg: (level, type, arg) # NOOP
		
		if blob is not None :
			self.upload_file(blob, file)
		elif os.path.isfile(file) :
			self.upload_file(blob=None, file=file)
		elif '.' == file or os.path.isdir(file) :
			
			if '.' != file :
				(lpwd, rpwd) = self.chdir(dir=file, make=True)
				out(2, "chdir", (os.getcwd(), self.ftp.pwd()))

			for subfile in os.listdir() :
				exclude_this = exclude(subfile) if exclude is not None else False
				if not exclude_this :
					(level, type) = (1, "uploaded")				
					self.upload(blob=None, file=subfile, exclude=exclude, notification = notification)					
				else :
					(level, type) = (2, "excluded")
					
				out(level, type, subfile)

			if '.' != file :
				out(2, "chdir", (lpwd, rpwd))
				self.chdir(dir=lpwd, remote=rpwd, make=False)
			
	def quit (self) :
		self.ftp.quit()

class ADPNStageContentScript :
	"""
Usage: adpn-stage-content.py [<OPTIONS>]... [<URL>]

URL should be an FTP URL, in the form ftp://[<user>[:<pass>]@]<host>/<dir>
The <user> and <pass> elements are optional; they can be provided as part
of the URL, or using command-line switches, or interactively at input and
password prompts.

  --local=<PATH>   	   	the local directory containing the files to stage
  --au_title=<TITLE>   	the human-readable title for the contents of this AU
  --subdirectory=<SLUG>	the subdirectory on the staging server to hold AU files
  --directory=<SLUG>   	identical to --subdirectory
  --backup=<PATH>      	path to store current contents (if any) of staging location
  
Output and Diagnostics:

  --output=<MIME>      	text/plain or application/json
  --verbose=<LEVEL>   	level (0-2) of diagnostic output during FTP upload/download
  --quiet             	identical to --verbose=0
  
Common configuration parameters:

  --base_url=<URL>     	WWW: the URL for web access to the staging area
  --host=<NAME>        	FTP: host name of the server with the staging area
  --user=<NAME>        	FTP: username for logging in to the staging server
  --pass=<PASSWD>      	FTP: password for logging in to the staging server
  --base_dir=<PATH>   	FTP: path to the staging area on the FTP server
  --institution=<NAME>  Manifest: human-readable nmae of the institution

To generate a manifest file, the script needs to use information from the
LOCKSS Publisher Plugin. Plugins are hosted on the LOCKSS props
server/admin node.

If you need to connect to the LOCKSS props server through a SOCKS5 proxy, use:

  --proxy=<HOST>      	the name of your proxy (use "localhost" for SSH tunnel)
  --port=<NUMBER>      	the port number for your proxy
  
If you need to use SSH tunneling to connect to the SOCKS5 proxy, use:

  --tunnel=<HOST>     	the name of the host to open an SSH tunnel to
  --tunnel-port=<PORT> 	the port for SSH connections to the tunnel (default: 22)

Default values for these parameters can be set in the JSON configuration file
adpnet.json, located in the same directory as the script. To set a default
value, add a key-value pair to the hash table with a key based on the name of
the switch. (For example, to set the default value for the --institution switch
to "Alabama Department of Archives and History", add the following pair to the
hash table:

	{
		...
		"institution": "Alabama Department of Archives and History",
		...
	}
	
The default values in adpnet.json are overridden if values are provided on the
command line with explicit switches.
	"""
	
	def __init__ (self, scriptname, argv, switches, parameters) :
		self.scriptname = scriptname
		self.argv = argv
		self.switches = switches
		self.parameters = parameters
		self.exitcode = 0
		
		self.verbose = int(self.switches.get('verbose')) if self.switches.get('verbose') is not None else 0
		if self.switches.get('quiet') :
			self.verbose=0

		# start out with defaults
		self.ftp = None
		self.host = "localhost"
		self.user = None
		self.passwd = None
		self.base_dir = "/Lockss"
		self.subdirectory = None
		
		# now unpack and overlay elements from the FTP URL, if any is provided
		if len(self.argv) > 1 :
			self.unpack_ftp_elements(self.argv[1])
			
		# now overlay any further values from the command-line switches, if provided
		self.host=self.switches.get('host') if self.switches.get('host') is not None else self.host
		self.user=self.switches.get('user') if self.switches.get('user') is not None else self.user
		self.passwd=self.switches.get('pass') if self.switches.get('pass') is not None else self.passwd
		self.base_dir=switches.get('base_dir') if switches.get('base_dir') is not None else self.base_dir
		self.subdirectory=switches.get('directory') if switches.get('directory') is not None else self.subdirectory
		self.subdirectory=switches.get('subdirectory') if switches.get('subdirectory') is not None else self.subdirectory	
	
	def switched (self, key) :
		got = not not self.switches.get(key, None)
		return got
		
	def unpack_ftp_elements(self, url) :
		(host, user, passwd, base_dir, subdirectory) = (None, None, None, None, None)
	
		bits=urllib.parse.urlparse(url)
		if len(bits.netloc) > 0 :
			netloc = bits.netloc.split('@', 1)
			netloc.reverse()
			(host, credentials)=(netloc[0], netloc[1] if len(netloc) > 1 else None)
			credentials=credentials.split(':', 1) if credentials is not None else [None, None]
			(user, passwd) = (credentials[0], credentials[1] if len(credentials) > 1 else None)

			self.host = host
			self.user = user
			self.passwd = passwd

		if len(bits.path) > 1 :
			base_dir = bits.path
			subdirectory = '.'
			
			self.base_dir = base_dir
			self.subdirectory = subdirectory

	def make_manifest_page (self) :
		try :
			jsonParams = json.dumps(self.parameters)
			
			cmdline = [
				"adpn-make-manifest.py",
				"--jar="+self.switches['jar'],
				"--proxy="+self.switches['proxy'],
				"--port="+self.switches['port'],
				"--tunnel="+self.switches['tunnel'],
				"--tunnel-port="+self.switches['tunnel-port'],
				"--parameters="+jsonParams
			]
			
			buf = subprocess.check_output(cmdline, encoding="utf-8")
		except subprocess.CalledProcessError as e :
			code = e.returncode
			buf = e.output
		
		return buf
		
	def mkBackupDir (self) :
		backupPath=self.switches['backup']
		
		try :
			os.mkdir(backupPath)
		except FileExistsError as e :
			pass
		
		datestamp=datetime.now().strftime('%Y%m%d%H%M%S')
		backupPath="%(backup)s/%(date)s" % {"backup": backupPath, "date": datestamp}
		
		try :
			os.mkdir(backupPath)
		except FileExistsError as e :
			pass

		backupPath="%(backup)s/%(subdirectory)s" % {"backup": backupPath, "subdirectory": self.subdirectory}
		try :
			os.mkdir(backupPath)
		except FileExistsError as e :
			pass

		return backupPath
		
	def output_status (self, level, type, arg) :
		(prefix, message) = (type, arg)

		if "uploaded" == type :
			prefix = ">>>"
		elif "downloaded" == type :
			prefix = "<<<"
		elif "excluded" == type :
			prefix = "---"
			message = ("excluded %(arg)s" % {"arg": arg})
		elif "chdir" == type :
			prefix = "..."
			path = "./%(dir)s" % {"dir": arg[1]} if arg[1].find("/")<0 else arg[1]
			message = "cd %(path)s" % {"path": path}
		elif "ok" == type :
			prefix = "JSON PACKET:\t"
			message["status"] = type
		
		out=sys.stdout
		if self.switches['output'] == 'application/json' :
			message = json.dumps(message)
			if level > 0 :
				out=sys.stderr
				
		if prefix is not None and level <= self.verbose :
			print(prefix, message, file=out)
	
	def display_usage (self) :
		print(self.__doc__)
		self.exitcode = 0
		
	def execute (self) :

		passwd_prompt = "FTP Password (%(user)s@%(host)s): " % {"user": self.user, "host": self.host}

		try :
			if self.user is None :
				self.user = input("User: ")
			if self.passwd is None :
				self.passwd = getpass(passwd_prompt)
			if self.base_dir is None or len(self.base_dir) == 0:
				self.base_dir = input("Base dir: ")
			if self.subdirectory is None or len(self.subdirectory) == 0 :
				self.subdirectory = input("Subdirectory: ")
	
			manifest_html=self.make_manifest_page()
		
			# Let's log in to the host
			self.ftp = FTPStaging(FTP(self.host, user=self.user, passwd=self.passwd), user=self.user)

			# Let's CWD over to the repository
			self.ftp.cwd(self.base_dir)

			backupDir = self.mkBackupDir()
		
			(local_pwd, remote_pwd) = self.ftp.chdir(dir=backupDir, remote=self.subdirectory, make=True)
			self.ftp.download(file=".", exclude=lambda file: file == 'Thumbs.db', notification=self.output_status)

			self.ftp.chdir(dir=local_pwd, remote=remote_pwd)
			(local_pwd, remote_pwd) = self.ftp.chdir(dir=self.switches['local'], remote=self.subdirectory, make=True)

			self.output_status(2, "chdir", (os.getcwd(), self.ftp.pwd()))
		
			# upload the generated manifest page
			self.ftp.upload(blob=manifest_html, file='manifestpage.html')	
			self.output_status(1, "uploaded", 'manifestpage.html')

			# upload the present directory recursively
			self.ftp.upload(file=".", exclude=lambda file: file == 'Thumbs.db', notification=self.output_status)
		
			self.output_status(0, "ok", {"local": os.getcwd(), "staged": self.ftp.url(), "jar": self.switches['jar'], "au_title": self.switches['au_title'], "parameters": [ [ key, parameters[key] ] for key in parameters ] })
		
		except KeyboardInterrupt as e :
			self.exitcode = 255
			print("[%(scriptname)s] Keyboard Interrupt." % {"scriptname": self.scriptname}, file=sys.stderr)
		
		if self.ftp is not None :
			try :
				self.ftp.quit()
			except ftplib.error_perm as e :
				pass

	def exit (self) :
		sys.exit(self.exitcode)
		
if __name__ == '__main__':

	scriptname = os.path.basename(sys.argv[0])
	scriptdir = os.path.dirname(sys.argv[0])
	configjson = "/".join([scriptdir, "adpnet.json"])
	
	os.environ["PATH"] = ":".join( [ scriptdir, os.environ["PATH"] ] )
	
	(sys.argv, switches) = myPyCommandLine(sys.argv, defaults={
			"ftp/host": None, "ftp/user": None, "ftp/pass": None,
			"subdirectory": None, "directory": None,
			"base_dir": None, "output": "text/plain",
			"local": None, "backup": "./backup",
			"verbose": 1, "quiet": False,
			"base_url": None, "au_title": None, "institution": None
	}, configfile=configjson, settingsgroup=["stage", "ftp"]).parse()

	parameters = {
		"base_url": switches['base_url'],
		"subdirectory": switches['subdirectory'],
		"institution": switches['institution'],
		"au_title": switches['au_title']
	}
	script = ADPNStageContentScript(scriptname, sys.argv, switches, parameters)
	if script.switched('help') :
		script.display_usage()
	elif script.switched('details') :
		print("Defaults:", defaults)
		print("")
		print("Settings:", switches)
	else :
		script.execute()

	script.exit()
	