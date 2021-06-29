#!/usr/bin/python3
#
# Produce a manifest HTML file from a standardized template to be staged along
# with a LOCKSS Archival Unit (AU).
#
# @version 2019.0719

import os
import sys
import stat
import json
import urllib.parse
import myLockssScripts
from getpass import getpass
from myLockssScripts import myPyCommandLine, myPyPipeline

def get_templatedirectory () :
    scriptpath = os.path.realpath(__file__)
    scriptname = os.path.basename(scriptpath)
    scriptdir = os.path.dirname(scriptpath)
    return scriptdir

def get_filesystemlocation (file) :
    location = None
    try :
        fstat = os.stat(file)
        if stat.S_ISDIR(fstat.st_mode) :
            location = file
        else :
            location = os.path.dirname(file)
            
    except FileNotFoundError as e :
        pass
    return location

def read_makemanifest_html (parameters) :
    infile = ( "%(path)s/%(file)s.sprintf" % {"path": get_templatedirectory(), "file": file} )
    
    instream = open(infile, "r")
    template = "\n".join([ line.rstrip() for line in instream ])
    instream.close()
    
    html = ( template % parameters )
    return html

if __name__ == '__main__' :

	(argv, switches) = myPyCommandLine(sys.argv, defaults={ "parameters": "{}", "local": None }).parse()

	scriptpath = os.path.realpath(__file__)
	scriptname = os.path.basename(scriptpath)
	scriptdir = get_templatedirectory()
	
	os.environ["PATH"] = ":".join([scriptdir, os.environ["PATH"]])
	
	scriptLine = ['adpn-plugin-details.py', '--output=text/tab-separated-values']
	
	detailsScript = myPyPipeline([ scriptLine + sys.argv[1:] ])
	(buff, errbuf, exits) = detailsScript.siphon()
	
	settings = [ line.rstrip().split("\t") for line in filter(lambda text: len(text.rstrip())>0, buff.split("\n")) ]
	settings = [ (line[1], line[2]) for line in settings if line[0] == 'setting' ]
	
	urlpaths = [ urllib.parse.urlparse(value) for setting, value in settings if setting == 'au_manifest' ]
	if len(urlpaths) == 0 :
		urlpaths = [ urllib.parse.urlparse(value) for setting, value in settings if setting == 'au_start_url' ]

	basenames = [ os.path.basename(url.path) for url in urlpaths ]

	parameters = json.loads(switches['parameters'])
	parameters = {**dict(settings), **parameters}

	for file in basenames :
		infile = "%(path)s/templates/%(file)s.sprintf" % {"path": scriptdir, "file": file}
		outdir = get_filesystemlocation(switches['local']) if switches['local'] is not None else "."
		outfile = "%(path)s/%(file)s" % {"path": outdir, "file": file}
		
		instream = open(infile, "r")
		intext = "\n".join([ line.rstrip() for line in instream ])
		instream.close()
		
		if "-" == switches['local'] :
			print(intext % parameters)
		else :
			hOut = open(outfile, "w")
			outtext = (intext % parameters)
			print(intext % parameters, file=hOut)
			hOut.close()
			print("%(filename)s\t%(size)d\n" % {"filename": outfile, "size": os.stat(outfile).st_size})
