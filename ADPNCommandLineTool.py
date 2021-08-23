#!/usr/bin/python3
#
# ADPNCommandLineTool.py: provide a base class that handles a lot of common tasks for CLI
# tools for the Python components of the ADPN-CLI scripts.
#
# @version 2021.0823

import io, os, sys, stat
import re, json, numbers
from myLockssScripts import myPyCommandLine, myPyJSON, align_switches, shift_args

class ADPNScriptPipeline :

    def __init__ (self, conditional=False, stream_in=sys.stdin) :
        self._stream_in = stream_in
        self._pipelines = None
        self._conditional = conditional
        self.json = myPyJSON()
    
    def test_piped_input (self) :
        mode = os.fstat(self._stream_in.fileno()).st_mode
        return any([stat.S_ISFIFO(mode), stat.S_ISREG(mode)])
        
    @property
    def pipelines (self) :
        if self._pipelines is None :
            if self.test_piped_input() or not self._conditional :
                text = self._stream_in.read()
                self._pipelines = [ line for line in re.split(r'[\r\n]+', text) if line ]
        return self._pipelines
    
    def get_data(self, key=None) :
        result = None
        if self.pipelines is not None :
            self.json.accept(self.pipelines)
            if key is None :
                result = self.json.allData
            else : 
                result = self.json.allData.get(key)
                if type(self.json.allData.get("parameters")) is list :
                    m = re.match(r"^[@](.*)$", key)
                    if m :
                        for pair in self.json.allData.get("parameters") :
                            if len(pair) == 2 :
                                (key, value) = pair
                                if key == m[1] :
                                    result = value
        return result
    
    def backfilled (self, table, key, data_source) :
        
        result = { **table }
        if result.get(key) is None :
        # O.K., nothing from switches; let's pull some text off stdin/pipeline
            
            value = self.get_data(data_source)
            if value is not None :
                result[key] = value
        
        return result

class ADPNCommandLineTool :
    """
Base class for ADPN command-line tools written in Python. To implement a script,
inherit from this class. For example:
    
        from ADPNCommandLineTool import ADPNCommandLineTool
        
        class ADPNStageContentScript(ADPNCommandLineTool) :
            pass
    """
    
    def __init__ (self, scriptname, argv, switches) :
        
        self.scriptname = scriptname
        self.argv = argv
        self.switches = switches
        self.exitcode = 0
        
        self.verbose=(0 if self.switches.get('quiet') else self.switches.get('verbose'))
        self.debug=self.switches.get('debug')
        if self.debug > self.verbose :
            self.verbose = self.debug
    
    @property
    def verbose (self) :
        return self._verbose
    
    @verbose.setter
    def verbose (self, rhs) :
        self._verbose = self.convertto_numeric_value(value=rhs)
    
    @property
    def debug (self) :
        return self._debug
    
    @debug.setter
    def debug (self, rhs) :
        self._debug = self.convertto_numeric_value(value=rhs)
    
    @verbose.setter
    def verbose (self, rhs) :
        if isinstance(rhs, numbers.Number) :
            self._verbose = int(rhs)
        elif type(rhs) is str :
            try :
                self._verbose = int(rhs)
            except ValueError as e :
                self._verbose = int(len(rhs) > 0)
        elif rhs is None :
            self._verbose = 0
        else :
            raise TypeError("verbose must be int, str or None")
    
    def convertto_numeric_value (self, switch=None, value=None) :
        rhs = self.switches.get(switch) if value is None else value
        
        m=re.match(r"^([0-9]+)[,].*$", rhs if type(rhs) is str else "")
        if m :
            rhs = m[1]
        
        if isinstance(rhs, numbers.Number) :
            rhs = int(rhs)
        elif type(rhs) is str :
            try :
                rhs = int(rhs)
            except ValueError as e :
                rhs = int(len(rhs) > 0)
        elif rhs is None :
            rhs = 0
        else :
            raise TypeError("%s must be int, str or None" % ( "value" if switch is None else switch ))
        return rhs

    @property
    def skip_steps (self) :
        return [ step.strip().lower() for step in self.switches.get('skip').split(",") ] if self.switched('skip') else [ ]
    
    def test_skip (self, step) :
        return ( ( step.strip().lower() ) in self.skip_steps )
        
    def switched (self, key) :
        got = not not self.switches.get(key, None)
        return got
    
    @property
    def still_ok (self) :
        return self.exitcode == 0
    
    @property
    def plain_text_output (self) :
        return ( self.switches.get('output') is None or self.switches.get('output') == 'text/plain')
    
    @property
    def json_output (self) :
        return not not re.match( r'^([^/]+/)?(json)(;.*)?$', self.switches.get('output', ''))
    
    def write_output (self, data, prolog=None, json_encode=True, end="\n", stream=sys.stdout) :
        if prolog :
            print(prolog, end="")
        
        if json_encode and self.json_output :
            print(json.dumps(data), end=end, file=stream)
        else :
            print(data, end=end, file=stream)
    
    def write_status (self, message, prolog=None, is_notice=True, verbosity=0) :
        if prolog is None :
            prefix = "[%(cmd)s] " % { "cmd": self.scriptname }
        else :
            prefix = "%(prolog)s " % { "prolog": prolog }
        
        if is_notice :
            stream = sys.stderr if ( not self.plain_text_output and verbosity > 0 ) else sys.stdout
            text = "%(prefix)s%(message)s" % { "prefix": prefix, "message": message }
        else :
            stream = sys.stdout
            text = message
        
        if verbosity <= self.verbose :
            print(text, file=stream)
    
    def write_error (self, code, message, prefix="") :
        self.exitcode = code
        print ( "%(prefix)s[%(cmd)s] %(message)s" % { "prefix": prefix, "cmd": self.scriptname, "message": message }, file=sys.stderr )

    def display_usage (self) :
        print(self.__doc__)
        self.exitcode = 0
        self.exit()
        
    def execute (self) :
        self.exit()
        
    def exit (self) :
        sys.exit(self.exitcode)

if __name__ == '__main__':

    scriptname = os.path.basename(sys.argv[0])
    scriptdir = os.path.dirname(sys.argv[0])
    configjson = "/".join([scriptdir, "adpnet.json"])
    
    os.environ["PATH"] = ":".join( [ scriptdir, os.environ["PATH"] ] )
    
    defaults={ "help": None, "version": None, "verbose": None, "debug": None }
    (sys.argv, switches) = myPyCommandLine(sys.argv, defaults=defaults, configfile=configjson).parse()
    
    # These defaults are conditional on the absence/presence of the --unstage flag:
    script = ADPNCommandLineTool(switches.get('context'), sys.argv, switches)
    
    if script.switched('help') :
        script.display_usage()
    elif script.switched('details') :
        print("FROM:", switches['local'], file=sys.stderr)
        print("TO:", switches['remote'], file=sys.stderr)
        if script.switches.get('details') in switches and script.switches.get('details') != 'details' :
            print(script.switches.get('details'), ": ", switches.get(script.switches.get('details')), file=sys.stderr)
        print("", file=sys.stderr)
        print("All Settings:", switches, file=sys.stderr)
        print("", file=sys.stderr)
        print("Defaults:", defaults, file=sys.stderr)
    else :
        script.execute()

    script.exit()
    