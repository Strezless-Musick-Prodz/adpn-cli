#!/usr/bin/python3

import sys, os.path, fileinput, re
import urllib.request

if __name__ == '__main__' :
	for line in fileinput.input() :
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
