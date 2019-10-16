#!/usr/bin/python3
#
# lockss-retrieve-jar.py: Retrieve a LOCKSS Plugin JAR file for
# analysis from a given URL, optionally using a SOCKS5 proxy for
# the connection (since the LOCKSS props server probably only
# allows HTTP GET from a limited set of IP addresses). The JAR
# file will be dumped to stdout, so you will probably want to pipe
# or redirect the binary output.
#
# Usage: lockss-retrieve-jar.py --url=<URL> [--proxy=<HOST>] [--port=<NUMBER>]
# 			[--tunnel=<HOST>] [--tunnel-port=<NUMBER>]
#
# 	--url=<URL>		the URL of the JAR package to retrieve
#
# 	--proxy=<HOST> 	the hostname of a SOCKS5 proxy to use in contacting host for HTTP GET
# 	--port=<NUMBER>	a port number for the SOCKS5 proxy to use with --proxy=<HOST>
# 		If you are using ssh tunneling for your proxy, these should probably be
# 		--proxy="localhost" and a high free port number, e.g. --port=31415
# 		If --proxy is omitted, the script assumes no proxy
#		If --port is omitted, it defaults to port 8080
#
# 	--tunnel=<HOST> the hostname of a remote host providing SSH tunnels to a SOCKS5 proxy
# 	--tunnel-port=<NUMBER> 	a port number for the **SSH connection** to the remote tunnel
# 		This should be a remote ssh host and a valid port number for ssh connections,
# 		e.g. --tunnel=adpnadah.alabama.gov --tunnel-port=22
# 		If --tunnel is omitted, the host assumes no tunneling
# 		If --tunnel-port is omitted, it defaults to port 22
#
# @version 2019.0614

import sys, os.path, re
import socks, socket
import subprocess

import urllib.request

from myLockssScripts import myPyCommandLine

if __name__ == '__main__':
	script = sys.argv[0]
	script = os.path.basename(script)
	
	(sys.argv, switches) = myPyCommandLine(sys.argv, defaults={
		"url": "", 
		"proxy": "", "port": 8080,
		"tunnel": "", "tunnel-port": 22
	}).parse()

	if len(switches['proxy']) > 0 :
		socks.set_default_proxy(socks.SOCKS5, switches['proxy'], int(switches['port']))
		socket.socket = socks.socksocket

	firstTry = True
	retry = False

	blob = ""
	
	while firstTry or retry :
		errmesg = ""
		firstTry = False
		retry = False

		try :
			blob = urllib.request.urlopen(switches['url']).read()
		except urllib.request.HTTPError as e :
			errmesg = "HTTP ERROR " + str(e.code) + " " + e.reason
			if 403 == e.code :
				errmesg = errmesg + ". Do you need to connect through a proxy? / Usage: " + sys.argv[0] +  " --url=[<URL>] --proxy=[<PROXYHOST>] --port=[<PORT>]"
		except urllib.request.URLError as e :
			errmesg = "URL: <Unrecognized Error>"
			if isinstance(e.reason, str) :
				errmesg = "URL Error: " + e.reason
			elif isinstance(e.reason, socks.ProxyConnectionError) :
				errmesg = "PROXY FAILURE: " + e.reason.msg

				if not retry and len(switches["tunnel"]) > 0 :
					retry = True
				else :
					errmesg = errmesg + ". Do you need to set up the proxy connection?"
					
		except Exception as e :
			errmesg = "<Unrecognized Exception> (" + e.__class__.__name__ + ") " + str(e.args) + " " + str(e.__context__)

		if retry :
			diag = "[%(script)s] %(errmesg)s. Trying to open SSH tunnel [%(tunnel)s]..." % {"script": script, "errmesg": errmesg, "tunnel": switches['tunnel']}
			
			print(diag, file=sys.stderr)
		
			fail=subprocess.call(["ssh", "-f", switches["tunnel"], "-D" + str(switches['port']), "sleep 3600"], stdout=sys.stderr);
		
			if fail :
				print("Exit code: " + str(fail), file=sys.stderr)
				retry = False
	
	exitcode = 0
	if len(errmesg) > 0 :
		print("[" + script + "] error: " + errmesg, file=sys.stderr)
		exitcode = 1
	elif len(blob) == 0 :	
		print("[" + script + "] error: empty result", file=sys.stderr)
		exitcode = 255
	else :
		sys.stdout.buffer.write(blob)
	sys.exit(exitcode)