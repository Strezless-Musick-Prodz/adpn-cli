#!/usr/bin/python3
#
# staged-content-file-size.py: Count up the total file size of a directory of files
# that has been staged on a server accessible by FTP.
#
# @version 2019.0627

import re
import sys
import os.path
import fileinput
import ftplib
import urllib.parse
import math
from ftplib import FTP
from getpass import getpass
from myLockssScripts import myPyCommandLine, myPyJSON

def bytes_to_human_readable (bytes: int) -> str :
	# supports units up to yottabytes. If you have 1,237,940,039,285,380,274,899,124,224
	# bytes or more to report, sorry, your human-readable number is going to be a bit wide
	units = ('B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB')
	magnitude = min(int(math.floor(math.log(bytes, 1024))), len(units)-1) if bytes != 0 else 0
	hubbabytes = (bytes / math.pow(1024, magnitude))
	return ("%(lots).1f %(unit)s" % {"lots": hubbabytes, "unit": units[magnitude]})

class FTPListing :

	def __init__ (self, ftp) :
		self.ftp = ftp
		
	def size (self, file) :
		size=None
		try :
			size=self.ftp.size(file)
		except ftplib.error_perm :
			pass
		return size

	def pwd (self) :
		return self.ftp.pwd()
		
	def cwd (self, dir) :
		self.ftp.cwd(dir)

	def nlst (self) :
		return self.ftp.nlst()

	def ls_r (self, path, maxdepth=-1) :
		anchor = self.pwd()
			
		if maxdepth != 0 :
			try :
				self.cwd(path)
			
				files = [ (file, self.size(file)) for file in self.nlst() ]
			
				result = [ ]
				for file, size in files :
					if size is not None :
						result.append((file, size))
					else :
						ls = self.ls_r(file, maxdepth-1)
						result.append((file, ls))
				
			except ftplib.error_perm as e :
				result = [ ]

			files = result
			
		else :
			files = [ ]
		
		self.cwd(anchor)
			
		return files
	
	def pack_ls (self, ls, prefix="") :
		out = [ ]
		path = (prefix + "/") if len(prefix) > 0 else ""
		
		for (key, value) in ls :
			if isinstance(value, list) :
				out = out + self.pack_ls(ls=value, prefix=path+key)
			else :
				out.append((path+key, value))

		return out
		
	def quit (self) :
		self.ftp.quit()

