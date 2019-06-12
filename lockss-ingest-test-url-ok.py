#!/usr/bin/python3

import sys, os.path, fileinput, re
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
