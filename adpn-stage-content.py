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
from getpass import getpass, getuser
from myLockssScripts import myPyCommandLine, myPyJSON, align_switches, shift_args
from ADPNPreservationPackage import ADPNPreservationPackage, myLockssPlugin
from myFTPStaging import myFTPStaging

python_std_input = input
def input (*args) :
    old_stdout = sys.stdout
    try :
        sys.stdout = sys.stderr
        return python_std_input(*args)
    finally :
        sys.stdout = old_stdout

class ADPNScriptPipeline :

    def __init__ (self) :
        self._pipelines = None
        self.json = myPyJSON()

    @property
    def pipelines (self) :
        if self._pipelines is None :
            self._pipelines = [ line for line in fileinput.input() ]
        return self._pipelines
    
    def get_data(self, key=None) :
        lines = self.pipelines
        self.json.accept(lines)
        return self.json.allData if key is None else ( self.json.allData[key] if key in self.json.allData else None )

class ADPNStagingArea :

    def __init__ (self, protocol="sftp", host="localhost", user=None, passwd=None, identity=None, base_dir="/", subdirectory=None, authentication=None) :
        self.protocol = protocol
        self.host = host
        self.user = user
        self.passwd = passwd
        self.identity = identity
        self.base_dir = base_dir
        self.subdirectory = subdirectory
        self.key_protocols = [ "sftp", "scp" ]
        self.authentication = authentication
    
    @property
    def account (self) :
        return ( "%(user)s@%(host)s" % { "user": self.user, "host": self.host } )
        
    def accept_url(self, url) :
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
            subdirectory = None
            
            self.base_dir = base_dir
            self.subdirectory = subdirectory
    
    def is_sftp (self) :
        return ( "sftp" == self.protocol )

    def uses_keyfile (self) :
        return ( self.protocol in self.key_protocols )
        
    def get_private_keyfile (self) :
        keyfile = None
        
        if self.uses_keyfile() :
            
            # do we have an explicitly specified identity / key file?
            if self.identity is not None :
                candidate_paths = [ os.path.realpath(os.path.expanduser(self.identity)) ]
                
            # can we figure out an implicit identity / key file based on defaults?
            else :
                candidates = [ "id_rsa", "id_dsa", "identity" ]
                ssh_dir = os.path.expanduser("~/.ssh")
                candidate_paths = [ os.path.join(os.path.expanduser(ssh_dir), candidate) for candidate in candidates ]
                
            keyfiles = [ path for path in candidate_paths if os.path.exists(path) ]
            
            if len(keyfiles) > 0 :
                keyfile = keyfiles[0]
            
        return keyfile
        
    def has_private_keyfile (self) :
        return ( self.authentication != "password" ) and ( self.get_private_keyfile() is not None )
    
    def get_password_prompt (self) :
        passwd_prompt=( "%(protocol)s password: " % {"protocol": self.protocol.upper()} )
        if self.has_private_keyfile() :
            passwd_prompt = "%(protocol)s private key passphrase (%(user)s@%(host)s): " % {"protocol": self.protocol.upper(), "user": self.user, "host": self.host}
        else :
            passwd_prompt = "%(protocol)s password (%(user)s@%(host)s): " % {"protocol": self.protocol.upper(), "user": self.user, "host": self.host}
        return passwd_prompt
        
    def open_connection (self) :
        if self.is_sftp() :
            
            # check for an id_rsa or identity file
            if self.has_private_keyfile() :
                passwd = None
                private_key = self.get_private_keyfile()
                private_key_pass = self.passwd
            else :
                passwd = self.passwd
                ( private_key, private_key_pass ) = ( None, None )
                
            conn = pysftp.Connection(self.host, username=self.user, password=passwd, private_key=private_key, private_key_pass=private_key_pass)
                
        else :
            conn = FTP(self.host, user=self.user, passwd=self.passwd)
        
        return myFTPStaging(conn, user=self.user, host=self.host) if conn is not None else None

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
        self.stage = ADPNStagingArea()
        self._package = None
        
        # now unpack and overlay elements from the SFTP/FTP URL, if any is provided
        stage_base = self.switches.get('stage/base') if self.switches.get('stage/base') is not None else None
        if stage_base is not None :
            self.stage.accept_url(stage_base)
        
        # now overlay any further values from the command-line switches, if provided
        self.stage.protocol=self.switches.get('protocol') if self.switches.get('protocol') is not None else self.stage.protocol
        self.stage.host=self.switches.get('host') if self.switches.get('host') is not None else self.stage.host
        self.stage.user=self.switches.get('user') if self.switches.get('user') is not None else self.stage.user
        self.stage.passwd=self.switches.get('pass') if self.switches.get('pass') is not None else self.stage.passwd
        self.stage.base_dir=self.switches.get('base_dir') if switches.get('base_dir') is not None else self.stage.base_dir
        self.stage.identity=self.switches.get('identity') if self.switches.get('identity') is not None else self.stage.identity
        self.stage.subdirectory=self.subdirectory_switch if self.subdirectory_switch is not None else self.stage.subdirectory
        self.stage.authentication=self.get_authentication_method()

        self.manifest["institution_code"] = self.stage.user

    @property
    def subdirectory_switch (self) :
        return self.switches.get('directory') if switches.get('directory') is not None else self.switches.get('subdirectory')
        
    @subdirectory_switch.setter
    def subdirectory_switch (self, rhs) :
        self.switches['subdirectory'] = rhs
        self.switches['directory'] = rhs
    
    @property
    def skip_steps (self) :
        return [ step.strip().lower() for step in self.switches.get('skip').split(",") ] if self.switched('skip') else [ ]
    
    def test_skip (self, step) :
        return ( ( step.strip().lower() ) in self.skip_steps )
    
    def get_locallocation (self) :
        return os.path.realpath(self.switches.get('local'))
        
    def get_authentication_method (self) :
        if not self.stage.uses_keyfile() :
            method = "password"
        elif self.switches.get("authentication") is not None :
            method = self.switches.get("authentication")
        elif self.switches.get("password") is not None :
            method = "password"
        else :
            method = None
        return method
        
    @property
    def package (self) :
        return self._package
    
    @package.setter
    def package (self, rhs) :
        self._package = rhs
        
    def switched (self, key) :
        got = not not self.switches.get(key, None)
        return got
    
    def get_itemparent (self, file) :
        canonical = os.path.realpath(file)
        return os.path.dirname(canonical)

    def get_username (self) :
        return self.switches.get("user/realname", None) if self.switched("user/realname") else getuser()
    
    def get_email (self) :
        return self.switches.get("user/email", None) if self.switched("user/email") else self.stage.account
    
    def get_emailname (self) :
        return ( "%(realname)s <%(email)s>" % { "realname": self.get_username(), "email": self.get_email() } )
        
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

        backupPath="%(backup)s/%(subdirectory)s" % {"backup": backupPath, "subdirectory": self.subdirectory_switch}
        try :
            os.mkdir(backupPath)
        except FileExistsError as e :
            pass

        return backupPath
    
    def exclude_filesystem_artifacts (self, file) :
        return file.lower() in ['thumbs.db']
        
    def read_password (self) :
        return getpass(self.stage.get_password_prompt())

    def establish_connection (self, interactive=True) :
        if self.stage.user is None :
            self.stage.user = input("User: ")
        if self.stage.passwd is None :
            self.stage.passwd = self.read_password()
        
        conn = None
        try :
            conn = self.stage.open_connection()
        except ValueError as e :
            if len(self.stage.passwd) == 0 :
                settings = { "protocol": self.stage.protocol.upper(), "key": self.stage.get_private_keyfile(), "err": str(e) }
                self.write_error(1, "%(protocol)s key failure. Did you use the right passphrase for the key [%(key)s]?" % settings)
            else :
                raise
        except ssh_exception.AuthenticationException as e :
            settings = { "protocol": self.stage.protocol.upper(), "key": self.stage.get_private_keyfile(), "err": str(e) }
            if self.stage.has_private_keyfile() :
                self.write_error(1, "%(protocol)s authentication failure. Did you use the right key file [%(key)s]?" % settings )
            else :
                self.write_error(1, "%(protocol)s authentication failure. Did you use the right password?" % settings )
        except ssh_exception.SSHException as e :
            settings = { "protocol": self.stage.protocol.upper(), "key": self.stage.get_private_keyfile(), "err": str(e) }
            if self.stage.has_private_keyfile() :
                self.write_error(1, "%(protocol)s key failure. Did you use the right passphrase for the key [%(key)s]?" % settings)
            else :
                self.write_error(1, "%(protocol)s connection failed: %(err)s." % settings)

        return conn
    
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
    
    @property
    def still_ok (self) :
        return self.exitcode == 0
    
    def write_error (self, code, message, prefix="") :
        self.exitcode = code
        print ( "%(prefix)s[%(cmd)s] %(message)s" % { "prefix": prefix, "cmd": self.scriptname, "message": message }, file=sys.stderr )

    def display_usage (self) :
        print(self.__doc__)
        self.exitcode = 0
    
    def get_au_start_url (self) :
        au_start_url = None
        
        details_list = self.package.plugin.get_details(check_parameters=True) # bolt on missing parameter(s)
        details = {}
        for detail in details_list :
            details[detail['name']] = detail['value']
        au_start_url = details['Start URL']
        return au_start_url

    def do_transfer_files (self) :
        # Let's log in to the host
        self.ftp = self.establish_connection()

        assert self.ftp is not None, { "message": ("Connection failed for %(user)s@%(host)s" % {"user": self.stage.user, "host": self.stage.host}), "code": 1 }
        
        # Let's CWD over to the repository
        try :
            self.ftp.set_remotelocation(self.stage.base_dir)
        except FileNotFoundError as e :
            raise AssertionError( { "message": ("Failed to set remote directory location: %(base_dir)s" % { "base_dir": self.stage.base_dir } ), "code": 1} ) from e
                    
        (local_pwd, remote_pwd) = self.ftp.get_location(local=True, remote=True)
                    
        if not self.test_skip("download") :
            backupDir = self.mkBackupDir()
            (local_pwd, remote_pwd) = self.ftp.set_location(dir=backupDir, remote=self.stage.subdirectory, make=True)
            self.ftp.download(file=".", exclude=self.exclude_filesystem_artifacts, notification=self.output_status)
                
        self.ftp.set_location(dir=local_pwd, remote=remote_pwd)
        (local_pwd, remote_pwd) = self.ftp.set_location(dir=self.switches['local'], remote=self.stage.subdirectory, make=True)
        self.output_status(2, "chdir", (os.getcwd(), self.ftp.get_location()))
            
        # upload the present directory recursively
        self.ftp.upload(file=".", exclude=self.exclude_filesystem_artifacts, notification=self.output_status)
        

    def execute (self) :

        try :
            if self.stage.base_dir is None or len(self.stage.base_dir) == 0:
                self.stage.base_dir = input("Base dir: ")
            if self.stage.subdirectory is None or len(self.stage.subdirectory) == 0 :
                self.subdirectory_switch = os.path.basename(self.get_locallocation())
                self.stage.subdirectory = self.subdirectory_switch
            
            # Let's determine the plugin and its parameters from the command line switches
            plugin = myLockssPlugin(jar=self.switches["jar"])
            plugin_parameters = plugin.get_parameter_keys()
            plugin_parameter_names = [ parameter["name"] for parameter in plugin_parameters ]
            plugin_parameter_map = {}
            for parameter_name in plugin_parameter_names :
                plugin_parameter_map[parameter_name] = self.switches.get(parameter_name)
            
            plugin_parameter_settings = [ [parameter, setting] for (parameter, setting) in self.switches.items() if parameter in plugin_parameter_names ]
            self.plugin_parameters = plugin_parameter_settings
            
            # Now let's plug the parameters for this package in to the package and plugin
            self.package = ADPNPreservationPackage(self.switches['local'], self.plugin_parameters, self.manifest, self.switches)

            au_start_url = self.get_au_start_url()
                
            # Now let's check the packaging
            assert self.package.has_bagit_enclosure(), { "message": "%(path)s must be packaged in BagIt format" % { "path": self.package.get_path(canonicalize=True) }, "remedy": "adpn package", "code": 2 }
            assert self.package.has_valid_manifest(), { "message": "%(path)s must be packaged with a valid LOCKSS manifest" % { "path": self.package.get_path(canonicalize=True) }, "remedy": "adpn package", "code": 2 }
                
            if self.manifest["au_file_size"] is None :
                self.manifest["au_file_size"] = self.package.reset_au_file_size()
                
            self.do_transfer_files()

            out_packet = {
            "Ingest Title": self.manifest["au_title"],
            "File Size": self.manifest["au_file_size"],
            "From Peer": self.manifest["institution_publisher_code"],
            "Plugin JAR": self.switches["jar"],
            "Start URL": au_start_url, # FIXME
            "Ingest Step": "staged",
            "Staged By": self.get_emailname(),
            "Staged To": self.stage.account,
            }
            
            for parameter in plugin_parameters :
                description = re.sub('\s*[(][^)]+[)]\s*$', '', parameter["description"])
                out_packet[description] = plugin_parameter_map[parameter["name"]]
            
            out_packet = { **out_packet, **{ "parameters": self.plugin_parameters } }
            
            self.output_status(0, "ok", out_packet)
                
        except AssertionError as e : # Parameter or precondition requirements failure
            if len(e.args) > 0 and type(e.args[0]) is dict :
                err = e.args[0]
                code = err['code'] if 'code' in err else 2
                message = ( "REQUIRED: %(message)s; try `%(remedy)s`" if "remedy" in err else "FAILED: %(message)s.") % err
                self.write_error(code, message)
            elif len(e.args) == 2 :
                ( message, req ) = e.args
                missing = [ parameter for parameter in req if self.switches.get(parameter) is None ]
                self.write_error(2, "Required parameter missing: %(missing)s" % { "missing": ", ".join(missing) })
            else :
                ( message, req ) = ( e.args[0], None )
                self.write_error(2, "Requirement failure: %(message)s" % { "message": message })
                
        except KeyboardInterrupt as e :
            self.write_error(255, "Keyboard Interrupt.", prefix="^C\n")

        finally :
            try :
                if self.ftp is not None :
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
    
    defaults={
            "ftp/host": None, "ftp/user": None, "ftp/pass": None,
            "stage/base": None, "stage/host": None, "stage/user": None, "stage/pass": None, "stage/protocol": None,
            "stage/identity": None, "identity": None,
            "stage/authentication": None, "authentication": None, "password": None,
            "user/realname": None, "user/email": None,
            "jar": None,
            "subdirectory": None, "directory": None,
            "base_dir": None, "output": "text/plain",
            "remote": None, "local": None, "backup": os.path.expanduser("~/backup"),
            "verbose": 1, "quiet": False,
            "base_url": None, "stage/base_url": None,
            "au_title": None, "au_notes": None, "au_file_size": None, "institution": None,
            "skip": None,
            "proxy": None, "port": None, "tunnel": None, "tunnel-port": None,
            "dummy": None
    }
    (sys.argv, switches) = myPyCommandLine(sys.argv, defaults=defaults, configfile=configjson, settingsgroup=["stage", "ftp", "user"]).parse()
    
    align_switches("identity", "stage/identity", switches)
    align_switches("authentication", "stage/authentication", switches)
    align_switches("directory", "subdirectory", switches)
    align_switches("base_url", "stage/base_url", switches)
    
    args = sys.argv[1:]
    
    # look for positional arguments: first argument goes to --local=...
    if switches.get('local') is None :
        if len(args) > 0 :
            ( switches['local'], args ) = shift_args(args)
    # look for positional arguments: next argument goes to --remote=...
    if switches.get('remote') is None :
        if len(args) > 0 :
            ( switches['remote'], args ) = shift_args(args)
    align_switches("remote", "stage/base", switches)
    
    pipes = ADPNScriptPipeline()
    if switches.get('local') is None :        
        # Let's pull some text off of standard input/pipeline
        local = pipes.get_data('Packaged In')
        if local :
            switches['local'] = local
    if switches.get('remote') is None :
        # Let's pull some text off of standard input/pipeline
        remote = pipes.get_data('Staged To')
        if remote :
            switches['remote'] = remote

    institution = switches["institution"]
    if switches["peer"] is not None :
        institution = "%(institution)s (%(code)s)" % { "institution": institution, "code": switches["peer"].upper() }
    institution_code = switches['stage/user']
    
    manifest = {
        "institution": switches["institution"],
        "institution_name": institution,
        "institution_code": switches['stage/user'],
        "institution_publisher_code": switches["peer"].upper(),
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
        print("FROM:", switches['local'])
        print("TO:", switches['remote'])
        print("Settings:", switches)
        print("")
        print("Defaults:", defaults)
    else :
        script.execute()

    script.exit()
    