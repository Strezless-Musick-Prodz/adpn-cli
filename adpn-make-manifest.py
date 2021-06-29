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
import urllib.parse, urllib.request
import myLockssScripts
from getpass import getpass
from myLockssScripts import myPyCommandLine, myPyPipeline

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

class MakeManifestHTMLWebAPI :

    def __init__ (self, url, parameters, file) :
        
        self._parameters = parameters
        self._api = url
        self._errmesg = None
        self._file = file
    
    @property
    def source_object (self) :
        return self.api
    
    @property
    def api (self) :
        return self._api
    
    @property
    def parameters (self, accept=None) :
        if accept is None :
            accept = lambda key, value: value is not None
        
        parameters = {}
        for (key, value) in self._parameters.items() :
            if accept(key, value) :
                parameters[key] = value
        
        return parameters
    
    @property
    def file (self) :
        return self._file
    
    @property
    def errmesg (self) :
        return self._errmesg
        
    @errmesg.setter
    def errmesg (self, rhs) :
        self._errmesg = rhs
    
    def get_data_body (self) :
        return urllib.parse.urlencode(self.parameters).encode('utf-8')
        
    def read (self) :
    
        response = None
        self.errmesg = None
        try :
            req = urllib.request.Request(self.api, data=self.get_data_body(), method="POST")
            response = urllib.request.urlopen(req)
        except urllib.request.HTTPError as e :
            self.errmesg = ( "HTTP ERROR %(code)d %(reason)s [URL=%(url)s]" % { "code": e.code, "reason": e.reason, "url": self.api } )
            raise
        except urllib.request.URLError as e :
            if isinstance(e.reason, str) :
                self.errmesg = ( "URL Error: %(reason)s" % { "reason": e.reason } )
            else :
                self.errmesg = "URL Error: <Unrecognized Error> %(args)s %(context)s" % { "args": str(e.args), "context": str(e.__context__) }
            raise
        except Exception as e :
            self.errmesg = "<Unrecognized Exception> (%(classname)s) %(args)s %(context)s" % { "classname": e.__class__.__name__, "args": str(e.args), "context": str(e.__context__) }
            raise

        text = None
        decoded_text = None
        if response is not None :
            text = response.read()
            encoding = response.headers.get_content_charset('utf-8')
            decoded_text = text.decode(encoding)
            if len(decoded_text) == 0 :
                print("[" + scriptname + "] error: empty result", file=sys.stderr)
        return decoded_text

class MakeManifestHTMLLocalTemplate :

    def __init__ (self, parameters, file) :
        
        self._parameters = parameters
        self._errmesg = None
        self._scriptpath = os.path.realpath(__file__)
        self._file = file
        self._source_object = None
        
    @property
    def parameters (self, accept=None) :
        if accept is None :
            accept = lambda key, value: value is not None
        
        parameters = {}
        for (key, value) in self._parameters.items() :
            if accept(key, value) :
                parameters[key] = value
        
        return parameters
    
    @property
    def file (self) :
        return self._file
    
    @property
    def errmesg (self) :
        return self._errmesg
        
    @errmesg.setter
    def errmesg (self, rhs) :
        self._errmesg = rhs
    
    @property
    def source_object (self) :
        return self._source_object
        
    @source_object.setter
    def source_object (self, rhs) :
        self._source_object = rhs
    
    def get_templatedirectory (self) :
        scriptdir = os.path.dirname(self._scriptpath)
        return os.path.join(scriptdir, "templates")
    
    def read (self) :
        self.source_object = ( "%(path)s/%(file)s.sprintf" % {"path": self.get_templatedirectory(), "file": self.file} )
    
        instream = open(self.source_object, "r")
        template = "\n".join([ line.rstrip() for line in instream ])
        instream.close()
    
        return ( template % parameters )

def align_switches (left, right, switches, override=True) :
    if switches[left] is None :
        switches[left] = switches[right]
    if switches[right] is None :
        switches[right] = switches[left]
    if override :
        if switches[right] != switches[left] :
            switches[right] = switches[left]

if __name__ == '__main__' :
	
	scriptpath = os.path.realpath(__file__)
	scriptname = os.path.basename(scriptpath)
	scriptdir = os.path.dirname(scriptpath)
	configjson = os.path.join(scriptdir, "adpnet.json")
	
	(argv, switches) = myPyCommandLine(sys.argv, defaults={
		"parameters": "{}", "local": None, "api": None, "api/makemanifest": None, "jar": None, "stage/jar": None
	}, configfile=configjson).parse()
	
	align_switches("api", "api/makemanifest", switches)
	align_switches("jar", "stage/jar", switches)
	
	os.environ["PATH"] = ":".join([scriptdir, os.environ["PATH"]])
	
	scriptLine = ['adpn-plugin-details.py', '--output=text/tab-separated-values']
	if switches["jar"] is not None :
		scriptLine.append("--jar=%(jar)s" % switches )

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
		outdir = get_filesystemlocation(switches['local']) if switches['local'] is not None else "."
		outfile = "%(path)s/%(file)s" % {"path": outdir, "file": file}
		
		html_resource = MakeManifestHTMLWebAPI(switches['api'], parameters, file) if switches['api'] else MakeManifestHTMLLocalTemplate(parameters, file)
		try :
			out_html = html_resource.read()
		except :
			if html_resource.errmesg is not None :
				print("[%(cmd)s] Error generating HTML content: %(mesg)s" % { "cmd": scriptname, "mesg": html_resource.errmesg }, file=sys.stderr)
			else :
				raise
		
		if "-" == switches['local'] :
			hOut = sys.stdout
		else :
			hOut = open(outfile, "w")
		
		if out_html is not None :
			print(out_html, file=hOut)
		
		if "-" != switches['local'] :
			hOut.close()
			print("%(filename)s\t%(size)d\t%(source)s:%(source_object)s" % {"filename": outfile, "size": os.stat(outfile).st_size, "source": html_resource.__class__.__name__, "source_object": html_resource.source_object})
