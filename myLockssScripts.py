#!/usr/bin/python3
#
# myLockssScripts: utility classes for use across various ADPNet/LOCKSS automation scripts
# Regularizing the use of key-value pair switches, JSON input, etc.
#
# @version 2019.0624

import sys
import os.path
import re
import json
import fileinput
import subprocess
from subprocess import PIPE

import base64
from Cryptodome.PublicKey import RSA
from Cryptodome.Random import get_random_bytes
from Cryptodome.Cipher import AES, PKCS1_OAEP

class myPyPipeline :
	"""Given a sequence of shell processes, pipe output from one to input for the next, using POSIX pipes.
	
	@param iterable pipeline an iterable sequence of lists specifying shell commands with command-line parameters
	"""
	def __init__ (self, pipeline) :
		self.pipeline = pipeline
	
	def process (self, cmd, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr, encoding="utf-8") :
		if callable(cmd) :
			res=cmd(stdin=stdin, stdout=stdout, stderr=stderr, encoding=encoding)
		else :
			res=subprocess.Popen(cmd, stdin=stdin, stdout=stdout, stderr=stderr, encoding=encoding)
		return res
		
	def siphon (self, encoding="utf-8", stdin=sys.stdin) :
		processes = []
		piped_in = stdin if type(stdin) is str or type(stdin) is bytes else None
		_stdin = stdin if piped_in is None else PIPE
		for cmd in self.pipeline :
			proc = self.process(cmd=cmd, stdin=_stdin, stdout=PIPE, encoding=encoding)
			_stdin = proc.stdout
			processes.append(proc)
		
		_lastproc = None
		for proc in processes :
			if _lastproc is None :
				if piped_in is not None :
					proc.communicate(input=piped_in)
			else :
				_lastproc.stdout.close()
			_lastproc = proc
		
		(buf, errbuf) = _lastproc.communicate()
		_lastproc.stdout.close()
		
		return (buf, errbuf, [proc.returncode for proc in processes])

def align_switches (left, right, switches, override=True) :
    if switches[left] is None :
        switches[left] = switches[right]
    if switches[right] is None :
        switches[right] = switches[left]
    if override :
        if switches[right] != switches[left] :
            switches[right] = switches[left]

def shift_args (args: list) -> tuple :
    top = args[0] if len(args) > 0 else None
    remainder = args[1:] if len(args) > 1 else []
    return ( top, remainder )

class myPyCommandLine :
	"""Parse a Unix-style shell command-line, separating out configuration parameters and files/objects.
	"""
	
	def __init__ (self, argv: list = [], defaults: dict = {}, configfile: str = "", alias: dict = {}, settingsgroup = "") :
		"""Initialize with a list of command-line arguments, and optionally a dictionary of default values for expected configuration switches."""
		self._argv = argv
		self._switches = {}
		
		jsonText = "{}"
		if len(configfile) > 0 :
			try :
				default_map = open(configfile, "r")
				jsonText = "".join([line for line in default_map])
				default_map.close()
			except FileNotFoundError as e :
				jsonText = "{}"
				
		try :
			self._defaults = {**defaults, **json.loads(jsonText)}
		except json.decoder.JSONDecodeError as e :
			self._defaults = defaults
		
		if len(settingsgroup) > 0 :
			overlay = { }

			if not isinstance(settingsgroup, list) :
				settingsgroup = [ settingsgroup ]

			for key in self._defaults.keys() :
				subkey = key.split("/", maxsplit=2)
				if len(subkey) > 1 and settingsgroup.count(subkey[0]) > 0 :
					overlay[subkey[1]] = self._defaults[key]
			
			self._defaults = {**self._defaults, **overlay}
		
		self._alias = alias
		
		self._switchPattern = '--([0-9_A-z][^=]*)(\s*=(.*)\s*)?$'

	@property 
	def pattern (self) -> str :
		"""Provides a regex that matches a command-line switch and parse out switch names and values."""
		return self._switchPattern

	@property
	def argv (self) -> list :
		"""List of files and objects from the command line, without --switches.
		"""
		return self._argv
	
	@property
	def switches (self) -> dict :
		"""Dictionary of configuration switches provided on command-line or in defaults.
		"""
		return self._switches
		
	def KeyValuePair (self, switch) -> tuple :
		"""Parses a string command-line switch into a (key, value) pair.

		Switches may be a parameter name and value (e.g. '--output=html' -> ('output', 'html')
		or they may be a simple setting name (e.g. '--turned-on' -> ('turned-on', 'turned-on')
		"""
		ref=re.match(self.pattern, switch)
	
		key = ref.group(1)
		if ref.group(3) is None :
			value = ref.group(1)
		else :
			value = ref.group(3)
	
		return (key, value)

	def parse (self, argv: list = [], defaults: dict = {}) -> tuple :
		"""Separate out a list of command-line arguments into switches and files/objects.
		"""
		if len(argv) > 0 :
			the_argv = argv
		else :
			the_argv = self.argv
		
		switches = dict([ self.KeyValuePair(arg) for arg in the_argv if re.match(self.pattern, arg) ])
		switches = {**self._defaults, **defaults, **switches}
		
		for (primary, secondary) in self._alias.items() :
			if switches.get(primary) is None :
				if switches.get(secondary) is not None :
					switches[primary] = switches.get(secondary)
			if switches.get(primary) is not None :
				switches[secondary] = switches.get(primary)
		
		argv = [ arg for arg in the_argv if not re.match(self.pattern, arg) ]
		
		self._argv = argv
		self._switches = switches
		
		return (argv, switches)
	
	def compose (self, keyvalues: list) -> list :		
		return self.argv + [ "--%(k)s=%(v)s" % {"k": key, "v": value} for key, value in keyvalues if not value is None ]
		

