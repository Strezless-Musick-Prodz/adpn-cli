import io, os, sys, stat
import subprocess
import json
import urllib

class myLockssPlugin :
    
    def __init__ (self, jar) :
        self._jar = jar
    
    @property
    def jar (self) :
        return self._jar
        
    def get_manifest_filename (self) :
        return "manifest.html" #FIXME
    
class ADPNPreservationPackage :
    
    def __init__ (self, path, parameters, switches) :
        self._path = path
        self._parameters = parameters
        self._switches = switches
        self._plugin = myLockssPlugin(jar=self.switches["jar"])
    
    @property
    def path (self) :
        return self._path
        
    @property
    def parameters (self) :
        return self._parameters
    
    @property
    def switches (self) -> dict :
        return self._switches
    
    @property
    def plugin (self) -> myLockssPlugin :
        return self._plugin
    
    def get_path (self, item=None) -> str :
        path = self.path
        if item is not None :
            path = os.path.join(path, item)
        return path
        
    def has_manifest (self) -> bool :
        has_it = False
        try :
            stat_results = os.stat(self.get_path(self.plugin.get_manifest_filename()))
            has_it = stat.S_ISREG(stat_results.st_mode)
        except FileNotFoundError as e :
            pass
        return has_it
    
    def make_manifest (self) :
        try :
            jsonParams = json.dumps(self.parameters)
            cmdline = [
                "adpn-make-manifest.py",
                    "--jar="+self.switches['jar'],
                    "--parameters="+jsonParams,
                    "--local="+self.switches['local']
            ]
            if ( 'proxy' in self.switches.keys() ) and ( self.switches['proxy'] is not None ) :
                cmdline.append("--proxy="+self.switches['proxy'])
            if ( 'port' in self.switches.keys() ) and ( self.switches['port'] is not None ) :
                cmdline.append("--port="+self.switches['port'])
            if ( 'tunnel' in self.switches.keys() ) and ( self.switches['tunnel'] is not None ) :
                cmdline.append("--tunnel="+self.switches['tunnel'])
            if ( 'tunnel-port' in self.switches.keys() ) and ( self.switches['tunnel-port'] is not None ) :
                cmdline.append( "--tunnel-port="+self.switches['tunnel-port'])
            
            buf = subprocess.check_output(cmdline, encoding="utf-8")
        except subprocess.CalledProcessError as e :
            code = e.returncode
            buf = e.output
        
        return buf

