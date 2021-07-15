#!/usr/bin/python3
#
# adpn-do-package.py: package a directory of files intended for preservation
# into a LOCKSS Archival Unit (AU), following conventions from ADPNet
# <http://www.adpn.org/wiki/HOWTO:_Package_files_for_staging_on_the_Drop_Server>
#
# @version 2021.0628

import io, os, sys
import fileinput, stat
import re, json
import urllib
from paramiko import ssh_exception
from datetime import datetime
from getpass import getpass, getuser
from myLockssScripts import myPyCommandLine, myPyJSON, align_switches, shift_args
from ADPNPreservationPackage import ADPNPreservationPackage, myLockssPlugin

python_std_input = input
def input (*args) :
    old_stdout = sys.stdout
    try :
        sys.stdout = sys.stderr
        return python_std_input(*args)
    finally :
        sys.stdout = old_stdout

class ADPNStageContentScript :
    """
Usage: adpn-do-package.py [<PATH>] [<OPTIONS>]...

  --local=<PATH>   	   	the local directory containing the files to stage
  --au_title=<TITLE>   	the human-readable title for the contents of this AU
  --subdirectory=<SLUG>	the subdirectory on the staging server to hold AU files
  --directory=<SLUG>   	identical to --subdirectory
  --backup=<PATH>      	path to store current contents (if any) of staging location
  
Output and Diagnostics:

  --output=<MIME>      	text/plain or application/json
  --verbose=<LEVEL>   	level (0-2) of diagnostic output for packaging/validation
  --quiet             	identical to --verbose=0
  
Common configuration parameters:

  --base_url=<URL>     	WWW: the URL for web access to the staging area
  --institution=<NAME>  Manifest: human-readable nmae of the institution

Default values for these parameters can be set in the JSON configuration file
adpnet.json, located in the same directory as the script. To set a default
value, add a key-value pair to the hash table with a key based on the name of
the switch. For example, to set the default value for the --institution switch
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
        self._package = None
        self._plugin = None
        self._plugin_parameters = None
        
        # FIXME: we need to figure out a good way to get this...
        self.manifest["institution_code"] = self.institution_code

    @property
    def subdirectory (self) :
        return self.switches.get('directory') if switches.get('directory') is not None else self.switches.get('subdirectory')
        
    @subdirectory.setter
    def subdirectory (self, rhs) :
        self.switches['subdirectory'] = rhs
        self.switches['directory'] = rhs
    
    @property
    def institution_code (self) :
        if self.switched('stage/user') :
            code = self.switches.get('stage/user')
        else :
            url = self.switches.get('stage/base')
            (host, user, passwd, base_dir, subdirectory) = (None, None, None, None, None)
        
            bits=urllib.parse.urlparse(url)
            if len(bits.netloc) > 0 :
                netloc = bits.netloc.split('@', 1)
                netloc.reverse()
                (host, credentials)=(netloc[0], netloc[1] if len(netloc) > 1 else None)
                credentials=credentials.split(':', 1) if credentials is not None else [None, None]
                (user, passwd) = (credentials[0], credentials[1] if len(credentials) > 1 else None)
            
            code = user
        
        return code
        
    @property
    def skip_steps (self) :
        return [ step.strip().lower() for step in self.switches.get('skip').split(",") ] if self.switched('skip') else [ ]
    
    def test_skip (self, step) :
        return ( ( step.strip().lower() ) in self.skip_steps )
    
    def get_location (self) :
        return os.path.realpath(self.switches.get('local'))
    
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

    def exclude_filesystem_artifacts (self, file) :
        return file.lower() in ['thumbs.db']
        
    def output_status (self, level, type, arg) :
        (prefix, message) = (type, arg)

        if "!" == type :
            prefix = ( "[%(cmd)s]" % { "cmd": self.scriptname } )
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
            if level > 0 :
                out=sys.stderr
            else :
                message = json.dumps(message)

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
    
    @property
    def plugin_parameters (self) :
        if self._plugin_parameters is None :
            self._plugin_parameters = self.get_plugin_parameters()
        return self._plugin_parameters
    
    @property
    def plugin (self) :
        if self._plugin is None :
            self._plugin = self.get_plugin()
        return self._plugin
        
    def get_plugin (self) :
        return myLockssPlugin(jar=self.switches["jar"])
    
    def get_plugin_parameters (self) :
        # Let's determine the plugin and its parameters from the command line switches
        return [ [parameter, setting] for (parameter, setting) in self.switches.items() if parameter in self.plugin.get_parameter_keys(names=True) ]

    def new_preservation_package (self) :
        # Now let's plug the parameters for this package in to the package and plugin
        return ADPNPreservationPackage(self.switches['local'], self.plugin_parameters, self.manifest, self.switches)

    def get_au_start_url (self) :
        au_start_url = None
        
        details_list = self.package.plugin.get_details(check_parameters=True) # bolt on missing parameter(s)
        details = {}
        for detail in details_list :
            details[detail['name']] = detail['value']
        au_start_url = details['Start URL']
        return au_start_url
        
    def execute (self) :

        try :
            if self.subdirectory is None :
                self.subdirectory = os.path.basename(self.get_location())
                self.output_status(1, "!", "Using present working directory name for staging area subdirectory: %(subdirectory)s" % { "subdirectory": self.subdirectory })
            
            self.package = self.new_preservation_package()

            # STEP 1. Confirm that we have all the plugin parameters required to produce AU Start URL
            self.output_status(2, "*", "Confirming required LOCKSS plugin parameters")
            au_start_url = self.get_au_start_url()

            # STEP 2. Check BagIt enclosure of files packaged in the AU
            if not ( self.package.has_bagit_enclosure() and self.test_skip("scan") ) :
                self.output_status(1, "*", "Checking BagIt packaging: %(path)s" % {"path": self.package.get_path(canonicalize=True)})
                self.package.make_bagit_enclosure(halt=True, validate=True)
            else :
                self.output_status(1, "*", "Skipped BagIt validation: %(path)s" % {"path": self.package.get_path(canonicalize=True)})

            # STEP 3. Request manifest HTML from MakeManifest service and write file
            if self.manifest["au_file_size"] is None :
                self.manifest["au_file_size"] = self.package.reset_au_file_size()
            if self.package.has_manifest() :
                self.output_status(1, "*", "Confirming manifest HTML: %(path)s" % { "path": self.package.plugin.get_manifest_filename() } )
                self.package.check_manifest()
            else :
                self.output_status(1, "*", "Requesting LOCKSS manifest HTML from service: %(path)s" % { "path": self.package.plugin.get_manifest_filename() } )
                self.package.make_manifest()
                
            out_packet = {
            "Ingest Title": self.manifest["au_title"],
            "File Size": self.manifest["au_file_size"],
            "From Peer": self.manifest["institution_publisher_code"],
            "Plugin JAR": self.switches["jar"],
            "Start URL": au_start_url, # FIXME
            "Ingest Step": "packaged",
            "Packaged In": self.package.get_path(canonicalize=True)
            }
            
            for parameter in self.plugin.get_parameter_keys(names=True) :
                if self.switches.get(parameter) :
                    self.plugin.set_parameter(parameter, self.switches.get(parameter))

            plugin_settings = self.plugin.get_parameters(mapped=True)
            for parameter in self.plugin.get_parameter_keys() :
                description = re.sub('\s*[(][^)]+[)]\s*$', '', parameter["description"])
                out_packet[description] = plugin_settings[parameter["name"]]
            out_packet = { **out_packet, **{ "parameters": self.plugin_parameters } }
            
            self.output_status(0, "ok", out_packet)

        except AssertionError as e : # Parameter requirements failure
            if "BagIt" == e.args[0] :
                self.write_error((100 + e.args[3]), "%(message)s on %(path)s, exit code %(code)d. Output:" % {
                    "message": e.args[1],
                    "path": os.path.realpath(e.args[2]),
                    "code": e.args[3]
                })
                print ( "\n".join(e.args[4]), file=sys.stderr)
            elif "manifest" == e.args[0] :
                self.write_error(4, "%(message)s for %(path)s. Required boilerplate: %(phrase)s" % {
                    "message": e.args[1],
                    "path": os.path.realpath(e.args[2]),
                    "phrase": e.args[3]
                })
            elif len(e.args) == 2 :
                ( message, req ) = e.args
                missing = [ parameter for parameter in req if self.switches.get(parameter) is None ]
                self.write_error(2, "Required parameter missing: %(missing)s" % { "missing": ", ".join(missing) })
            else :
                ( message, req ) = ( e.args[0], None )
                self.write_error(2, "Requirement failure: %(message)s" % { "message": message })

        except KeyboardInterrupt as e :
            self.write_error(255, "Keyboard Interrupt.", prefix="^C\n")

        except FileNotFoundError as e :
            if 3 == self.exitcode :
                pass
            else :
                raise

    def exit (self) :
        sys.exit(self.exitcode)

if __name__ == '__main__':

    scriptname = os.path.basename(sys.argv[0])
    scriptdir = os.path.dirname(sys.argv[0])
    configjson = "/".join([scriptdir, "adpnet.json"])
    
    os.environ["PATH"] = ":".join( [ scriptdir, os.environ["PATH"] ] )
    
    (sys.argv, switches) = myPyCommandLine(sys.argv, defaults={
            "stage/base": None, "stage/host": None, "stage/user": None, "stage/pass": None, "stage/protocol": None,
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
    }, configfile=configjson, settingsgroup=["stage", "ftp", "user"]).parse()
    
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
        print("Defaults:", defaults)
        print("")
        print("Settings:", switches)
    else :
        script.execute()

    script.exit()
    