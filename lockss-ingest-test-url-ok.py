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

reSwitch = '--([0-9_A-z][^=]*)(\s*=(.*)\s*)?$'

def KeyValuePair (switch) :
	ref=re.match(reSwitch, switch)
	return (ref[1], ref[3])

if __name__ == '__main__' :

	switches = dict([ KeyValuePair(arg) for arg in sys.argv if re.match(reSwitch, arg) ])
	sys.argv = [ arg for arg in sys.argv if not re.match(reSwitch, arg) ]

	if len(sys.argv) > 1 :
		input = fileinput.input(files=sys.argv[1:2])
	else :
		input = fileinput.input()

	for line in input :
		cols = line.rstrip().split("\t")
		prop = cols[0]
		url = cols[1]

		code = 200 # OK
		try :
			page = urllib.request.urlopen(cols[1]).read().rstrip
		except urllib.request.HTTPError as e :
			code = e.code
			errmesg = e.reason
		except urllib.request.URLError as e :
			code = -1
			errmesg = e.reason
		
		if 200 == code :
			print("200 OK", "\t", cols[0], "\t", cols[1], "\t", cols[2])
			code = 0
		else :
			print(str(code) + " " + errmesg, "\t", cols[0], "\t", cols[1], "\t", cols[2])
		
		sys.exit(code)
