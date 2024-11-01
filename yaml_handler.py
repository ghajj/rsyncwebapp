import os
import yaml
import paramiko
from flask import flash, redirect, render_template, session, url_for, current_app

class YAMLHandler:
    def __init__(self, use_remote=False, yaml_path=None):
        """Initialize the YAML handler with options for remote or local handling."""
        if current_app.config['ENV'] == 'production':
            CONFIG_YAML_FILE = 'rsyncwebapp.yml'
        else:    
            CONFIG_YAML_FILE = 'rsyncwebapp_dev.yml'
        self.use_remote = use_remote
        self.yaml_path = yaml_path or CONFIG_YAML_FILE
        self.remote_base_dir = f"/home/{session['username']}/rsyncwebapp"  # Base directory on the remote server
        self.remote_yaml_path = os.path.join(self.remote_base_dir, self.yaml_path)  # Full path to the YAML file

    def get_sftp_connection(self):
        """Establish and return an SFTP connection using session credentials."""
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        server = session.get("server")
        username = session.get("username")
        password = session.get("password")
        port = session.get("port", 22)  # Default SSH port

        if not server or not username or not password:
            return redirect(url_for('login'))

        # Establish SSH connection
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(server, username=username, password=password, port=port)

        # Open SFTP session
        return ssh.open_sftp()

    def ensure_yaml_file(self):
        """Ensure the YAML file exists on the remote or local directory; create it if it doesn't."""
        if self.use_remote:
            sftp = self.get_sftp_connection()
            try:
                # Ensure the base directory exists
                try:
                    sftp.stat(self.remote_base_dir)  # Check if the directory exists
                except IOError:
                    sftp.mkdir(self.remote_base_dir)  # Create the directory if it doesn't exist
                
                # Check if the YAML file exists, and create it if it doesn’t
                try:
                    sftp.stat(self.remote_yaml_path)  # Check if the file exists
                except IOError:
                    sftp.open(self.remote_yaml_path, 'w').close()  # Create an empty YAML file
            except Exception as e:
                raise Exception(f"Failed to ensure remote YAML file: {e}")
            finally:
                sftp.close()  # Close the SFTP connection
        else:
            # Ensure the YAML file exists locally
            local_path = os.path.join(os.getcwd(), self.yaml_path)  # Full local path
            if not os.path.exists(local_path):
                with open(local_path, 'w') as file:
                    yaml.safe_dump({}, file)  # Create an empty YAML file

    def load_yaml(self):
        """Load data from the YAML file."""
        if self.use_remote:
            return self.load_remote_yaml()
        else:
            return self.load_local_yaml()

    def load_local_yaml(self):
        """Load data from the local YAML file."""
        try:
            with open(self.yaml_path, 'r') as file:
                return yaml.safe_load(file) or {}
        except FileNotFoundError:
            return {}
        except Exception as e:
            raise Exception(f"Error loading local YAML data: {e}")

    def load_remote_yaml(self):
        """Load data from the remote YAML file using SFTP."""
        sftp = self.get_sftp_connection()
        try:
            with sftp.open(self.remote_yaml_path, "r") as file:
                return yaml.safe_load(file) or {}
        except FileNotFoundError:
            return {}
        except Exception as e:
            raise Exception(f"Error loading remote YAML data: {e}")
        finally:
            sftp.close()

    def save_yaml(self, data):
        """Save data to the YAML file."""
        if self.use_remote:
            self.save_remote_yaml(data)
        else:
            self.save_local_yaml(data)

    def save_local_yaml(self, data):
        """Save data to the local YAML file."""
        try:
            with open(self.yaml_path, 'w') as file:
                yaml.safe_dump(data, file, sort_keys=False)
        except Exception as e:
            raise Exception(f"Error saving local YAML data: {e}")

    def save_remote_yaml(self, data):
        """Save data to the remote YAML file using SFTP."""
        sftp = self.get_sftp_connection()
        try:
            with sftp.open(self.remote_yaml_path, 'w') as file:
                yaml.safe_dump(data, file, sort_keys=False)
        except Exception as e:
            raise Exception(f"Error saving remote YAML data: {e}")
        finally:
            sftp.close()

    def get_or_create_default_settings(self):
        """Retrieve or create default settings in the YAML file."""
        server = session.get("server")
        username = session.get("username")
        data = self.load_yaml()
        if not data or f"{server}" not in data:
            data.update({
                f"{server}": {
                    'log_files_dir': f"/home/{username}/rsyncwebapp/",
                    'pairs': [],
                }
            })
            self.save_yaml(data)
        return data
    
    def delete_server(self, server_name):
        """Delete a server entry from the YAML data."""
        data = self.load_yaml()
        if data and server_name in data:
            del data[server_name]
            self.save_yaml(data)
            return True
        return False
