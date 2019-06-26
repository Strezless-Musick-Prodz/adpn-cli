#!/usr/bin/python3

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

def unpack_ftp_elements(url) :
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
		subdirectory = '/.'
		
	return (host, user, passwd, base_dir, subdirectory)
	
(sys.argv, switches) = myPyCommandLine(sys.argv, defaults={
	"host": None, "user": None, "subdirectory": None, "base_dir": None,
	"output": "text/plain"
}).parse()

if len(sys.argv) > 1 :
	(host, user, passwd, base_dir, subdirectory) = unpack_ftp_elements(sys.argv[1])
else :
	(host, user, passwd, base_dir, subdirectory) = ("localhost", None, None, "/Lockss", None)

passwd_prompt = "FTP Password (%(user)s@%(host)s): " % {"user": user, "host": host}

host=switches.get('host') if switches.get('host') is not None else host
user=switches.get('user') if switches.get('user') is not None else user
base_dir=switches.get('base_dir') if switches.get('base_dir') is not None else base_dir
subdirectory=switches.get('subdirectory') if switches.get('subdirectory') is not None else subdirectory

passwd=passwd if passwd is not None else getpass(passwd_prompt)
base_dir=base_dir if base_dir is not None and len(base_dir) > 0 else input("Base dir: ")
subdirectory=subdirectory if subdirectory is not None else input("Subdirectory: ")

ftp = FTPListing(FTP(host, user=user, passwd=passwd))

# Let's CWD over to the repository
ftp.cwd(base_dir)

files = ftp.pack_ls(ftp.ls_r(subdirectory))
total = sum([ size for (filename, size) in files ])

output = {
	"text/plain": "TOTAL: %(hu)s (%(bytes)s bytes; %(files)d files)",
	"text/tab-separated-values": "\t".join(["%(hu)s", "%(bytes)s", "%(files)d"])
}

print(output[switches['output']] % { 
"hu": bytes_to_human_readable(total), "bytes": "{:,}".format(total), "files": len(files)})

ftp.quit()


