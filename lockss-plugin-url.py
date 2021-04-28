#!/usr/bin/python3
#
# lockss-plugin-url.py: Extract and report URL(s) for one or more LOCKSS Plugin JAR packages.
#
# @see LockssPluginDetails.__doc__ for usage notes
# @version 2019.0610

import sys, fileinput, re, json, os.path
import urllib.request, urllib.parse, socket, html
from bs4 import BeautifulSoup
from getpass import getpass
from functools import reduce

from myLockssScripts import myPyCommandLine

class LockssPluginDetails :
	"""
Usage: lockss-plugin-url.py [<XML>] [--help]
	[--daemon=<HOST>|--url=<URL>] [--user=<NAME>] [--pass=<PASSWORD>]
	[--plugin=<NAME>|--plugin-regex=<PATTERN>|--plugin-keywords=<WORDS>|--plugin-id=<FQCN>]

Retrieves the URL for one given LOCKSS Publisher Plugin, based on the Plugin's
human-readable title, or a list of all of the avaliable LOCKSS Publisher Plugins, with
human-readable title and JAR URL. The result will be printed out to stdout. 

	--help                   	display these usage notes
	--daemon=<HOST>          	get info from LOCKSS Daemon at host <HOST>
	--url=<URL>              	get info from Publisher Plugins page located at <URL>
	--user=<NAME>           	use <NAME> for HTTP Auth when retrieving plugin details
	--password=<PASS>         	use <PASS> for HTTP Auth when retrieving plugin details
	--plugin=<NAME>         	display URL for the plugin whose human-readable name exactly matches <NAME>
	--plugin-regex=<PATTERN> 	display URL for the plugin name matching <PATTERN>
	--plugin-keywords=<WORDS> 	display URL for the plugin name containing keywords <WORDS>
	--plugin-id=<FQCN>       	display URL for the plugin whose ID is <FQCN>

If no Daemon URL is provided using --daemon or --url then the script will attempt to
read an XML or HTML Plugin listing from a local file. If no file name is provided, then
the script will try to read the HTML or XML listing from stdin.

If no HTTP username or password is provided on the command line, but the daemon requires
HTTP Authentication credentials, the script will prompt the user for the missing username
or password on stderr.
	"""

	def __init__ (self, script: str, switches: dict = {}) :
		self._switches = switches
		self._soup = None
		self._script = script

	@property
	def script (self) :
		return self._script

	@property
	def switches (self) :
		return self._switches

	@property
	def soup (self) :
		return self._soup
	
	@soup.setter
	def soup (self, soup) :
		self._soup = soup
		
	def daemon_url (self) :
	
		url = None
		if ('daemon' in self.switches and not 'url' in self.switches) :
            if len(self.switches['daemon']) > 0 :
                daemonHost = urllib.parse.urlparse(self.switches['daemon'])
            else :
                daemonHost = urllib.parse.urlparse("http://localhost:8081")
            
            if ( daemonHost.netloc ) :
                daemonUrl = ( daemonHost.geturl() )
            else :
                daemonUrl = ( "http://%(daemon)s/" % self.switches )
            daemonPath = 'DaemonStatus?table=%(table)s&key=%(key)s&output=%(output)s'
			
			url = urllib.parse.urljoin(
                daemonUrl,
				(daemonPath % {'table': 'Plugins', 'key': '', 'output': 'xml'})
			)
		elif 'url' in self.switches :
			url = self.switches['url']
			
		return url

	def read_daemon_data (self) :
		if not (self.daemon_url() is None) :
			blob = self.get_from_url(self.daemon_url())
		elif len(sys.argv) > 1 :
			blob = ''.join(fileinput.input())
		else :
			print("[%(script)s] Reading Plugins XML/HTML list from stdin" % {"script": script}, file=sys.stderr)
			blob = ''.join(fileinput.input())
	
		return blob

	def get_username (self) :
		"""Return a Username for scripted HTTP Authentication
		
		Returns the Username to be used in an HTTP Authentication handshake for the HTTP
		GET request sent by {@see LockssPluginDetails.get_from_url_with_authentication}
		This uses a value taken from the command line or default switches if available.
		If nothing is available from switches, it prints a prompt to stderr and reads the
		username from stdin.
		
		@return str a username for HTTP Authentication (e.g.: "User.Name")
		"""
		return self.get_auth_parameter("user", "HTTP Username", input)

	def get_passwd (self) :
		"""Return a Password for scripted HTTP Authentication

		Returns the Password to be used in an HTTP Authentication handshake for the HTTP
		GET request sent by {@see LockssPluginDetails.get_from_url_with_authentication}
		This uses a value taken from the command line or default switches if available.
		If nothing is available from switches, it prints a prompt to stderr and reads the
		password from stdin.

		@return str a password for HTTP Authentication (e.g.: "ChangeThisPassword")
		"""
		return self.get_auth_parameter("pass", "HTTP Password", getpass)

	def get_realm (self) :
		"""Return a Realm for scripted HTTP Authentication

		Returns the Realm to be used in an HTTP Authentication handshake for the HTTP
		GET request sent by {@see LockssPluginDetails.get_from_url_with_authentication}
		This uses a value taken from the command line or default switches if available.
		If nothing is available from switches, it prints a prompt to stderr and reads the
		password from stdin.

		@return str a realm for HTTP Authentication (e.g.: "LOCKSS Admin")
		"""
		return self.get_auth_parameter("realm", "HTTP Authentication Realm", input)		
	
	def get_auth_parameter (self, key: str, title: str, inputFunction: "function") -> str :
		"""Return a parameter for scripted HTTP Authentication
		
		Returns a parameter required for the HTTP Authentication handshake (e.g. username,
		password, or realm) on a scripted HTTP 	GET request sent by
		{@see LockssPluginDetails.get_from_url_with_authentication}. This uses a value
		taken from the command line or default switches if available. If nothing is
		available from switches, it redirects stdout to stderr, prints a prompt to the
		user console, and uses the provided console input function to read input from the
		user.

		@uses sys.stdout
		@uses sys.stderr
		
		@param str key the name of the switch to check for a value (e.g.: "user", "pass", "realm")
		@param str title The human-readable title. Used as a console input prompt if the
			value was not provided on command line or in default switches.
		@param function inputFunction The console input function used to read a value from
			the user console, if necessary.
			(E.g.: input for parameters that can be	displayed in cleartext,
			getpass for parameters that should not be.)
		@return str The parameter value retrieved from switches or from the user console.
		"""
		if key in self.switches :
			param = self.switches[key]
		else :
			old_stdout = sys.stdout
			try :
				sys.stdout = sys.stderr
				param = inputFunction("%(title)s: " % {"title": title})
			finally :
				sys.stdout = old_stdout
		
		return param
		
	def get_from_url (self, url) :
		"""Retrieve data from a resource using HTTP GET

		Send an HTTP GET request to the resource located at a given URL, and return the body of the response
		If HTTP Authentication is required, fall back on self.get_from_url_with_authentication()
		If non-Authentication related HTTP errors are returned, raise an exception or display an error message
		
		@uses urllib.request.urlopen
		
		@param str url The URL to send a GET request to
		@return str the entire contents of the HTTP response body
		"""

		try :
			if (self.switches['debug']) :
				print("[dbg] html=urllib.request.urlopen(url).read()", file=sys.stderr)
				print("[dbg] url=", url, file=sys.stderr)
			html = urllib.request.urlopen(url).read()
		except urllib.error.HTTPError as e :
			if 401 == e.code :
				if (self.switches['debug']) :
					print("[dbg] html = self.get_from_url_with_authentication(url)", file=sys.stderr)
					print("[dbg] url=", url, file=sys.stderr)
				html = self.get_from_url_with_authentication(url)
			else :
				raise

		return html
		
	def get_from_url_with_authentication (self, url) :
		"""Retrieve data from a resource using HTTP GET with HTTP Basic Authentication
		
		Send an HTTP GET request to the resource located at a given URL using HTTP Basic Authentication
		Return the body of the response. If the return is a network error or an HTTP
		client or server error code (400-599, etc.), then use LockssPluginDetails.do_handle_error
		to raise an exception or print out an error code.
		
		@param str url The URL to send a GET request to. Authentication credentials and realm are kept in user switches.
		@return str the entire contents of the HTTP response body
		"""
		user = self.get_username()
		passwd = self.get_passwd()
		auth_realm = self.get_realm()
		
		auth_handler = urllib.request.HTTPBasicAuthHandler()
		auth_handler.add_password(realm=auth_realm, uri=url, user=user, passwd=passwd)
		opener = urllib.request.build_opener(auth_handler)
		
		urllib.request.install_opener(opener)

		try :
			html = urllib.request.urlopen(url).read()
		except urllib.error.HTTPError as e :
			raise
			
		return html

	def get_soup_jars (self, blob = None) -> dict :
		"""Parse LOCKSS Daemon Plugin listing page into a dictionary from names to Plugin Details

		Parses XML or HTML contained in blob, presumably returned by the LOCKSS Daemon's
		query API, and returns a dictionary mapping the human-readable name of the Plugin
		to a row of Plugin Details including the URL of the JAR package, a unique ID code,
		etc. etc.

		@param str blob
		@return dict
		"""
		if not (blob is None) :
			self.soup = BeautifulSoup(blob, 'html.parser')
			
		if len(self.soup.find_all('html')) :
			pluginJars = self.get_html_scrape_jars()
		elif len(self.soup.find_all('st:table')) :
			pluginJars = self.get_xml_jars()
		else :
			raise ValueError('No XML/HTML available to scrape for Plugins.')
		
		return pluginJars
		
	def get_xml_jars (self) :
		cols = { }
		pluginJars = { }

		url = self.daemon_url()
		
		tablename = self.soup.find('st:name')
		if "Plugins" == tablename.text :
			col = 0
			for tr in self.soup.find_all('st:row') :
				for td in tr.find_all('st:cell') :
					th = td.find('st:columnname').text
					table = ''
					key = ''
					if 'plugin' == th :
						table = td.find('st:name').text
						key = td.find('st:key').text
						
						daemonurl = urllib.parse.urlsplit(url)
						
						iq = urllib.parse.parse_qs(daemonurl.query)
						oq = { }
						
						oq['table'] = [ table ]
						oq['key'] = [ key ]
						oq['output'] = iq['output']
						
						oquery = urllib.parse.urlencode(oq, doseq=True)
						
						# list elements: scheme, netloc, path, params, query, fragment
						linkedurl = urllib.parse.urlunparse([daemonurl.scheme, daemonurl.netloc, daemonurl.path, '', oquery, ''])

						# retrieve URL of JAR file
						try :
							subxml = self.get_from_url(linkedurl)
						except urllib.error.HTTPError :
							subxml = ''
					
						props = LockssPropertySheet(subxml)
						
						if 'URL' in props :
							Name = props['Name']
							pluginJars[Name] = props
						
					# end for link
				# end for td
			# end for tr
		# end for form
		
		return pluginJars

	def get_html_scrape_jars (self) :
		forms = self.soup.find_all('form')

		url = self.daemon_url()
		
		cols = { }
		pluginJars = { }

		for form in forms :
			for tr in form.find_all('tr') :
				col = 0
				for td in tr.find_all('td') :
					elClass = ''
					if 'class' in td.attrs :
						elClass = ''.join(td.attrs['class'])
					
					if elClass == 'colhead' :
						cols[col] = td.text
					elif col in cols :
						th = cols[col]
						
						links = [ link for link in td.find_all('a') if ('Name' == th) ]

						# retrieve URL of JAR file
						for link in links :
						
							href = urllib.parse.urljoin(url, link.attrs['href'])
							
							try :
								subhtml = urllib.request.urlopen(href).read()
							except urllib.error.HTTPError :
								subhtml = ''
						
							props = LockssPropertySheet(subhtml)
							
							if 'URL' in props :
								pluginJars[td.text] = props
							
						# end for link
						
					col = col + 1
				# end for td
			# end for tr
		# end for form
		
		return pluginJars

	def display_usage (self) :
		print(self.__doc__)
		sys.exit(0)

	def template_list (self, count: int) -> tuple:
		open = ""
		close = ""
		
		if self.switches['output']=='text/html' and count > 0 :
			open = "<ol>";
			close = "</ol>"
		
		return (open, close)
		
	def template (self, link: tuple, count: int) -> tuple:
		esc = lambda text, place: text
		if self.switches['output']=='text/tab-separated-values' :
			if count > 1 :
				line="%(name)s\t%(url)s"
			else :
				line="%(url)s"
		elif self.switches['output']=='text/html' :
			esc = lambda text, place: html.escape(text)
			line='<li><a href="%(url)s">%(name)s</a></li>'
		
		return (line, esc)
		
	def display (self, urls: list) :
	
		if len(urls)==1 :
			exitcode=0
		elif len(urls) > 1 :
			exitcode=2
		else :
			criteria = dict([ (key, self.switches[key]) for key in self.switches if re.match('plugin(-[A-Za-z0-9]+)?', key, re.I) ])
			
			print("[%(script)s] No Plugins found matching criteria: " % {"script": self.script}, criteria, file=sys.stderr)
			line = ""
			exitcode=1
		
		(open, close) = self.template_list(len(urls))
		
		if len(open) > 0 :
			print(open)
			
		for pair in urls :
			(line, esc) = self.template(pair, len(urls))
			print(line % {"name": esc(pair[0], "name"), "url": esc(pair[1], "url")})
			
		if len(close) > 0 :
			print(close)
			
		sys.exit(exitcode)
	
	def display_error (self, text, exitcode) :
		print("[%(script)s] %(message)s" % { "script": self.script, "message": text }, file=sys.stderr)
		if exitcode >= 0 :
			sys.exit(exitcode)
			
	def do_output_http_error (self, e: urllib.error.HTTPError) :
		mesg = "HTTP Error: %(code)d %(reason)s"
		if 401 == e.code :
			mesg = "Authentication error: %(reason)s"
		exitcode = (e.code - 200) % 256
		self.display_error(mesg % {"code": e.code, "reason": e.reason}, exitcode)

	def execute (self) :
		pluginJars = {}
		try :
			if (self.switches['debug']) :
				print("[dbg] blob=self.read_daemon_data()", file=sys.stderr)
			blob=self.read_daemon_data()
			if (self.switches['debug']) :
				print("[dbg] self.get_soup_jars(blob)", file=sys.stderr)
			pluginJars = self.get_soup_jars(blob)
		except FileNotFoundError as e :
			self.display_error(str(e), -1)
		except ValueError as e :
			self.display_error(str(e), -1)
		except urllib.error.HTTPError as e:
			self.do_output_http_error(e)
		except urllib.error.URLError as e:
			message = str(e.reason)
			exitcode = 255
			if isinstance(e.reason, socket.gaierror) :
				message = ("Socket Error %d: %s" % e.reason.args)
				exitcode = e.reason.args[0]
			self.display_error(message, exitcode)

		if (self.switches['debug']) :
			print("[dbg] checking plug_matchers", file=sys.stderr)
		
		plug_matchers = {
			'*': lambda name, row: True,
			'plugin': lambda name, row: (name.upper()==switches['plugin'].upper()),
			'plugin-regex': lambda name, row: re.search(switches['plugin-regex'], name, re.I),
			'plugin-keywords': lambda name, row: logical_product(map(make_keyword_match(name), switches['plugin-keywords'].split())),
			'plugin-id': lambda name, row: (row['Id']==switches['plugin-id']),
		}
		criteria = [ key for key in switches if re.match('plugin(-[A-Za-z0-9])?', key, re.I) ] + [ '*' ]
	
		plug_match = plug_matchers[criteria[0]]
	
		urls = [ (pluginName, pluginJars[pluginName]['URL'] ) for pluginName in pluginJars.keys() if plug_match(pluginName, pluginJars[pluginName]) ]
	
		self.display(urls)

