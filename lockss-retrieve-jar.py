#!/usr/bin/python3
#
# lockss-retrieve-jar.py: Retrieve a LOCKSS Plugin JAR file for
# analysis from a given URL, optionally using a SOCKS5 proxy for
# the connection (since the LOCKSS props server probably only
# allows HTTP GET from a limited set of IP addresses). The JAR
# file will be dumped to stdout, so you will probably want to pipe
# or redirect the binary output.
#
# Usage: lockss-retrieve-jar.py --url=<URL> [--proxy=<HOST>] [--port=<PORTNUMBER>]
#
# If no proxy host is provided, the script will assume no proxy
# If no proxy port is provided, the script will default to 8080
# To force a direct connection without a proxy, use --proxy=""
#
# @version 2019.0610

import sys, os.path, re
import socks, socket
import subprocess

import urllib.request

reSwitch = '--([0-9_A-z][^=]*)\s*=(.*)\s*$'

def KeyValuePair (switch) :
	ref=re.match(reSwitch, switch)
	return (ref[1], ref[2])

if __name__ == '__main__':
	script = sys.argv[0]
	script = os.path.basename(script)
	
	defaults = {"proxy": "", "port": 8080, "tunnel": "", "tunnel-port": 22}
	switches = dict([ KeyValuePair(arg) for arg in sys.argv if re.match(reSwitch, arg) ])
	switches = {**defaults, **switches}

	sys.argv = [ arg for arg in sys.argv if not re.match(reSwitch, arg) ]

	if len(switches['proxy']) > 0 :
		socks.set_default_proxy(socks.SOCKS5, switches['proxy'], int(switches['port']))
		socket.socket = socks.socksocket

	errmesg = ""
	
	try :
		blob = urllib.request.urlopen(switches['url']).read()
	except urllib.request.HTTPError as e :
		errmesg = "HTTP ERROR " + str(e.code) + " " + e.reason
		if 403 == e.code :
			errmesg = errmesg + ". Do you need to connect through a proxy? / Usage: " + sys.argv[0] +  " --url=[<URL>] --proxy=[<PROXYHOST>] --port=[<PORT>]"
	except urllib.request.URLError as e :
		mesg = "URL: <Unrecognized Error>"
		if isinstance(e.reason, str) :
			errmesg = "URL Error: " + e.reason
		elif isinstance(e.reason, socks.ProxyConnectionError) :
			errmesg = "PROXY FAILURE: " + e.reason.msg
			errmesg = errmesg + ". Do you need to set up the proxy connection?"
	except Exception as e :
		mesg = "<Unrecognized Exception>"

	if len(errmesg) > 0 :
		print("[" + script + "] error: " + errmesg, file=sys.stderr)
	else :
		sys.stdout.buffer.write(blob)
