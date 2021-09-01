#!/usr/bin/python3
#
# adpn-json.py: utility script, pulls data elements from a JSON hash table
# provided on stdin and outputs the value (a printed str or a serialized str equivalent)
# from a given key-value pair, so that bash scripts can capture values from JSON packets.
#
# @version 2021.0726

from myLockssScripts import myPyCommandLine, myPyJSON
from ADPNStashEncryption import ADPNStashEncryption
import sys, os, stat, fileinput, tempfile
import re, json
import urllib.parse
import binascii
from Cryptodome.PublicKey import RSA
from Cryptodome.Random import get_random_bytes
from Cryptodome.Cipher import AES, PKCS1_OAEP
from contextlib import contextmanager

class ADPNStashScript :
    """
Usage: VALUE=$( <INPUT> | adpn-json.py - --key=<KEY> )

Input: a copy-pasted block of text, including one or more JSON hash tables,
possibly prefixed by a label like "JSON PACKET: " before the beginning of
the {...} hash table structure. (The label will be ignored.) If there are
multiple lines with JSON hash tables in them, the divers hash tables will
be merged together into one big hash table.

Output: the str value or typecasted str serialization of the value paired
with the provided key in the hash table. If there is no such key in the
hash table, nothing is printed out.

Exit code:
0= successful output of the value associated with the key requested
1= failed to output a value because the key requested does not exist
2= failed to output a value because the JSON could not be decoded
    """
    
    def __init__ (self, scriptname, argv, switches) :
        self.scriptname = scriptname
        self._argv = argv
        self._switches = switches
        self._output = []
        self._flags = { "file_not_found": [], "wrong_key": [], "output_error": [], "other_error": [] }
        self._default_mime = "text/plain"
        with open(argv[0], 'r') as f :
            for line in f.readlines() :
                ref = re.search(r'^#\s*@version\s*(.*)\s*$', line)
                if ref :
                    self._version = ref.group(1)
            f.close()
        
        # Initialize attributes to None/empty
        self._file = None
        self._fileobject = None
        self._filenames_provided = []
        self._keys = []
        self._crypt = None
        self._exitcode = None
        self._piped_input = None
        self._json = None
        
        # Initialize properties from command-line
        try :
            self.file = self.get_file_from()
        except FileNotFoundError as e :
            self.add_flag("file_not_found", e)
        
        self.crypt = ADPNStashEncryption()
        
        try :
            self.key = self.get_keys_from()
        except binascii.Error as e :
            self.add_flag( "wrong_key", e )
        
    @property
    def version (self) :
        return self._version
        
    @property
    def switches (self) :
        return self._switches

    @property
    def flags (self) :
        return self._flags
        
    @property
    def argv (self) :
        return self._argv
    
    @property
    def output (self) :
        return self._output
    
    @property
    def piped_input (self) :
        if self._piped_input is None :
            self._piped_input = self.get_piped_input()
        return self._piped_input
    
    def test_piped_input (self) :
        mode = os.fstat(sys.stdin.fileno()).st_mode
        return any([stat.S_ISFIFO(mode), stat.S_ISREG(mode)])
    
    def get_piped_input (self) :
        piped_text = None
        if self.test_piped_input() :
            piped_text = sys.stdin.read()
        return piped_text
    
    @property
    def piped_data (self) :
        if self._json is None :
            self._json = myPyJSON()
        maybe_json = self.piped_input
        self._json.accept(maybe_json)
        return self._json.allData
    
    def switched (self, name, default = None) :
        result = default
        if name in self.switches :
            result = self.switches[name]
        return result
    
    def add_flag (self, flag, value) :
        if value is not None :
            self.flags[flag].extend( [ value ] )

    def test_flagged (self, flag) :
        flags = self.flags.get(flag)
        return ( flags is not None ) and ( len(flags) > 0 )
    
    def raise_any_flags (self, flag=None) :
        
        if type(flag) is str :
            flags = [ flag ]
        elif type(flag) is list :
            flags = flag
        elif type(flag) is None :
            flags = self.flags.keys()
        else :
            raise TypeError("Parameter 'flag' must be of type str or list, not %s" % type(flag), flag)
        
        all_exceptions = []
        for key in flags :
            values = self.flags.get(key)
            all_exceptions.extend( [ e for e in values if isinstance(e, Exception) ] )
        
        if len(all_exceptions) > 0 :
            raise all_exceptions[0]
        
    @property
    def exitcode (self) :
        return self._exitcode
    
    @exitcode.setter
    def exitcode (self, rhs) :
        if type(rhs) is int :
            if rhs in range(0, 255) :
                self._exitcode = rhs
            else :
                raise ValueError("Script exit codes must be in range [0..255]")
        else : 
            raise TypeError("Script exit codes must be integers in range [0..255]")
    
    def get_exitcode (self) :
        if self.test_flagged("wrong_key") :
            self.exitcode=2
        elif self.test_flagged("file_not_found") :
            self.exitcode=1
        elif self.test_flagged("output_error") :
            self.exitcode=254
        else :
            self.exitcode=0
        return self.exitcode
    
    def get_file_from (self) :
        file = self.switches.get('file')
        if file is None :
            file = self.argv[1] if len(self.argv) > 1 else None
        if file is None and self.piped_data is not None :
            data = self.piped_data
            self.file = data.get("file")
        if file is not None :
            self.file = file
    
    def get_keys_from (self) :
        data = self.piped_data if self.piped_data is not None else {}
        public_key = self.switches.get('public_key')
        if public_key is None and data.get('public_key') is not None :
            public_key = data.get('public_key').encode("UTF-8")
        private_key = self.switches.get('private_key')
        if private_key is None and data.get('private_key') is not None :
            private_key = data.get('private_key').encode("UTF-8")
        return ( public_key, private_key )
        
    def display_version (self) :
        print("%(script)s version %(version)s" % {"script": self.scriptname, "version": self.version})

    def display_usage (self) :
        print(self.__doc__)
    
    @property
    def filename_provided (self) :
        return self._filenames_provided[0] if len(self._filenames_provided) > 0 else None
    
    @filename_provided.setter
    def filename_provided (self, rhs) :
        self._filenames_provided.append(rhs)
    
    @property
    def file (self) :
        return self._file
    
    @file.setter
    def file (self, rhs) :
        if type(rhs) is str :
            self.filename_provided = rhs
            if os.path.exists(rhs) :
                self._file = rhs
                self._fileobject = None
            else :
                raise FileNotFoundError("Could not find file: '%(file)s'" % { "file": rhs }, rhs)
        elif hasattr(rhs, 'fileno') and hasattr(rhs, 'name') :
            self.filename_provided = rhs.name
            self._file = rhs.name
            self._fileobject = rhs
    
    @property
    def key (self) :
        return ( self._keys[0] if len(self._keys) > 0 else None )
        
    @key.setter
    def key (self, rhs) :
        if rhs != self.key :
            self._keys = [ rhs ] + self._keys
            self.crypt.keys = rhs
        
    @property
    def crypt (self) :
        return self._crypt
    
    @crypt.setter
    def crypt (self, rhs) :
        self._crypt = rhs

    def new_temp_file (self) :
        return tempfile.NamedTemporaryFile(delete=False, mode="wb")
    
    @contextmanager
    def file_opened (self, mode="rb") :
        if self._fileobject is None :
            self._fileobject = open(self.file, mode=mode)
        try :
            yield self._fileobject
        finally :
            self._fileobject.close()
    
    def test_filename (self) :
        return self.filename_provided is not None # FIXME - STUB
    
    def test_file (self, key) :
        return os.path.exists(self.file) if self.file is not None else False # FIXME - STUB
    
    def new_encryption_key (self) :
        self.key = self.crypt.generate_keypair()
        return self.key
    
    def get_text (self, size=-1, lines=False, headers=False, bork=None) :
        with self.file_opened(mode="rb") as stream:
            text = self.get_decrypted_text(stream.read(size), key=self.key)
        
        if bork is not None :
            text = bork
        
        try :
            ( heads, body ) = re.split(r'\r\n\r\n', text, maxsplit=1)
        except ValueError as e :
            ( heads, body ) = ( "", text )

        header_lines = re.split(r'[\r\n]+', heads)
    
        s_wrong_key_message = "Wrong decryption key for %(filename)s: %(key)s" % { "filename": self.filename_provided, "key": self.key }

        assert len(header_lines) > 0, "%s (no headers found in decrypts)" % s_wrong_key_message
        splits = [ tuple(header.split(": ", maxsplit=1)) for header in header_lines if len(header.split(": "))>1 ]
        version = [ value for (key, value) in splits if "ADPN-Stash" == key ]
        assert len(version) > 0, "%s (no headers found in decrypts)" % s_wrong_key_message
        assert version[0] == self.version, "%s (wrong version header found in decrypts)" % s_wrong_key_message
        
        if lines :
            result = re.split(r'[\r\n]+', body)
            if headers :
                result = ( header_lines, result )
        elif headers :
            result = text
        else :
            result = body
        
        return result
    
    def put_text (self, size=-1) :
        text = self.piped_input
        with self.file_opened(mode="wb") as stream :
            headed_text = "\r\n".join( [ "MIME-Version: 1.0", "ADPN-Stash: %s" % self.version, "Content-Type: %s" % self.get_content_type(), "", text ] )
            stream.write(self.get_encrypted_text(headed_text, key=self.key))
    
    def remove_file (self) :
        try :
            os.remove(self.file)
        except FileNotFoundError as e :
            self.add_flag('file_not_found', e)
            raise
    
    def get_content_type (self) -> str :
        return "text/plain" # FIXME - STUB
        
    def get_decrypted_text (self, source: bytes, key=None) -> str:
        if key is not None :
            self.key = key
        
        return self.crypt.decrypt_text(source)
    
    def get_encrypted_text (self, text: str, key=None) -> bytes :
        if key is not None :
            self.key = key
        return self.crypt.encrypt_text(text)
    
    def get_bork_text (self) :
        bork = self.switches.get('bork')
        if bork == "bork" :
            bork = sys.stdin.read()
        return bork
        
    def execute (self) :
        try :
            self.raise_any_flags(['file_not_found', 'wrong_key'])
            if self.test_filename() :
                if not self.test_file(self.key) :
                    e = FileNotFoundError("Could not find file: '%(file)s'" % { "file": self.filename_provided }, self.filename_provided )
                    self.add_flag('file_not_found', e)
                    raise e
            else :
                if not self.test_file(self.key) :
                    self.file = self.new_temp_file()
                    self.key = self.new_encryption_key()
            
            if self.switched('get') :
                output = self.get_text(headers=self.switched('headers'), lines=self.switched('lines'), bork=self.get_bork_text())
                print(output)
            elif self.switched('put') :
                self.put_text()
                output_report = {
                    "file": self.file,
                    "public_key": self.key[0].decode("UTF-8"),
                    "private_key": self.key[1].decode("UTF-8")
                }
                print(json.dumps(output_report))
            elif self.switched('delete') :
                self.remove_file()
        except AssertionError as e :
            self.add_flag( "wrong_key", e )
            print(
                ("[%(script)s] %(message)s") % {"script": self.scriptname, "message": e.args[0] },
                file=sys.stderr
            )
        except binascii.Error as e :
            self.add_flag( "wrong_key", e.args[0] )
            print(
                ("[%(script)s] Bad key for '%(filename)s': %(key)s") % {"script": self.scriptname, "filename": self.filename_provided, "public_key": self.key[0], "private_key": self.key[1] },
                file=sys.stderr
            )
        except FileNotFoundError as e :
            self.add_flag( "file_not_found", e.args[1] )
            print(
                ("[%(script)s] Could not access data file: '%(filename)s'") % {"script": self.scriptname, "filename": self.filename_provided },
                file=sys.stderr
            )
        
if __name__ == '__main__' :

    scriptname = sys.argv[0]
    scriptname = os.path.basename(scriptname)

    (sys.argv, switches) = myPyCommandLine(sys.argv).parse()

    script = ADPNStashScript(scriptname, sys.argv, switches)
    if script.switched('help') :
        script.display_usage()
    elif script.switched('regex') :
        script.display_regex()
    elif script.switched('version') :
        script.display_version()
    elif script.switched('key') and script.switched('value') :
        script.display_keyvalue()
    else :
        script.execute()
    sys.exit(script.get_exitcode())

        