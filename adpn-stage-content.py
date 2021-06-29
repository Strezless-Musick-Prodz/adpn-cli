#!/usr/bin/python3
#
# adpn-stage-content.py: upload a directory of files for preservation to a staging server
# accessible via FTP, easy-peasy lemon squeezy.
#
# @version 2021.0628

import io, os, sys
import fileinput, stat
import subprocess
import re, json
import urllib, ftplib, pysftp
import math
from datetime import datetime
from io import BytesIO
from ftplib import FTP
from getpass import getpass
from myLockssScripts import myPyCommandLine, myPyJSON
from ADPNPreservationPackage import ADPNPreservationPackage

class FTPStaging :

    def __init__ (self, ftp, user, host) :
        self.ftp = ftp
        self.user = user
        self.host = host
    
    def is_sftp (self) :
        return isinstance(self.ftp, pysftp.Connection)
    
    def is_ftp (self) :
        return isinstance(self.ftp, FTP)
    
    def get_protocol (self) :
        return "sftp" if self.is_sftp() else "ftp"
    
    def get_file_size (self, file) :
        size=None
        try :
            if self.is_sftp() :
                stat=self.ftp.stat(file)
                size=stat.st_size
            else :
                size=self.ftp.size(file)
        except FileNotFoundError :
            pass
        except ftplib.error_perm :
            pass
        
        return size
    
    def url_host (self) :
        return ("%(user)s@%(host)s" if self.user else "%(host)s") % {"user": self.user, "host": self.host}
    
    def url (self) :
        return "%(protocol)s://%(host)s%(path)s" % {"protocol": self.get_protocol(), "host": self.url_host(), "path": self.get_location() }
    
    def get_location (self) :
        return ( self.ftp.getcwd() if self.is_sftp() else self.ftp.pwd() )
    
    def remove_item (self, file) :
        if self.is_sftp() :
            self.ftp.remove(file)
        else :
            self.ftp.delete(file)
    
    def new_directoryitem (self, dir) :
        if self.is_sftp() :
            self.ftp.mkdir(dir)
        else :
            self.ftp.mkd(dir)
    
    def remove_directoryitem (self, dir) :
        if self.is_sftp() :
            self.ftp.rmdir(dir)
        else :
            self.ftp.rmd(dir)
    
    def set_location (self, dir=None, remote=None, make=False) :
        rdir = remote if remote is not None else dir
        rlast = self.set_remotelocation(dir=rdir, make=make)
        llast = os.getcwd()

        try :
            if dir is not None :
                os.chdir(dir)
        except FileNotFoundError as e :
            if make :
                os.mkdir(dir)
                os.chdir(dir)
            else :
                raise
        
        return (llast, rlast)
        
    def set_remotelocation (self, dir, make=False) :
        last = self.get_location()
        
        exists = False
        try :
            if self.is_sftp() :
                self.ftp.chdir(dir)
                exists = True
            else :
                self.ftp.cwd(dir)
                exists = True
        except ftplib.error_perm as e :
            pass
        except FileNotFoundError as e :
            pass
        
        if not exists :
            
            if make :
                self.new_directoryitem(dir)
                self.set_remotelocation(dir, make=False)
            else :
                raise FileNotFoundError
            
        return last
    
    def get_childitem (self) :
        return self.ftp.listdir() if self.is_sftp() else self.ftp.nlst()

    def download_file (self, file = None) :
        try :
            if self.is_sftp() :
                self.ftp.get(file)
            else :
                self.ftp.retrbinary("RETR %(file)s" % {"file": file}, open( file, 'wb' ).write)
        except OSError :
            pass

    def download (self, file = None, exclude = None, notification = None) :
        out = notification if notification is not None else lambda level, type, arg: (level, type, arg) # NOOP
        
        if '.' == file or self.get_file_size(file) is None :
            
            if '.' != file :
                fileparent = os.path.realpath(file)
                out(2, "realpath", fileparent)
                (lpwd, rpwd) = self.set_location(dir=file, make=True)
                out(2, "set_location", (os.getcwd(), self.pwd()))

            for subfile in self.get_childitem() :
                exclude_this = exclude(subfile) if exclude is not None else False
                if not exclude_this :
                    (level, type) = (1, "downloaded")

                    self.download(file=subfile, exclude=exclude, notification=notification)
                        
                else :
                    (level, type) = (2, "excluded")
                    
                out(level, type, subfile)

            if '.' != file :
                self.set_location(dir=lpwd, remote=rpwd, make=False)
                out(2, "set_location", (lpwd, rpwd))
                self.remove_directoryitem(file)
                out(1, "remove_directoryitem", file)
                
        else :
            self.download_file(file=file)
            if self.get_file_size(file) == os.stat(file).st_size :
                self.remove_item(file)
                out(1, "remove_item", file)
    
    def upload_file (self, blob = None, file = None) :
        if isinstance(blob, str) :
            blob = blob.encode("utf-8")
        
        if self.is_sftp() :
            if blob is not None :
                self.ftp.putfo(io.BytesIO(bytes(blob)), remotepath=file)
            else :
                self.ftp.put(file)
        else :
            stream=BytesIO(bytes(blob)) if blob is not None else open(file, 'rb')
            self.ftp.storbinary("STOR %(filename)s" % {"filename": file}, stream)
            stream.close()
    
    def upload (self, blob = None, file = None, exclude = None, notification = None) :
        out = notification if notification is not None else lambda level, type, arg: (level, type, arg) # NOOP
        
        if blob is not None :
            self.upload_file(blob, file)
        elif os.path.isfile(file) :
            self.upload_file(blob=None, file=file)
        elif '.' == file or os.path.isdir(file) :
            
            if '.' != file :
                fileparent = os.path.realpath(file)
                out(2, "realpath", fileparent)
                (lpwd, rpwd) = self.set_location(dir=file, make=True)
                out(2, "set_location", (os.getcwd(), self.get_location()))

            for subfile in os.listdir() :
                exclude_this = exclude(subfile) if exclude is not None else False
                if not exclude_this :
                    (level, type) = (1, "uploaded")
                    self.upload(blob=None, file=subfile, exclude=exclude, notification = notification)
                else :
                    (level, type) = (2, "excluded")
                    
                out(level, type, subfile)

            if '.' != file :
                out(2, "set_location", (lpwd, rpwd))
                self.set_location(dir=lpwd, remote=rpwd, make=False)
            
    def quit (self) :
        if self.is_sftp() :
            self.ftp.close()
        else :
            self.ftp.quit()

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
    
    def establish_connection (self) :
        if "sftp" == self.protocol :
            o_connection = FTPStaging(pysftp.Connection(self.host, username=self.user, password=self.passwd), user=self.user, host=self.host)
        else :
            o_connection = FTPStaging(FTP(self.host, user=self.user, passwd=self.passwd), user=self.user, host=self.host)
        
        return o_connection
    
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

        passwd_prompt = "FTP Password (%(user)s@%(host)s): " % {"user": self.user, "host": self.host}

        try :
            if self.user is None :
                self.user = input("User: ")
            if self.passwd is None :
                self.passwd = getpass(passwd_prompt)
            if self.base_dir is None or len(self.base_dir) == 0:
                self.base_dir = input("Base dir: ")
            if self.subdirectory is None or len(self.subdirectory) == 0 :
                self.subdirectory = input("Subdirectory: ")
            
            # Let's log in to the host
            self.ftp = self.establish_connection()

            # Let's CWD over to the repository
            self.ftp.set_remotelocation(self.base_dir)
            backupDir = self.mkBackupDir()
        
            (local_pwd, remote_pwd) = self.ftp.set_location(dir=backupDir, remote=self.subdirectory, make=True)
            self.ftp.download(file=".", exclude=lambda file: file == 'Thumbs.db', notification=self.output_status)

            self.ftp.set_location(dir=local_pwd, remote=remote_pwd)
            (local_pwd, remote_pwd) = self.ftp.set_location(dir=self.switches['local'], remote=self.subdirectory, make=True)
            self.output_status(2, "set_location", (os.getcwd(), self.ftp.get_location()))
            
            package = ADPNPreservationPackage(self.switches['local'], self.manifest, self.switches)
            fileparent = self.get_itemparent(package.get_path())
            if not package.has_manifest() :
                package.make_manifest()

            # upload the present directory recursively
            self.ftp.upload(file=".", exclude=lambda file: file == 'Thumbs.db', notification=self.output_status)
        
            self.output_status(0, "ok", {"local": os.getcwd(), "staged": self.ftp.url(), "jar": self.switches['jar'], "au_title": self.switches['au_title'], "parameters": [ [ key, self.manifest[key] ] for key in self.manifest ] })
        
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
        
if __name__ == '__main__':

    scriptname = os.path.basename(sys.argv[0])
    scriptdir = os.path.dirname(sys.argv[0])
    configjson = "/".join([scriptdir, "adpnet.json"])
    
    os.environ["PATH"] = ":".join( [ scriptdir, os.environ["PATH"] ] )
    
    (sys.argv, switches) = myPyCommandLine(sys.argv, defaults={
            "ftp/host": None, "ftp/user": None, "ftp/pass": None,
            "stage/host": None, "stage/user": None, "stage/pass": None, "stage/protocol": None,
            "jar": None,
            "subdirectory": None, "directory": None,
            "base_dir": None, "output": "text/plain",
            "local": None, "backup": "./backup",
            "verbose": 1, "quiet": False,
            "base_url": None, "au_title": None, "au_notes": None, "au_file_size": None, "institution": None,
            "proxy": None, "port": None, "tunnel": None, "tunnel-port": None,
            "dummy": None
    }, configfile=configjson, settingsgroup=["stage", "ftp"]).parse()
    
    manifest = {
        "institution_name": switches['institution'],
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
    