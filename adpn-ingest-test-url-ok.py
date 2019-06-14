#!/usr/bin/python3
#
# lockss-ingest-test-url-ok.py: send an HTTP GET to a URL provided on stdin, then return
# an exit code and a diagnostic printed to stdout based on whether or not we get
# back an HTTP 200 OK.
#
# Optionally, the request can be sent through a SOCKS proxy to test the HTTP connection
# from a different origin IP address.
#
# Usage: <input> | lockss-ingest-test-url-ok.py [<INPUTFILE>] [--proxy=<HOST>] [--port=<PORT>]
#
# 	--help			display these usage notes
# 	--proxy=<HOST> 	host name of SOCKS5 proxy, if any (localhost for SSH tunnels)
# 	--port=<PORT> 	port number for SOCKS5 proxy, if any
#
# Input provided on stdin or in a text input file on the command line is expected
# to be one or more lines of plain text. The lines may be simple unseparated text, or they
# may be tab-separated value fields. If there are no tabs, the URL is assumed to be the
# ENTIRE line. If there are tabs, then the URL is assumed to be in the SECOND field.
#
# Output sent to stdout consists of a table of tab-separated values:
#
# 	field 0: (int) the HTTP response code from the web server, or a magic error code (>=600)
# 		in case of network errors that prevented the HTTP connection from completing
# 	field 1: (str) a diagnostic message related to the response code
# 	field 2: (str) the property name with which the URL was associated (if none, "url" is used)
# 	field 3: (str) the URL tested
# 	field 4: (str) any additional data that was provided in the TSV input
#
# e.g.:
#
# 		200 	OK 	 au_start_url    http://archives.alabama.gov/Lockss/WPA-Folder-01/       "%s%s/", base_url, subdirectory
#
# @return 0 on a successful HTTP GET request (200 OK)
# 	non-zero error codes in case of unsuccessful HTTP requests, based on (http_code - 200) % 256
# 	e.g.:
# 		203 = HTTP 403, Forbidden
# 		204 = HTTP 404, Not Found
# 		 44 = HTTP 500, Internal Server Error
# 
# @version 2019.0612

import sys, os.path, fileinput, re
import socks, socket
import urllib.request

from myLockssScripts import myPyCommandLine

if __name__ == '__main__' :

	######################################################################################
	## COMMAND LINE: pull switches out of sys.argv, parse into switches: dict ############
	######################################################################################
	
	script = sys.argv[0]
	script = os.path.basename(script)

	(sys.argv, switches) = myPyCommandLine(sys.argv, defaults={"proxy": "", "port": -1}).parse()

	######################################################################################
	## PROXY: if --proxy/--port are provided, connect to SOCKS5 proxy and monkeypatch ####
	######################################################################################
	
	if len(switches['proxy']) > 0 :
		socks.set_default_proxy(socks.SOCKS5, switches['proxy'], int(switches['port']))
		socket.socket = socks.socksocket
		
	######################################################################################
	## INPUT: read URLs line-by-line from stdin or from INPUTFILE ########################
	######################################################################################
	
	if len(sys.argv) > 1 :
		input = fileinput.input(files=sys.argv[1:2])
	else :
		input = fileinput.input()

	exitcode = 0 # assume success
	for line in input :
		cols = line.rstrip().split("\t", maxsplit=3)
		if len(cols) > 1 :
			prop = cols[0]
			url = cols[1]
		else :
			prop = 'url'
			url = cols[0]
			
		if len(cols) > 2 :
			rest = cols[2]
		else :
			rest = ''

		##################################################################################
		## urlopen: Send HTTP GET Request and assess the response code. ##################
		##################################################################################
		
		code = 200 # OK
		try :
			page = urllib.request.urlopen(url).read()
		except urllib.request.HTTPError as e :
			code = e.code
			errmesg = e.reason
		except urllib.request.URLError as e :
			if isinstance(e.reason, str) :
				code = 601
				errmesg = e.reason
			elif isinstance(e.reason, socket.gaierror) :
				code = 602
				errmesg = "HOST FAILURE: " + str(e.reason)
			elif isinstance(e.reason, socks.ProxyConnectionError) :
				code = 603
				errmesg = "PROXY FAILURE: " + e.reason.msg
				errmesg = errmesg + ". Do you need to set up the proxy connection?"
			else :
				code = 604
				errmesg = "UNRECOGNIZED URL FAILURE: " + str(e.reason)
		except Exception as e :
			code = 605
			errmesg = "<Unrecognized Exception>"

		##################################################################################
		## OUTPUT: Print out TSV lines, [code, response, property, url, ...] #############
		##################################################################################
		
		if code == 0 :
			exitcode = (code - 200) # return an error code from first failure, if any
			
		if 200 == code :
			print("200", "\t", "OK", "\t", prop, "\t", url, "\t", rest)
		else :
			print(str(code), "\t", errmesg, "\t", prop, "\t", url, "\t", rest)
		
	sys.exit(exitcode)
