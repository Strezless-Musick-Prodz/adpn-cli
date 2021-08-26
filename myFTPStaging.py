#!/usr/bin/python3
#
# myFTPStaging.py: provide the myFTPStaging class, a gateway to upload and download files from a file server
# using either FTP (via Python ftplib) or SFTP (via pysftp) client classes
#
# @version 2021.0629

import io, os, sys, errno, re
import ftplib, pysftp, paramiko.sftp
from io import BytesIO
from ftplib import FTP

class myFTPStaging :

    def __init__ (self, ftp, user, host, dry_run=False, skip_download=False) :
        self.ftp = ftp
        self.user = user
        self.host = host
        self.dry_run = dry_run
        self._skip_download = skip_download
    
    @property
    def skip_download (self) :
        return self._skip_download
    
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
    
    def is_directory (self, file) :
        if self.is_sftp() :
            test_directory = self.ftp.isdir(file)
        else :
            test_directory = ( '.' == file or self.get_file_size(file) is None )
        return test_directory
        
    def url_host (self) :
        return ("%(user)s@%(host)s" if self.user else "%(host)s") % {"user": self.user, "host": self.host}
    
    def url (self) :
        return "%(protocol)s://%(host)s%(path)s" % {"protocol": self.get_protocol(), "host": self.url_host(), "path": self.get_location(remote=True) }
    
    def get_location (self, remote=False, local=False) :
        remote_pwd = ( self.ftp.getcwd() if self.is_sftp() else self.ftp.pwd() )
        local_pwd = os.getcwd()
        
        if remote and local :
            result = ( local_pwd, remote_pwd )
        elif remote :
            result = ( remote_pwd )
        elif local :
            result = ( local_pwd )
        # Default to remote only...
        else :
            result = ( remote_pwd )
            
        return result
    
    def remove_item (self, file) :
        if self.dry_run :
            pass
        elif self.is_sftp() :
            self.ftp.remove(file)
        else :
            self.ftp.delete(file)
    
    def new_directoryitem (self, dir) :
        if self.dry_run :
            pass
        elif self.is_sftp() :
            self.ftp.mkdir(dir)
        else :
            self.ftp.mkd(dir)
    
    def remove_directoryitem (self, dir) :
        if self.dry_run :
            pass
        elif self.is_sftp() :
            self.ftp.rmdir(dir)
        else :
            self.ftp.rmd(dir)
    
    def set_location (self, dir=None, remote=None, make=False) :
        llast = self.get_location(local=True)
        try :
            if dir is not None :
                os.chdir(dir)
        except FileNotFoundError as e :
            if self.dry_run :
                pass
            elif make :
                os.mkdir(dir)
                os.chdir(dir)
            else :
                raise
        
        rdir = remote if remote is not None else dir
        rlast = self.set_remotelocation(dir=rdir, make=make)
        
        return (llast, rlast)
        
    def set_remotelocation (self, dir, make=False) :
        last = self.get_location(remote=True)
        
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
            
            if not self.dry_run and make :
                self.new_directoryitem(dir)
                self.set_remotelocation(dir, make=False)
            else :
                remote_file = "/".join([ self.url(), dir])
                raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), remote_file)
            
        return last
    
    def get_childitem (self) :
        return self.ftp.listdir() if self.is_sftp() else self.ftp.nlst()
    
    def test_matched (self, file) :
        if not self.skip_download :
            is_matched = self.get_file_size(file) == os.stat(file).st_size
        else :
            is_matched = True
        return is_matched
    
    def get_volume (self, location=None) :
        if self.is_sftp() :
            remote_pwd = location if location is not None else self.get_location(remote=True)
            requests = [ 'space-available', 'statvfs@openssh.com' ]
            errs = []
            request_id, sftp_message = (None, None)
            for req in requests :
                if sftp_message is None :
                    try :
                        request_id, sftp_message = self.ftp.sftp_client._request(paramiko.sftp.CMD_EXTENDED, req, remote_pwd)
                        sftp_request = req
                    except OSError as e :
                        errs.append(e)
            
            (df, packet) = ( {}, {} )
            if len(errs) > 0 and sftp_message is None :
                raise results[len(results)-1]
            elif 'space-available' == sftp_request :
                df['bytes_on_device'] = sftp_message.get_int64()
                df['unused_bytes_on_device'] = sftp_message.get_int64()
                df['bytes_available_to_user'] = sftp_message.get_int64()
                df['unused_bytes_available_to_user'] = sftp_message.get_int64()
                df['bytes_per_allocation_unit'] = sftp_message.get_int()
            elif 'statvfs@openssh.com' == sftp_request :
                packet['f_bsize'] = sftp_message.get_int64()
                packet['f_frsize'] = sftp_message.get_int64()
                packet['f_blocks'] = sftp_message.get_int64() # number of blocks
                packet['f_bfree'] = sftp_message.get_int64() # free blocks in file system
                packet['f_bavail'] = sftp_message.get_int64() # free blocks for non-root
                packet['f_files'] = sftp_message.get_int64()
                packet['f_ffree'] = sftp_message.get_int64()
                packet['f_favail'] = sftp_message.get_int64()
                packet['f_fsid'] = sftp_message.get_int64()
                packet['f_flag'] = sftp_message.get_int64()
                packet['f_namemax'] = sftp_message.get_int64()
                
                df['bytes_on_device'] = ( packet['f_bsize'] * packet['f_blocks'] )
                df['unused_bytes_on_device'] = ( packet['f_bsize'] * packet['f_bfree'] )
                df['unused_bytes_available_to_user'] = (  packet['f_bsize'] * packet['f_bavail'] )
            result = df
        else :
            raise OSError(255, "Not supported for FTP connections")
        return df
        
    def download_file (self, file = None) :
        try :
            if self.dry_run or self.skip_download :
                pass
            elif self.is_sftp() :
                self.ftp.get(file)
            else :
                self.ftp.retrbinary("RETR %(file)s" % {"file": file}, open( file, 'wb' ).write)
        except OSError :
            pass

    def download (self, file = None, exclude = None, notification = None) :
        out = notification if notification is not None else lambda level, type, arg: (level, type, arg) # NOOP
        
        if self.is_directory(file) :
            
            if '.' != file :
                
                (lpwd, rpwd) = self.set_location(dir=file, make=True)
                out(2, "chdir", self.get_location(local=True, remote=True))

            listing = [ item for item in self.get_childitem() ]
            listing.sort(key=lambda name: not re.match(r'^[Mm]anifest.*$', name))
            for subfile in listing :
                exclude_this = exclude(subfile) if exclude is not None else False
                if not exclude_this :
                    (level, type) = (1, "downloaded")
                    self.download(file=subfile, exclude=exclude, notification=notification)
                    
                else :
                    (level, type) = (2, "excluded")
                
                out(level, type, subfile)

            if '.' != file :

                self.set_location(dir=lpwd, remote=rpwd, make=False)
                out(2, "chdir", (lpwd, rpwd))
                self.remove_directoryitem(file)
                out(2, "remove_directoryitem", file)
        
        else :
            self.download_file(file=file)
            if not self.dry_run :
                if self.skip_download or self.test_matched(file) :
                    self.remove_item(file)
                out(2, "remove_item", file)
    
    def upload_file (self, blob = None, file = None) :
        if isinstance(blob, str) :
            blob = blob.encode("utf-8")
        
        if self.dry_run :
            pass
        elif self.is_sftp() :
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
            (lpwd, rpwd) = self.get_location(local=True, remote=True)
            if '.' != file :
                try :
                    (lpwd, rpwd) = self.set_location(dir=file, make=True)
                except FileNotFoundError as e :
                    if self.dry_run :
                        pass
                    else :
                        raise
                out(2, "chdir", self.get_location(local=True, remote=True))

            for subfile in os.listdir() :
                exclude_this = exclude(subfile) if exclude is not None else False
                if not exclude_this :
                    (level, type) = (1, "uploaded")
                    if self.get_file_size(subfile) != os.stat(subfile).st_size :
                        self.upload(blob=None, file=subfile, exclude=exclude, notification=notification)
                else :
                    (level, type) = (2, "excluded")
                    
                out(level, type, subfile)

            if '.' != file :
                out(2, "chdir", (lpwd, rpwd))
                self.set_location(dir=lpwd, remote=rpwd, make=False)
            
    def quit (self) :
        if self.is_sftp() :
            self.ftp.close()
        else :
            self.ftp.quit()

