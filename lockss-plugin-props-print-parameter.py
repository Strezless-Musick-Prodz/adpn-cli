#!/usr/bin/python3

import fileinput, re, sys, json

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

	table = {}
	for line in input :
		if len(line.strip()) > 0 :
			fields = line.rstrip().split("\t")
			param=fields[1]
	
			if (re.match('^PARAM[(]', fields[0])) :
				key=fields[2]
				value=fields[1]
			else :
				key=fields[0]
				value=fields[1]

			if ('output' in switches) and ('application/json' == switches['output']) :
				table[key] = value
			else :
				print(key.upper() + ":\t" + value)
		
	if ('output' in switches) and ('application/json' == switches['output']) :
		print(json.dumps(table))
