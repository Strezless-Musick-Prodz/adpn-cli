#!/usr/bin/python3
#
# adpn-get-keepass.py: retrieve a stored password or token information stored in an
# encrypted .kdbx (KeePass) database.
#
# @version 2021.0706

import io, os, stat, sys
import pykeepass
from pykeepass import PyKeePass
from getpass import getpass
import re, json
import urllib.parse
from myLockssScripts import myPyCommandLine, myPyPipeline, myPyJSON
from ADPNCommandLineTool import ADPNCommandLineTool

class KeePassDatabase :

    def __init__ (self, file=None, keyfile=None) :
        self._kp = None
        self._file = file
        self._keyfile = keyfile
        self._made = False
        self._requested_passphrase = False
        self._dirty = False
        
    @property
    def file (self) -> str :
        return self._file
    
    @property
    def keyfile (self) :
        return self._keyfile
    
    @property
    def made (self) -> bool :
        return self._made
    
    @made.setter
    def made (self, rhs: bool) :
        self._made = not not rhs
    
    @property
    def requested_passphrase (self) -> bool :
        return self._requested_passphrase
    
    @requested_passphrase.setter
    def requested_passphrase (self, rhs: bool) :
        self._requested_passphrase = rhs
    
    @property
    def dirty (self) -> bool :
        return self._dirty
    
    @dirty.setter
    def dirty (self, rhs: bool) :
        dirty_before = self.dirty
        dirty_after = rhs
        if dirty_before and not dirty_after :
            self._kp.save()
        self._dirty = dirty_after
    
    @property
    def db (self) :
        return self._kp
    
    def read (self, make=False, get_password=getpass) :
        self.requested_passphrase = False

        try :
            self._kp = PyKeePass(self.file)
        except pykeepass.exceptions.CredentialsError as e:
            self._kp = None
            self.requested_passphrase = True
        except FileNotFoundError as e :
            if make :
                self._kp = pykeepass.create_database(self.file, password=get_password())
                self._kp.add_group(self._kp.root_group, "ADPNet")
                self.made = True

            else :
                self._kp = None
                raise
        
        if self.requested_passphrase :
            
            try :
                if self.keyfile :
                    self._kp = PyKeePass(self.file, keyfile=self.keyfile)
                else :
                    self._kp = PyKeePass(self.file, password=get_password())
            except pykeepass.exceptions.CredentialsError as e:
                self._kp = None
                raise
            except FileNotFoundError as e :
                self._kp = None
                raise

        if self._kp is None :
            raise KeyError("Unable to open KeePass database", self.file) 
            
        return self._kp