def LockssPropertySheet (blob) :
	stew = BeautifulSoup(blob, 'html.parser')
	
	cols = { }
	if len(stew.find_all('html')) > 0 :
		forms = stew.find_all('form')

		for form in forms :
			formtables = form.find_all('table')
			for table in formtables :
				trs = table.find_all('tr')
				for tr in trs :
					tds = tr.find_all('td')
					if len(tds) == 2 :
						keyvalue = [ td.text for td in tds ]
						key = ''.join([c for c in keyvalue[0] if c.isalpha()])
						value = keyvalue[1]
						cols[key] = value

	elif len(stew.find_all('st:table')) > 0 :
		tableName = stew.find('st:name').text
		if ('PluginDetail' == tableName) :
			for td in stew.find_all('st:summaryinfo') :
				key = td.find('st:title').text
				value = td.find('st:value').text
				cols[key] = value
				
	return cols

def logical_product(sequence) :
	return reduce(lambda carry, found: (carry and (not not found)), sequence, True)

def keyword_match(keyword, text) :
	return re.search('\\b' + re.escape(keyword), text, re.I);

def make_keyword_match (text) :
	return lambda keyword: keyword_match(keyword, text)
	
if __name__ == '__main__':
	
	scriptname = sys.argv[0]
	scriptname = os.path.basename(scriptname)

	(sys.argv, switches) = myPyCommandLine(sys.argv, defaults={
		"output": "text/tab-separated-values",
		"realm": "LOCKSS Admin",
		"debug": 0
	}).parse()

	script = LockssPluginDetails(scriptname, switches)	
	if ('help' in switches) :
		script.display_usage()
	else :
		script.execute()
