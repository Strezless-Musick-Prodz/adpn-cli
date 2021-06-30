#!/usr/bin/python3
#
# adpn-stage-content.py: upload a directory of files for preservation to a staging server
# accessible via FTP, easy-peasy lemon squeezy.
#
# @version 2021.0628

import io, os, sys
import fileinput, stat
import re, json
import urllib, ftplib, pysftp
import math
from paramiko import ssh_exception
from datetime import datetime
from io import BytesIO
from ftplib import FTP
from getpass import getpass
from myLockssScripts import myPyCommandLine, myPyJSON
from ADPNPreservationPackage import ADPNPreservationPackage
from myFTPStaging import myFTPStaging

class ADPNStageContentScript :
    """
Usage: adpn-stage-content.py [<OPTIONS>]... [<URL>]

URL should be an FTP URL, in the form ftp://[<user>[:<pass>]@]<host>/<dir>
The <user> and <pass> elements are optional; they can be provided as part
of the URL, or using command-line switches, or interactively at input and
password prompts.

  --local=<PATH>   	   	the local directory containing the files to stage
  --au_title=<TITLE>   	the human-readable title for the contents of this AU
  --subdirectory=<SLUG>	the subdirectory on the staging server to hold AU files
  --directory=<SLUG>   	identical to --subdirectory
  --backup=<PATH>      	path to store current contents (if any) of staging location
  
Output and Diagnostics:

  --output=<MIME>      	text/plain or application/json
  --verbose=<LEVEL>   	level (0-2) of diagnostic output during FTP upload/download
  --quiet             	identical to --verbose=0
  
Common configuration parameters:

  --base_url=<URL>     	WWW: the URL for web access to the staging area
  --host=<NAME>        	FTP: host name of the server with the staging area
  --user=<NAME>        	FTP: username for logging in to the staging server
  --pass=<PASSWD>      	FTP: password for logging in to the staging server
  --base_dir=<PATH>   	FTP: path to the staging area on the FTP server
  --institution=<NAME>  Manifest: human-readable nmae of the institution

To generate a manifest file, the script needs to use information from the
LOCKSS Publisher Plugin. Plugins are hosted on the LOCKSS props
server/admin node.

If you need to connect to the LOCKSS props server through a SOCKS5 proxy, use:

  --proxy=<HOST>      	the name of your proxy (use "localhost" for SSH tunnel)
  --port=<NUMBER>      	the port number for your proxy
  
If you need to use SSH tunneling to connect to the SOCKS5 proxy, use:

  --tunnel=<HOST>     	the name of the host to open an SSH tunnel to
  --tunnel-port=<PORT> 	the port for SSH connections to the tunnel (default: 22)

Default values for these parameters can be set in the JSON configuration file
adpnet.json, located in the same directory as the script. To set a default
value, add a key-value pair to the hash table with a key based on the name of
the switch. (For example, to set the default value for the --institution switch
to "Alabama Department of Archives and History", add the following pair to the
hash table:

    {
        ...
        "institution": "Alabama Department of Archives and History",
        ...
    }
    
The default values in adpnet.json are overridden if values are provided on the
command line with explicit switches.
    """
    
    def __init__ (self, scriptname, argv, switches, manifest) :
        self.scriptname = scriptname
        self.argv = argv
        self.switches = switches
        self.manifest = manifest
        self.exitcode = 0
        
        self.verbose = int(self.switches.get('verbose')) if self.switches.get('verbose') is not None else 0
        if self.switches.get('quiet') :
            self.verbose=0
        
        # start out with defaults
        self.ftp = None
        self.protocol = "sftp"
        self.host = "localhost"
        self.user = None
        self.passwd = None
        self.base_dir = "/"
        self.subdirectory = None
        
        # now unpack and overlay elements from the FTP URL, if any is provided
        if len(self.argv) > 1 :
            self.unpack_ftp_elements(self.argv[1])
        
        # now overlay any further values from the command-line switches, if provided
        self.protocol=self.switches.get('protocol') if self.switches.get('protocol') is not None else self.protocol
        self.host=self.switches.get('host') if self.switches.get('host') is not None else self.host
        self.user=self.switches.get('user') if self.switches.get('user') is not None else self.user
        self.passwd=self.switches.get('pass') if self.switches.get('pass') is not None else self.passwd
        self.base_dir=switches.get('base_dir') if switches.get('base_dir') is not None else self.base_dir
        self.subdirectory=switches.get('directory') if switches.get('directory') is not None else self.subdirectory
        self.subdirectory=switches.get('subdirectory') if switches.get('subdirectory') is not None else self.subdirectory
        
        self.manifest["institution_code"] = self.user
    
    def switched (self, key) :
        got = not not self.switches.get(key, None)
        return got
    
    def get_itemparent (self, file) :
        canonical = os.path.realpath(file)
        return os.path.dirname(canonical)

    def unpack_ftp_elements(self, url) :
        (host, user, passwd, base_dir, subdirectory) = (None, None, None, None, None)
        
        bits=urllib.parse.urlparse(url)
        if len(bits.scheme) > 0 :
            self.protocol = bits.scheme
        
        if len(bits.netloc) > 0 :
            netloc = bits.netloc.split('@', 1)
            netloc.reverse()
            (host, credentials)=(netloc[0], netloc[1] if len(netloc) > 1 else None)
            credentials=credentials.split(':', 1) if credentials is not None else [None, None]
            (user, passwd) = (credentials[0], credentials[1] if len(credentials) > 1 else None)
        
            self.host = host
            self.user = user
            self.passwd = passwd
        
        if len(bits.path) > 1 :
            base_dir = bits.path
            subdirectory = '.'
            
            self.base_dir = base_dir
            self.subdirectory = subdirectory
    
    def mkBackupDir (self) :
        backupPath=self.switches['backup']
        
        try :
            os.mkdir(backupPath)
        except FileExistsError as e :
            pass
        
        datestamp=datetime.now().strftime('%Y%m%d%H%M%S')
        backupPath="%(backup)s/%(date)s" % {"backup": backupPath, "date": datestamp}
        
        try :
            os.mkdir(backupPath)
        except FileExistsError as e :
            pass

        backupPath="%(backup)s/%(subdirectory)s" % {"backup": backupPath, "subdirectory": self.subdirectory}
        try :
            os.mkdir(backupPath)
        except FileExistsError as e :
            pass

        return backupPath
    
    def get_private_keyfile (self) :
        keyfile = None
        if "sftp" == self.protocol :
            if self.switches["identity"] is not None :
                candidate_paths = [ os.path.realpath(os.path.expanduser(self.switches["identity"])) ]
            else :
                candidates = [ "id_rsa", "id_dsa", "identity" ]
                ssh_dir = os.path.expanduser("~/.ssh")
                candidate_paths = [ os.path.join(os.path.expanduser(ssh_dir), candidate) for candidate in candidates ]
            keyfiles = [ path for path in candidate_paths if os.path.exists(path) ]
            if len(keyfiles) > 0 :
                keyfile = keyfiles[0]
        return keyfile
        
    def has_private_keyfile (self) :
        return ( self.switches['password'] is None ) and ( self.get_private_keyfile() is not None )
    
    def read_password (self) :
        if self.has_private_keyfile() :
            passwd_prompt = "%(protocol)s private key passphrase (%(user)s@%(host)s): " % {"protocol": self.protocol.upper(), "user": self.user, "host": self.host}
        else :
            passwd_prompt = "%(protocol)s password (%(user)s@%(host)s): " % {"protocol": self.protocol.upper(), "user": self.user, "host": self.host}
        return getpass(passwd_prompt)

    def establish_connection (self, interactive=True) :
        if self.user is None :
            self.user = input("User: ")
        if self.passwd is None :
            self.passwd = self.read_password()

        if "sftp" == self.protocol :
            # check for an id_rsa or identity file
            if self.has_private_keyfile() :
                passwd = None
                private_key = self.get_private_keyfile()
                private_key_pass = self.passwd
            else :
                passwd = self.passwd
                private_key = None
                private_key_pass = None
                
            try :
                o_connection = pysftp.Connection(self.host, username=self.user, password=passwd, private_key=private_key, private_key_pass=private_key_pass)
            except ValueError as e:
                o_connection = None
                print("[%(cmd)s] Invalid passphrase for private key." % { "cmd": self.scriptname },  file=sys.stderr)
            except ssh_exception.AuthenticationException as e :
                o_connection = None
                if private_key is not None :
                    print("[%(cmd)s] %(protocol)s authentication failure. Did you use the right key file [%(key)s]?" % { "cmd": self.scriptname, "protocol": self.protocol.upper(), "key": private_key }, file=sys.stderr)
                else :
                    print("[%(cmd)s] %(protocol)s authentication failure. Did you use the right password?" % { "cmd": self.scriptname, "protocol": self.protocol.upper() },  file=sys.stderr)
            except ssh_exception.SSHException as e :
                o_connection = None
                
                if private_key is not None :
                    print("[%(cmd)s] %(protocol)s key decoding failure. Did you use the right passphrase [%(key)s]?" % { "cmd": self.scriptname, "protocol": self.protocol.upper(), "key": private_key, "err": str(e) },  file=sys.stderr)
                else :
                    print("[%(cmd)s] %(protocol)s connection failed: %(err)s." % { "cmd": self.scriptname, "protocol": self.protocol.upper(), "err": str(e) },  file=sys.stderr)
                
        else :
            o_connection = FTP(self.host, user=self.user, passwd=self.passwd)
        
        return myFTPStaging(o_connection, user=self.user, host=self.host) if o_connection is not None else None
    
    def output_status (self, level, type, arg) :
        (prefix, message) = (type, arg)

        if "uploaded" == type :
            prefix = ">>>"
        elif "downloaded" == type :
            prefix = "<<<"
        elif "excluded" == type :
            prefix = "---"
            message = ("excluded %(arg)s" % {"arg": arg})
        elif "chdir" == type :
            prefix = "..."
            path = "./%(dir)s" % {"dir": arg[1]} if arg[1].find("/")<0 else arg[1]
            message = "cd %(path)s" % {"path": path}
        elif "ok" == type :
            prefix = "JSON PACKET:\t"
            message["status"] = type
        
        out=sys.stdout
        if self.switches['output'] == 'application/json' :
            message = json.dumps(message)
            if level > 0 :
                out=sys.stderr
                
        if prefix is not None and level <= self.verbose :
            print(prefix, message, file=out)
    
    def display_usage (self) :
        print(self.__doc__)
        self.exitcode = 0
        
    def execute (self) :

        try :
            if self.base_dir is None or len(self.base_dir) == 0:
                self.base_dir = input("Base dir: ")
            if self.subdirectory is None or len(self.subdirectory) == 0 :
                self.subdirectory = input("Subdirectory: ")
            
            # First, let's check the packaging
            package = ADPNPreservationPackage(self.switches['local'], self.manifest, self.switches)
            if not package.has_bagit_enclosure() :
                self.output_status(2, "package.make_bagit_enclosure", ( package.get_path(), os.path.realpath(package.get_path()) ) )
                package.make_bagit_enclosure()

            self.output_status(2, "package.check_bagit_validation", ( package.get_path(), os.path.realpath(package.get_path()) ) )
            validates = package.check_bagit_validation()
            if validates :
                if not package.has_manifest() :
                    self.output_status(2, "package.make_manifest", ( package.get_path(), os.path.realpath(package.get_path()) ) )
                    package.make_manifest()
            else :
                raise OSError(package._bagit_exitcode, "BagIt validation FAILED", os.path.realpath(package.get_path()), package._bagit_output)
            
            # Let's log in to the host
            self.ftp = self.establish_connection()

            if self.ftp is not None :
                # Let's CWD over to the repository
                self.ftp.set_remotelocation(self.base_dir)
                backupDir = self.mkBackupDir()
            
                (local_pwd, remote_pwd) = self.ftp.set_location(dir=backupDir, remote=self.subdirectory, make=True)
                self.ftp.download(file=".", exclude=lambda file: file == 'Thumbs.db', notification=self.output_status)
                
                self.ftp.set_location(dir=local_pwd, remote=remote_pwd)
                (local_pwd, remote_pwd) = self.ftp.set_location(dir=self.switches['local'], remote=self.subdirectory, make=True)
                self.output_status(2, "set_location", (os.getcwd(), self.ftp.get_location()))
                
                # upload the present directory recursively
                self.ftp.upload(file=".", exclude=lambda file: file == 'Thumbs.db', notification=self.output_status)
            
                self.output_status(0, "ok", {
                    "local": os.getcwd(), "staged": self.ftp.url(),
                    "jar": self.switches['jar'],
                    "au_title": self.switches['au_title'],
                    "parameters": [ [ key, self.manifest[key] ] for key in self.manifest ]
                })
            
            else :
                self.exitcode = 1
                print("[%(scriptname)s] Connection failed for %(user)s@%(host)s." % {"scriptname": self.scriptname, "user": self.user, "host": self.host}, file=sys.stderr)
                
        except KeyboardInterrupt as e :
            self.exitcode = 255
            print("[%(scriptname)s] Keyboard Interrupt." % {"scriptname": self.scriptname}, file=sys.stderr)
        
        if self.ftp is not None :
            try :
                self.ftp.quit()
            except ftplib.error_perm as e :
                pass

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

    scriptname = os.path.basename(sys.argv[0])
    scriptdir = os.path.dirname(sys.argv[0])
    configjson = "/".join([scriptdir, "adpnet.json"])
    
    os.environ["PATH"] = ":".join( [ scriptdir, os.environ["PATH"] ] )
    
    (sys.argv, switches) = myPyCommandLine(sys.argv, defaults={
            "ftp/host": None, "ftp/user": None, "ftp/pass": None,
            "stage/host": None, "stage/user": None, "stage/pass": None, "stage/protocol": None,
            "stage/identity": None, "identity": None, "password": None,
            "jar": None,
            "subdirectory": None, "directory": None,
            "base_dir": None, "output": "text/plain",
            "local": None, "backup": "./backup",
            "verbose": 1, "quiet": False,
            "base_url": None, "au_title": None, "au_notes": None, "au_file_size": None, "institution": None,
            "proxy": None, "port": None, "tunnel": None, "tunnel-port": None,
            "dummy": None
    }, configfile=configjson, settingsgroup=["stage", "ftp"]).parse()
    
    align_switches("identity", "stage/identity", switches)
    align_switches("directory", "subdirectory", switches)
    
    institution = switches["institution"]
    if switches["peer"] is not None :
        institution = "%(institution)s (%(code)s)" % { "institution": institution, "code": switches["peer"].upper() }
    institution_code = switches['stage/user']
    
    manifest = {
        "institution": switches["institution"],
        "institution_name": institution,
        "institution_code": switches['stage/user'],
        "au_title": switches['au_title'],
        "au_directory": switches['directory'] if switches['directory'] is not None else switches['subdirectory'],
        "au_file_size": switches['au_file_size'],
        "au_notes": switches['au_notes'],
        "drop_server": switches['base_url'],
        "lockss_plugin": switches['jar'],
        "display_format": "text/html"
    }
    script = ADPNStageContentScript(scriptname, sys.argv, switches, manifest)
    
    if script.switched('help') :
        script.display_usage()
    elif script.switched('details') :
        print("Defaults:", defaults)
        print("")
        print("Settings:", switches)
    else :
        script.execute()

    script.exit()
    