class myPyJSON :
	"""Extract JSON hash tables from plain-text input, for example copy-pasted or piped into stdin.
	"""
	
	def __init__ (self, splat=True, cascade=False, where=None) :
		"""Initialize the JSON extractor pattern."""
		self._jsonPrologRE = r'^JSON(?:\s+(?:PACKET|DATA))?:\s*'
		self._jsonPrologText = 'JSON: '
		self._jsonBraces = r'^\s*([{].*[}]|\[.*\])\s*'
		self._jsonRaw = ''
		self._jsonText = [ ]
		self._splat = splat
		self._cascade = cascade
		self.select_where(where)
		
	@property
	def prolog (self) :
		"""Regex that matches and parses out the JSON representation from a line of text."""
		return self._jsonPrologRE
	
	@property
	def prologText (self) :
		"""Plain text that will match against the myPyJSON.prolog regex."""
		return self._jsonPrologText
		
	@property
	def braces (self) :
		"""Regex that matches and parses out a likely JSON hashtable or array from a line of text."""
		return self._jsonBraces
		
	@property
	def splat (self) :
		"""Switch for splatting (or not) single item lists into their first unit."""
		return self._splat
		
	@property
	def cascade (self) :
		"""Switch for joining (or not) multiple data items in a first-to-last cascade or list them separately."""
		return self._cascade
	
	@property
	def selected (self) :
		"""Lambda that filters JSON data objects according to programmatic criteria."""
		return self._where
	
	@property
	def raw (self) -> str :
		return self._jsonRaw

	@property
	def json (self) -> list :
		"""List of all the JSON representations taken from the accepted input."""
		return self._jsonText
	
	@property
	def data (self) -> "list of dict" :
		"""A list of all the hash tables parsed from the JSON representations."""
		return [ json.loads(marble) for marble in self.json ]
	
	@property
	def text (self) :
		return self._jsonText
		
	@property
	def allData (self) :
		"""A unified hash table that either lists or merges together all the tables parsed from the JSON representations."""
		data = {
			"splat": { "used": False, "data": [ ] },
			"hashes": { "used": 0, "data": { } },
			"lists": { "used": 0, "data": [ ] }
		}
		
		for datum in self.data :
			if self.selected(datum) :
				if self.cascade :
					if isinstance(datum, dict) :
						data["hashes"]["data"] = {**data["hashes"]["data"], **datum}
						data["hashes"]["used"] = True
					elif isinstance(datum, list) :
						data["lists"]["data"].extend(datum)
						data["lists"]["used"] = True
				else :
					data["splat"]["used"] = True
					data["splat"]["data"].extend( [ datum ] )
			
		splat = [ self.splatted(data[glob]["data"]) for glob in data.keys() if data[glob]["used"] ]
		return self.splatted(splat)

	def select_where (self, condition=None) :
		self._where = condition if condition is not None else lambda x: True
		
	def splatted (self, data, force=False) :
		splat = data
		if force or self.splat :
			if isinstance(data, list) :
				if len(data) == 0 :
					splat = None
				elif len(data) == 1 :
					splat = data[0]
				else :
					splat = data

		return splat
	
	def add_prolog (self, line) :
		if re.match(self.prolog, line, flags=re.I) :
			output=line
		else :
			output=( "%(prolog)s%(line)s" % { "prolog": self.prologText, "line": line } )
		return output
		
	def is_acceptable (self, line) :
		is_prologged = re.match(self.prolog, line, flags=re.I)
		is_braces = False
		maybe_braces = re.match(self.braces, line, flags=re.I)
		if maybe_braces :
			try :
				json.loads(line)
				is_braces = True
			except json.decoder.JSONDecodeError as e :
				is_braces = False
		return ( is_prologged or is_braces )
		
	def accept (self, jsonSource, screen=False) :
		"""Accept the plain-text input containing one or more JSON hash tables within the text.
		
		jsonSource can be a string, or an iterable object that spits out lines of text
		(for example, flieinput.input()).
		"""
		self._jsonRaw = ( jsonSource if isinstance(jsonSource, str) else "\n".join(jsonSource) )

		if screen :
			if isinstance(jsonSource, str) :
				split_src = [ jsonSource ]
			else :
				split_src = jsonSource
			self._jsonText = [ self.add_prolog(bit) for bit in split_src if self.is_acceptable(bit) ]
		else :
			self._jsonText = jsonSource
		
		if isinstance(self._jsonText, str) :
			src = self._jsonText
		else :
			src = "\n".join(self._jsonText)

		split_src = re.split(self.prolog, src, flags=re.M)
		self._jsonText = [ bit for bit in split_src if len(bit.strip()) > 0 ]
		
		if len(self._jsonText) == 0 :
			self._jsonText = [ "".join(src) ]