class ADPNDoKeePassScript(ADPNCommandLineTool) :
    """
Usage: adpn-get-keypass.py [<OPTIONS>]... --database=<FILE.KDBX>

FILE.KDBX should provide the file path location of a KeePass password manager database file
(KDBX file). KeePass databases are encrypted, and typically accessed using either a master
passphrase, or a separate key file. If the database file provided requires a master passphrase,
the user will be prompted to provide it interactively.

  --database=<FLE.KDBX>         the file path location of a KeePass database file
  --output=<MIME-TYPE>          a MIME type providing the format for returning information about the password entry
                                options: text/plain, text/tab-separated-values, or application/json
  --password=<PASSWORD>         a master passphrase to access data in the KeePass database
  --keyfile=<KEY-FILE>          a file system path to a key file to access data in the KeePass database
  --title=<TITLE>               the title of the key requested from the database
  --regex=<REGULAR-EXPRESSION>  a regular expression to match the title of the key requested from the database
  --all                         if provided, return ALL keys that match the requested title or regular expression pattern; if not, return the first matching key
  --set                         if provided, then SET the password for the selected key to the first line of text on STDIN
    """
    
    def __init__ (self, scriptpath, argv, switches) :
        super().__init__(scriptpath, argv, switches)
        
        self._query={ "title": "ADPNet" }

        self._url = urllib.parse.urlparse(self.database_url)
        if self._url.scheme == "keepass" :
            # Check whether we can get entry name from query or from fragment
            if self._url.query :
                qs = urllib.parse.parse_qs(self._url.query)
                
                for key in qs.keys() :
                    if len(qs[key]) == 1 :
                        qs[key] = qs[key][0]
                        
                self._query = { **self._query,  **qs }
            if self._url.fragment :
                self._query = { **self._query, **{ "title": self._url.fragment } }
        
        if self.switched('title') :
            self._query = { **self._query, **{ "title": self.switches.get("title") } }
    
    @property
    def is_localurl (self) :
        return not self._url.netloc
    
    @property
    def url_path (self) :
        return self._url.path if hasattr(self._url, 'path') else None
    
    @property
    def is_homepath (self) :
        return re.match("^~", self.url_path.lstrip("/")) and self.is_localurl 
        
    @property
    def database_file (self) :
        return os.path.expanduser(self.url_path.lstrip("/")) if self.is_homepath else self.url_path
        
    @property
    def database_url (self) :
        return self.switches.get("database", None)
    
    @property
    def keyfile (self) :
        return self.switches.get("keyfile", None)
        
    @property
    def entry_title (self) :
        return self.switches.get("regex") if self.entry_title_use_regex else self._query.get("title")
    
    @property
    def entry_title_use_regex (self) :
        return self.switched("regex")
    
    def read_password (self) :
        password = None
        if self.has_piped_data :
            if not self.switched('interactive') :
                password = sys.stdin.readline()
        
        if password is None : # still
            password=getpass(self.get_password_prompt())
        
        if self.switched('stash') and password is not None :
            try :
                cmdline = self.switches.get('stash')
                argv = [ arg for arg in re.split(r"\s+", cmdline) ]
                pipe = myPyPipeline( [ argv ] )
                (out, err, code) = pipe.siphon(stdin=str(password))
            except Exception as e :
                write_error(code, "--stash error: %(e)s" % { "e": e})
        return password
    
    def get_password_prompt (self) :
        return ( "Passphrase to access %(database)s (%(title)s): " % { "database": self.database_file, "title": self.entry_title if self.entry_title else "KDBX" } )
    
    def get_password (self) :
        password = self.switches.get('password')
        if password is not None :
            if password == 'password' or len(password) == 0 :
                if self.has_piped_data :
                    password = sys.stdin.readline()

        if password is None :
            password = self.read_password()

        return password
    
    def write_entry (self, entry) :
        fmt = self.switches.get("output", "text/plain")
        if "application/json" == fmt :
            print(json.dumps({"username": entry.username, "password": entry.password, "url": entry.url, "title": entry.title}))
        elif "text/tab-separated-values" == fmt :
            print("\t".join([ entry.password, entry.username, entry.url, entry.title ]))
        else :
            print(entry.password, end="")
    
    def read_keepass_database (self) :
        kdbx = None
        
        try :
            kdbx = KeePassDatabase(file=self.database_file, keyfile=self.keyfile)
            kdbx.read(make=self.switched('create'), get_password=self.get_password)
            
        except pykeepass.exceptions.CredentialsError as e:
            kp = None
            self.write_error(2, "FAILED: found KeePass database but could not open with the provided passphrase. Did you use the correct passphrase for [%(database)s]?" % { "database": self.database_file })

        except FileNotFoundError as e :
            self.write_error(1, "FAILED: could not open KeePass database [%(db)s]" % {"db": self.database_file})

        if kdbx.made : 
            self.write_error(0, "CREATED: created new KeePass database [%(db)s]" % {"db": self.database_file})

        return kdbx.db

    def execute (self) :
        dirty = False
        
        if self.switched('database') :

            try :
                kp = self.read_keepass_database()
                entries = kp.find_entries( title=self.entry_title, first=False, regex=self.entry_title_use_regex )

                if len(entries) > 0 :
                    if not self.switched('all') :
                        entries = [ entries[0] ]
                    for entry in entries :
                        if self.switched('set') :
                        
                            if self.has_piped_data :
                                next_line = sys.stdin.readline()
                            else :
                                next_line = getpass("Password for %(key)s: " % {"key": entry.title})
                            
                            if next_line :
                                next_line.strip("\n")
                                entry.password = next_line
                                dirty = True
                                self.write_error(0, "Set password for %(key)s to %(stars)s" % { "key": entry.title, "stars": "*" * len(next_line) })
                                
                        else :
                            self.write_entry(entry)
                
                elif ( self.switched('create') or self.switched('set') ) and not self.entry_title_use_regex :
                    self.write_error(0, "CREATE/SET: KeePass database [%(database)s] accessed, creating key '%(key)s'..." % { "database": self.database_file, "key": self.entry_title })
                    group = kp.find_groups(name="ADPNet", first=True)
                    if group is None :
                        group = kp.root_group
                    
                    if self.has_piped_data :
                        # Piped or redirected stdin
                        received_username = self.entry_title
                        received_password = sys.stdin.readline()
                        if received_password : 
                            received_password.strip("\n")
                    else :
                        # Terminal
                        received_username = input("Username [%(username)s]: " % { "username": self.entry_title } )
                        received_password = getpass("Password: ")
                        
                    kp.add_entry(group, title=self.entry_title, username=received_username, password=received_password)
                    dirty = True
                    
                else :
                    self.write_error(3, "FAILED: KeePass database [%(database)s] accessed, but no such key ['%(key)s'] found" % { "database": self.database_file, "key": self.entry_title })

            except KeyError as e :
                pass
            
        else :
            self.write_error(1, "REQUIRED: path to KeePass database must be provided in --database='...'")
            
        if dirty :
            kp.save()

    def exit (self) :
        sys.exit(self.exitcode)

if __name__ == '__main__':

    scriptpath = os.path.realpath(sys.argv[0])
    scriptname = os.path.basename(scriptpath)
    scriptdir = os.path.dirname(scriptpath)
    configjson = "/".join([scriptdir, "adpnet.json"])
    
    os.environ["PATH"] = ":".join( [ scriptdir, os.environ["PATH"] ] )
    
    (sys.argv, switches) = myPyCommandLine(sys.argv, defaults={
        "database": None, "output": "text/plain",
        "password": None, "keyfile": None,
        "title": None, "regex": None,
        "all": None, "single": None,
        "set": None, "create": None,
        "help": None, "version": None
    }, configfile=configjson).parse()
       
    # look for positional arguments: first argument goes to --database=...
    cmd_args = sys.argv[1:]
    if switches.get('database') is None :
        if len(sys.argv) > 1 :
            switches['database'] = cmd_args[0]
            cmd_args = cmd_args[1:]
    
    script = ADPNDoKeePassScript(scriptpath, sys.argv, switches)
    
    if script.switched('help') :
        script.display_usage()
    elif script.switched('details') :
        print("Settings:", argv, switches)
    else :
        script.execute()

    script.exit()
