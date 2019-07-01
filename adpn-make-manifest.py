#!/usr/bin/python3

import os
import sys
import json
import urllib.parse
import myLockssScripts
from getpass import getpass
from myLockssScripts import myPyCommandLine, myPyPipeline

if __name__ == '__main__' :

	(argv, switches) = myPyCommandLine(sys.argv, defaults={}).parse()

	scriptname = os.path.basename(sys.argv[0])
	scriptdir = os.path.dirname(sys.argv[0])
	
	os.environ["PATH"] = ":".join([scriptdir, os.environ["PATH"]])

	scriptLine = ['adpn-plugin-details.py', '--output=text/tab-separated-values']
	
	detailsScript = myPyPipeline([ scriptLine + sys.argv[1:] ])
	(buff, errbuf, exits) = detailsScript.siphon()
	
	settings = [ line.rstrip().split("\t") for line in filter(lambda text: len(text.rstrip())>0, buff.split("\n")) ]
	settings = [ (line[1], line[2]) for line in settings if line[0] == 'setting' ]
	urlpaths = [ urllib.parse.urlparse(value) for setting, value in settings if setting == 'au_manifest' ]
	basenames = [ os.path.basename(url.path) for url in urlpaths ]
	
	parameters = json.loads(switches['parameters'])
	parameters = {**dict(settings), **parameters}
	
	for file in basenames :
		infile = "%(path)s/%(file)s.sprintf" % {"path": scriptdir, "file": file}
		outfile = "./%(file)s" % {"file": file}
		
		instream = open(infile, "r")
		intext = "\n".join([ line.rstrip() for line in instream ])
		instream.close()
		print(intext % parameters)