class myADPNScriptSuite :

    def __init__ (self, script=None) :
        path = (script if script is not None else __file__)
        self._modpath = os.path.realpath(path)
        self._modname = os.path.basename(self._modpath)
        self._moddir = os.path.dirname(self._modpath)
    
    @property 
    def directory (self) :
        return self._moddir
    
    @property
    def name (self) :
        return self._modname
    
    def python (self) :
        return sys.executable
    
    def path (self, filename) :
        return os.path.join(self.directory, filename)

class ADPNStashEncryption :
    def __init__ (self) :
        self._public_key_bytes = None
        self._private_key_bytes = None
    
    @property
    def keys (self) :
        return ( self._public_key_bytes, self._private_key_bytes )
    
    @keys.setter
    def keys (self, rhs) :
        if type(rhs) is tuple or type(rhs) is list:
            ( self.public_key, self.private_key ) = rhs
        elif hasattr(rhs, 'publickey') :
            ( self.public_key, self.private_key ) = ( rhs, rhs )
        else :
            raise TypeError("Required: key pair in tuple or object", rhs)
    
    @property
    def public_key (self) :
        return RSA.import_key(self._public_key_bytes)
    
    @property
    def rsa_public_key (self) :
        return RSA.import_key(self._public_key_bytes)
        
    @public_key.setter
    def public_key (self, rhs) :
        if type(rhs) is bytes :
            self._public_key_bytes = rhs
        elif hasattr(rhs, 'publickey') :
            self._public_key_bytes = rhs.publickey().export_key()
        elif hasattr(rhs, 'export_key') :
            self._public_key_bytes = rhs.export_key()
        elif rhs is None :
            self._public_key_bytes = rhs
        else :
            raise TypeError("Required: RSA key pair or public key block", rhs)
    
    @property
    def private_key (self) :
        return RSA.import_key(self._private_key_bytes)
    
    @property
    def rsa_private_key (self) :
        return RSA.import_key(self._private_key_bytes)
        
    @private_key.setter
    def private_key (self, rhs) :
        if type(rhs) is bytes :
            self._private_key_bytes = rhs
        elif hasattr(rhs, 'export_key') :
            self._private_key_bytes = rhs.export_key()
        elif rhs is None :
            self._private_key_bytes = None
        else :
            raise TypeError("Required: RSA key pair or private key block", rhs)
    
    def encode_to_file (self, data: list) -> bytes :
        all_data = b"".join(data)
        return base64.urlsafe_b64encode(all_data)

    def decode_from_file (self, data: bytes, private_key) -> bytes :
        all_data = base64.urlsafe_b64decode(data)
        
        N0, N = ( 0, private_key.size_in_bytes() )
        enc_session_key = all_data[N0:N]
        N0, N = ( N, N+16 )
        nonce = all_data[N0:N]
        N0, N = ( N, N+16 )
        tag = all_data[N0:N]
        N0, N = ( N, len(all_data) )
        ciphertext = all_data[N0:N]
        
        return ( enc_session_key, nonce, tag, ciphertext )
    
    def generate_keypair (self, size=2048) :
        key = RSA.generate(size)
        private_key = key.export_key()
        public_key = key.publickey().export_key()
        return (public_key, private_key)
    
    def generate_session_key (self) :
        return get_random_bytes(16)
    
    def encrypt_text (self, text: str) -> bytes :
        data = text.encode("utf-8")
        
        session_key = self.generate_session_key()
        
        # Encrypt the session key with the public RSA key
        cipher_rsa = PKCS1_OAEP.new(self.rsa_public_key)
        enc_session_key = cipher_rsa.encrypt(session_key)

        # Encrypt the data with the AES session key
        cipher_aes = AES.new(session_key, AES.MODE_EAX)
        ciphertext, tag = cipher_aes.encrypt_and_digest(data)
        return self.encode_to_file([ enc_session_key, cipher_aes.nonce, tag, ciphertext])

    def decrypt_text (self, data: bytes) -> str:
        
        rsa_private_key = self.rsa_private_key
        ( enc_session_key, nonce, tag, ciphertext ) = self.decode_from_file(data, rsa_private_key)
        
        # Decrypt the session key with the private RSA key
        cipher_rsa = PKCS1_OAEP.new(rsa_private_key)
        session_key = cipher_rsa.decrypt(enc_session_key)
        
        # Decrypt the data with the AES session key
        cipher_aes = AES.new(session_key, AES.MODE_EAX, nonce)
        data = cipher_aes.decrypt_and_verify(ciphertext, tag)
        
        return data.decode("utf-8")