class StagedContentFileSizeScript :
	"""Usage: staged-content-file-size.py [OPTIONS]... [FTP_URL]
	
  --help               	display these usage notes
  --host=<HOSTNAME>    	connect to the FTP host named <HOSTNAME>
  --user=<USERNAME>   	connect to the FTP host as user <USERNAME>
  --base_dir=<PATH>    	the base path containing our subdirectory is <PATH>
  --subdirectory=<DIR> 	a specific subdirectory in which to tally the file sizes
  --directory=<DIR>    	alternate form of --subdirectory=<DIR>
  --output=<FORMAT>    	text/plain or text/tab-separated-values

FTP_URL can provide a hostname, a username, a password, and a base_dir path packed into
a URL in the format:

  ftp://[<USER>[:<PASS>]@]<HOSTNAME>/<BASE_DIR>

For example:

  ./staged-content-file-size.py --output=text/plain --subdirectory=WPA-Folder-01 ftp://charlesw.johnson@archives.alabama.gov/Lockss/

Exit code is 0 in case of successful output.
1= login failure (usually due to an incorrect username/password pair)
2= file not found error (usually due to an incorrect base_dir or subdirectory)
3= miscellaneous (unrecognized FTP error code)
	"""
	def __init__ (self, scriptname, argv, switches) :
		self.scriptname = scriptname
		self.argv = argv
		self.switches = switches
		self.exitcode = 0
		self.ftp = None
		
	def display_usage (self) :
		print(self.__doc__)

	def display_error (self, errmesg) :
		print("[%(scriptname)s] %(errmesg)s" % {"scriptname": scriptname, "errmesg": errmesg}, file=sys.stderr)

	def display_output (self, bytes, files) :
		output = {
		"text/plain": "TOTAL: %(hu)s (%(bb)s bytes; %(files)s files)",
		"text/tab-separated-values": "\t".join(["%(hu)s", "%(bb)s", "%(files)s"])
		}

		print(
			output[self.switches['output']]
			% { 
				"hu": bytes_to_human_readable(bytes),
				"bb": "{:,}".format(bytes),
				"files": "{:,}".format(files)
			}
		)
	
	def execute (self) :
		(host, user, passwd, base_dir, subdirectory) = self.get_params()
	
		try :
			self.ftp = FTPListing(FTP(host, user=user, passwd=passwd))

			# Let's CWD over to the repository
			self.ftp.cwd(base_dir)

			# Let's request a recursive listing of all the files together with their sizes
			files = self.ftp.pack_ls(self.ftp.ls_r(subdirectory))
			
			# Let's add up the size of every file to get a total
			total = sum([ size for (filename, size) in files ])

			self.display_output(total, len(files))
		
			self.ftp.quit()

		except ftplib.error_perm as e :
			(code, message) = e.args[0].split(" ", 1)
			code = int(code)
	
			if 530 == code :
				errmesg = "%(code)d Failed login for %(user)s@%(host)s -- Double-check your username and password? (%(mesg)s)" % {"user": user, "host": host, "code": code, "mesg": message.rstrip()}
				self.exitcode = 1
			elif 550 == code :
				errmesg = "%(code)d File Not Found in %(base_dir)s/%(subdirectory)s -- Double-check your file path? (%(mesg)s)" % {"code": code, "mesg": message.rstrip(), "base_dir": base_dir, "subdirectory": subdirectory}
				self.exitcode = 2
			else :
				errmesg = e.args[0]
				self.exitcode = 3
		
			self.display_error("FTP FAILURE: %(errmesg)s" % {"errmesg": errmesg})
	
	def get_params (self) :
		if len(self.argv) > 1 :
			(host, user, passwd, base_dir, subdirectory) = self.unpack_ftp_elements(self.argv[1])
		else :
			(host, user, passwd, base_dir, subdirectory) = ("localhost", None, None, "/Lockss", None)

		# start with elements from ftp:// URL, but allow switches to override them
		host=self.switches.get('host') if self.switches.get('host') is not None else host
		user=self.switches.get('user') if self.switches.get('user') is not None else user
		base_dir=self.switches.get('base_dir') if self.switches.get('base_dir') is not None else base_dir
		subdirectory=self.switches.get('directory') if self.switches.get('directory') is not None else subdirectory
		subdirectory=self.switches.get('subdirectory') if self.switches.get('subdirectory') is not None else subdirectory

		# request user input if these are not sepcified on command line
		passwd_prompt = "FTP Password (%(user)s@%(host)s): " % {"user": user, "host": host}
		passwd=passwd if passwd is not None else getpass(passwd_prompt)
		base_dir=base_dir if base_dir is not None and len(base_dir) > 0 else input("Base dir: ")
		subdirectory=subdirectory if subdirectory is not None else input("Subdirectory: ")

		return (host, user, passwd, base_dir, subdirectory)
		
	def unpack_ftp_elements(self, url) :
		(host, user, passwd, base_dir, subdirectory) = (None, None, None, None, None)
	
		bits=urllib.parse.urlparse(url)
		if len(bits.netloc) > 0 :
			netloc = bits.netloc.split('@', 1)
			netloc.reverse()
			(host, credentials)=(netloc[0], netloc[1] if len(netloc) > 1 else None)
			credentials=credentials.split(':', 1) if credentials is not None else [None, None]
			(user, passwd) = (credentials[0], credentials[1] if len(credentials) > 1 else None)
		if len(bits.path) > 1 :
			base_dir = bits.path
			subdirectory = '.'
		
		return (host, user, passwd, base_dir, subdirectory)

if __name__ == '__main__':

	scriptname = os.path.basename(sys.argv[0])

	(sys.argv, switches) = myPyCommandLine(sys.argv, defaults={
		"host": None, "user": None,
		"subdirectory": None, "directory": None, "base_dir": None,
		"output": "text/plain", "help": None
	}).parse()

	script = StagedContentFileSizeScript(scriptname, sys.argv, switches)
	if switches['help'] :
		script.display_usage()
	else :
		script.execute()

	sys.exit(script.exitcode)


