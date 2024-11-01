import os
import paramiko
import logging
from typing import Tuple

import yaml

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SSHConnection:
    def __init__(self, hostname: str, username: str, password: str = None, private_key_path: str = None):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.private_key_path = private_key_path
        self.client = None

    def connect(self):
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            if self.private_key_path:
                private_key = paramiko.RSAKey.from_private_key_file(self.private_key_path)
                self.client.connect(self.hostname, username=self.username, pkey=private_key)
            else:
                self.client.connect(self.hostname, username=self.username, password=self.password)
            logger.info(f"Successfully connected to {self.hostname}")
        except Exception as e:
            logger.error(f"Failed to connect to {self.hostname}: {e}")
            raise

    def disconnect(self):
        if self.client:
            self.client.close()
            logger.info(f"Disconnected from {self.hostname}")

    def run_command(self, command: str, timeout: int = 10) -> Tuple[str, str, int]:
        if not self.client:
            raise Exception("SSH client is not connected.")
        
        logger.info(f"Running command on {self.hostname}: {command}")
        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            stdout_str = stdout.read().decode('utf-8')
            stderr_str = stderr.read().decode('utf-8')
            return_code = stdout.channel.recv_exit_status()
            logger.info(f"Command executed with return code {return_code}")
            return stdout_str, stderr_str, return_code
        except Exception as e:
            logger.error(f"Failed to execute command {command} on {self.hostname}: {e}")
            raise

    def file_exists(self, remote_path: str) -> bool:
        command = f"test -f {remote_path} && echo 'exists' || echo 'not exists'"
        stdout, stderr, return_code = self.run_command(command)
        return stdout.strip() == 'exists'

    def read_yaml_file(self, remote_path: str):
        command = f"cat {remote_path}"
        stdout, stderr, return_code = self.run_command(command)
        if return_code == 0:
            return yaml.safe_load(stdout)
        else:
            raise Exception(f"Failed to read file {remote_path}: {stderr}")

    def write_yaml_file(self, remote_path: str, data):
        yaml_data = yaml.dump(data, default_flow_style=False)
        command = f"echo '{yaml_data}' > {remote_path}"
        stdout, stderr, return_code = self.run_command(command)
        if return_code != 0:
            raise Exception(f"Failed to write file {remote_path}: {stderr}")

    def read_file(self, remote_path):
        stdin, stdout, stderr = self.ssh.exec_command(f"cat {remote_path}")
        return stdout.read().decode()
    
    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.disconnect()