if __name__ == '__main__':

	defaults = {"foo": "bar"}
	ss = {}
	
	old_argv = sys.argv

	print("DEFAULTS: ", "\t", defaults)
	print("")
	
	print(">>>", "(sys.argv, sw) = myPyCommandLine(sys.argv).parse(defaults=defaults)")
	(sys.argv, sw) = myPyCommandLine(sys.argv).parse(defaults=defaults)

	print("ARGV:    ", "\t", sys.argv)
	print("SWITCHES:", "\t", sw)

	sys.argv = old_argv
	
	print("")
	
	print(">>>", "cmd = myPyCommandLine(sys.argv) ; cmd.parse(defaults=defaults) ; args = cmd.argv ; sw = cmd.switches")

	cmd = myPyCommandLine(sys.argv)
	cmd.parse(defaults=defaults)
	args = cmd.argv
	sw = cmd.switches
	
	print("ARGS:    ", "\t", args)
	print("SWITCHES:", "\t", sw)
	
	sys.argv = old_argv

	print("")
	
	print("Good JSON...")
	
	table1 = {"Ingest Title": "Alabama Department of Archives and History WPA Folder 01", "File Size ": "2.1G (2,243,154,758 bytes, 689 files)", "Plugin JAR": "http://configuration.adpn.org/overhead/takeover/plugins/AlabamaDepartmentOfArchivesAndHistoryDirectoryPlugin.jar", "Plugin ID": "gov.alabama.archives.adpn.directory.AlabamaDepartmentOfArchivesAndHistoryDirectoryPlugin", "Plugin Name": "Alabama Department of Archives and History Directory Plugin", "Plugin Version": "1", "Start URL": "http://archives.alabama.gov/Lockss/WPA-Folder-01/", "Manifest URL": "http://archives.alabama.gov/Lockss/WPA-Folder-01/manifestpage.html", "Base URL": "base_url=\"http://archives.alabama.gov/Lockss/\"", "Subdirectory": "subdirectory=\"WPA-Folder-01\"", "au_name": "Alabama Department of Archives and History Directory Plugin, Base URL http://archives.alabama.gov/Lockss/, Subdirectory WPA-Folder-01"}
	table2 = {"au_start_url": "http://archives.alabama.gov/Lockss/WPA-Folder-01/", "au_manifest": "http://archives.alabama.gov/Lockss/WPA-Folder-01/manifestpage.html", "parameters": [["base_url", "http://archives.alabama.gov/Lockss/"], ["subdirectory", "WPA-Folder-01"]]}

	inp = "USELESS LINE: FooBar" + "\n" + "JSON PACKET: " + json.dumps(table1) + "\n" + json.dumps(table2) + "\n\n"

	jsonInput = myPyJSON()
	jsonInput.accept(inp)
	print("")
	
	print("")
	print("JSON TEXT >>>")
	print(jsonInput.json)
	print("")
	print("JSON DATA >>>")
	print(jsonInput.data)
	print("")
	print("AGGREGATED JSON DATA >>>")
	print(jsonInput.allData)
	print("")
	
	print("Bad JSON...")

	inp = "JSON PACKET: {oooOOooo what's this?}" + "\n" + "NON-JSON LINE: Hmmm"

	jsonInput = myPyJSON()
	jsonInput.accept(inp)
	print("")
	
	print("")
	print("JSON TEXT >>>")
	print(jsonInput.json)
	print("")
	print("JSON DATA >>>")
	try :
		print(jsonInput.data)
	except json.decoder.JSONDecodeError as e :
		print("myPyJSON.data -- excepted expected, OK !")
	print("")
	print("AGGREGATED JSON DATA >>>")
	try :
		print(jsonInput.allData)
	except json.decoder.JSONDecodeError as e :
		print("myPyJSON.data -- excepted expected, OK !")
	print("")
