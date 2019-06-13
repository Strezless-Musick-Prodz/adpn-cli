#!/usr/bin/python3
#
# lockss-plugin-props-print-parameter.py: accept a list of tab-separated values
# representing key-value pairs of LOCKSS Plugin properties and parameters, reformat it
# according to scripting needs and print it out in the desired format.
#
# Usage: <input> | lockss-plugin-props-print-parameter.py [--output=<FORMAT>]
#
# 	--output=<FORMAT> 	MIME-type of format for output.
# 						Supported formats: text/plain, application/json
#
# Input: text/tab-separated values, usually piped output from lockss-plugin-props.py
#
# @version 2019.0612

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
	params = []
	for line in input :
		if len(line.strip()) > 0 :
			fields = line.rstrip().split("\t", maxsplit=3)
			param=fields[1]
	
			if (re.match('^PARAM[(]', fields[0])) :
				key=fields[2]
				value=fields[1]
				
				parameter_mapping = value.split("=", maxsplit=2)
				if len(parameter_mapping) > 1 :
					parameter_mapping[1] = json.loads(parameter_mapping[1])
					
				params = params + [parameter_mapping]
				
			else :
				key=fields[0]
				value=fields[1]

			if ('output' in switches) and ('application/json' == switches['output']) :
				table[key] = value
			else :
				print(key.upper() + ":\t" + value)
		
	if ('output' in switches) and ('application/json' == switches['output']) :
		table["parameters"] = params
		print(json.dumps(table))
