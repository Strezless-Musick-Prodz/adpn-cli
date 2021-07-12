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
from myLockssScripts import myPyCommandLine, myPyJSON

class ADPNDoKeePassScript :
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
        self._path = scriptpath
        self._argv = argv
        self._switches = switches
        self._exitcode = 0
        if not self.switched('regex') and not self.switched('title') :
            self._switches["title"] = "ADPNet"
    
    @property
    def path (self) :
        return self._path
        
    @property
    def name (self) :
        return os.path.basename(scriptpath)
    
    @property
    def argv (self) :
        return self._argv
        
    @property
    def switches (self) :
        return self._switches
    
    @property
    def exitcode (self) -> int:
        return self._exitcode
        
    @exitcode.setter
    def exitcode (self, code: int) :
        if code >= 0 and code <= 255 :
            self._exitcode = code
        else :
            raise ValueError("Exit code must be in range 0...255", code)
    
    @property
    def still_ok (self) :
        return ( self.exitcode == 0 )
    
    @property
    def database_file (self) :
        return self.switches.get("database", None)
    
    @property
    def keyfile (self) :
        return self.switches.get("keyfile", None)
        
    @property
    def entry_title (self) :
        return self.switches.get("regex" if self.entry_title_use_regex else "title")
    
    @property
    def entry_title_use_regex (self) :
        return self.switched("regex")
        
    def switched (self, key) :
        got = not not self.switches.get(key, None)
        return got
        
    def read_password (self) :
        return getpass(self.get_password_prompt())
    
    def get_password_prompt (self) :
        return ( "Passphrase to access %(database)s: " % { "database": self.database_file } )
    
    def get_password (self) :
        return self.switches.get('password') if self.switched('password') else self.read_password()
            
    def write_error (self, code, message, prefix="") :
        self.exitcode = code
        print ( "%(prefix)s[%(cmd)s] %(message)s" % { "prefix": prefix, "cmd": self.name, "message": message }, file=sys.stderr )

    def display_usage (self) :
        print(self.__doc__)
        self.exitcode = 0
    
    def write_entry (self, entry) :
        fmt = self.switches.get("output", "text/plain")
        if "application/json" == fmt :
            print(json.dumps({"username": entry.username, "password": entry.password, "url": entry.url, "title": entry.title}))
        elif "text/tab-separated-values" == fmt :
            print("\t".join([ entry.password, entry.username, entry.url, entry.title ]))
        else :
            print(entry.password, end="")
    
    def read_keepass_database (self) :
        kp = None
        request_passphrase = False
        
        try :
            kp = PyKeePass(self.database_file)
        except pykeepass.exceptions.CredentialsError as e:
            kp = None
            request_passphrase = True
        except FileNotFoundError as e :
            if self.switched('create') :
                kp = pykeepass.create_database(self.database_file, password=self.get_password())
                kp.add_group(kp.root_group, "ADPNet")
                self.write_error(0, ("CREATED: created new KeePass database [%(database)s]" % {"database": self.database_file}))

            else :
                kp = None
                self.write_error(1, ("FAILED: could not open KeePass database [%(database)s]" % {"database": self.database_file}))
        
        if request_passphrase :
            
            try :
                if self.keyfile :
                    kp = PyKeePass(self.database_file, keyfile=self.keyfile)
                else :
                    kp = PyKeePass(self.database_file, password=self.get_password())
            except pykeepass.exceptions.CredentialsError as e:
                kp = None
                self.write_error(2, "FAILED: found KeePass database but could not open with the provided passphrase. Did you use the correct passphrase for [%(database)s]?" % { "database": self.database_file })
            except FileNotFoundError as e :
                kp = None
                self.write_error(1, ("FAILED: could not open KeePass database [%(database)s] with passphrase..." % {"database": self.database_file}))
        
        if kp is None :
            raise KeyError("Unable to open KeePass database", self.database_file) 
            
        return kp

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
                            next_line = sys.stdin.readline()
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

                    mode = os.fstat(sys.stdin.fileno()).st_mode
                    if stat.S_ISFIFO(mode) or stat.S_ISREG(mode) :
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

def align_switches (left, right, switches, override=True) :
    if switches[left] is None :
        switches[left] = switches[right]
    if switches[right] is None :
        switches[right] = switches[left]
    if override :
        if switches[right] != switches[left] :
            switches[right] = switches[left]

if __name__ == '__main__':

    scriptpath = os.path.realpath(sys.argv[0])
    scriptname = os.path.basename(scriptpath)
    scriptdir = os.path.dirname(scriptpath)
    configjson = "/".join([scriptdir, "adpnet.json"])
    
    os.environ["PATH"] = ":".join( [ scriptdir, os.environ["PATH"] ] )
    
    (sys.argv, switches) = myPyCommandLine(sys.argv, defaults={
        "database": None, "output": "text/plain",
        "password": None, "keyfile": None,
        "title": None, "regex": None, "all": None,
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
