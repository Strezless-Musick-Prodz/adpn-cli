#!/usr/bin/python3
#
# ADPNStashEncryption.py: provide a utility class that handles a lot of the grunt work of
# encrypting and decrypting a cryptographically-secured data stash file
#
# @version 2021.0901

import base64
from Cryptodome.PublicKey import RSA
from Cryptodome.Random import get_random_bytes
from Cryptodome.Cipher import AES, PKCS1_OAEP

class ADPNStashEncryption :
    def __init__ (self) :
        self._public_key_bytes = None
        self._private_key_bytes = None
    
    @property
    def keys (self) :
        return ( self._public_key_bytes, self._private_key_bytes )
    
    @keys.setter
    def keys (self, rhs) :
        if type(rhs) is tuple or type(rhs) is list:
            ( self.public_key, self.private_key ) = rhs
        elif hasattr(rhs, 'publickey') :
            ( self.public_key, self.private_key ) = ( rhs, rhs )
        else :
            raise TypeError("Required: key pair in tuple or object", rhs)
    
    @property
    def public_key (self) :
        return RSA.import_key(self._public_key_bytes)
    
    @property
    def rsa_public_key (self) :
        return RSA.import_key(self._public_key_bytes)
        
    @public_key.setter
    def public_key (self, rhs) :
        if type(rhs) is bytes :
            self._public_key_bytes = rhs
        elif hasattr(rhs, 'publickey') :
            self._public_key_bytes = rhs.publickey().export_key()
        elif hasattr(rhs, 'export_key') :
            self._public_key_bytes = rhs.export_key()
        elif rhs is None :
            self._public_key_bytes = rhs
        else :
            raise TypeError("Required: RSA key pair or public key block", rhs)
    
    @property
    def private_key (self) :
        return RSA.import_key(self._private_key_bytes)
    
    @property
    def rsa_private_key (self) :
        return RSA.import_key(self._private_key_bytes)
        
    @private_key.setter
    def private_key (self, rhs) :
        if type(rhs) is bytes :
            self._private_key_bytes = rhs
        elif hasattr(rhs, 'export_key') :
            self._private_key_bytes = rhs.export_key()
        elif rhs is None :
            self._private_key_bytes = None
        else :
            raise TypeError("Required: RSA key pair or private key block", rhs)
    
    def encode_to_file (self, data: list) -> bytes :
        all_data = b"".join(data)
        return base64.urlsafe_b64encode(all_data)

    def decode_from_file (self, data: bytes, private_key) -> bytes :
        all_data = base64.urlsafe_b64decode(data)
        
        N0, N = ( 0, private_key.size_in_bytes() )
        enc_session_key = all_data[N0:N]
        N0, N = ( N, N+16 )
        nonce = all_data[N0:N]
        N0, N = ( N, N+16 )
        tag = all_data[N0:N]
        N0, N = ( N, len(all_data) )
        ciphertext = all_data[N0:N]
        
        return ( enc_session_key, nonce, tag, ciphertext )
    
    def generate_keypair (self, size=2048) :
        key = RSA.generate(size)
        private_key = key.export_key()
        public_key = key.publickey().export_key()
        return (public_key, private_key)
    
    def generate_session_key (self) :
        return get_random_bytes(16)
    
    def encrypt_text (self, text: str) -> bytes :
        data = text.encode("utf-8")
        
        session_key = self.generate_session_key()
        
        # Encrypt the session key with the public RSA key
        cipher_rsa = PKCS1_OAEP.new(self.rsa_public_key)
        enc_session_key = cipher_rsa.encrypt(session_key)

        # Encrypt the data with the AES session key
        cipher_aes = AES.new(session_key, AES.MODE_EAX)
        ciphertext, tag = cipher_aes.encrypt_and_digest(data)
        return self.encode_to_file([ enc_session_key, cipher_aes.nonce, tag, ciphertext])

    def decrypt_text (self, data: bytes) -> str:
        
        rsa_private_key = self.rsa_private_key
        ( enc_session_key, nonce, tag, ciphertext ) = self.decode_from_file(data, rsa_private_key)
        
        # Decrypt the session key with the private RSA key
        cipher_rsa = PKCS1_OAEP.new(rsa_private_key)
        session_key = cipher_rsa.decrypt(enc_session_key)
        
        # Decrypt the data with the AES session key
        cipher_aes = AES.new(session_key, AES.MODE_EAX, nonce)
        data = cipher_aes.decrypt_and_verify(ciphertext, tag)
        
        return data.decode("utf-8")
