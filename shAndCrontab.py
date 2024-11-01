import subprocess
import tempfile
from flask import redirect, url_for, flash, session, current_app
import os
import paramiko

class SHAndCRONTABHandler:
    def __init__(self, use_remote=False, sh_script_path=None):
        # Define the path to the logfile for rsync output
        # Path to the shell script where rsync commands will be stored
        if current_app.config['ENV'] == 'production':
            RSYNC_SCRIPT_NAME = "rsyncwebapp.sh"  
        else:
            RSYNC_SCRIPT_NAME = "rsyncwebapp_dev.sh"  
        self.use_remote = use_remote
        self.sh_script_path = sh_script_path or RSYNC_SCRIPT_NAME
        self.remote_base_dir = "/home/"+session['username']+'/rsyncwebapp' # Base directory on the remote server
        self.ensure_sh_script_file()
    
    def get_ssh_connection(self):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        server = session.get("server")
        username = session.get("username")
        password = session.get("password")
        port = session.get("port", 22)  # Default SSH port

        if not server or not username or not password:
            return redirect(url_for('login'))

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(server, username=username, password=password, port=port)

        return ssh

    def get_sftp_connection(self):
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

    def ensure_sh_script_file(self):
        """Ensure the sh_script file exists in the current directory; create it if it doesn't."""
        if self.use_remote:
            sftp = self.get_sftp_connection()  # Establish SFTP connection
            try:
                # Use the remote base directory to derive the path
                remote_path = os.path.join(self.remote_base_dir, self.sh_script_path)  # Construct the full path
                try:
                    sftp.stat(remote_path)  # Check if the file exists
                except IOError:
                    # If the file doesn't exist, create it
                    sftp.open(remote_path, 'w').close()  # Create an empty sh_script file
            except Exception as e:
                raise Exception(f"Failed to ensure remote sh script file: {e}")
            finally:
                sftp.close()  # Close the SFTP connection to avoid resource leaks
        else:
            # Work with local files in the current working directory
            current_dir = os.getcwd()  # Get the current working directory
            local_path = os.path.join(current_dir, self.sh_script_path)  # Get the full local path
            if not os.path.exists(local_path):
                with open(local_path, 'w') as file:
                    file.write("").close()  # Create an empty sh_script file

    
    def add_to_local_script(self, rsync_command):
        """Adds the rsync command to the local shell script, avoiding duplicates."""
        current_dir = os.getcwd()  # Get the current working directory
        local_path = os.path.join(current_dir, self.sh_script_path)  # Get the full local path
        
        with open(local_path, 'r') as file:
            script_content = file.read()
            if rsync_command not in script_content:
                with open(local_path, 'a') as file:
                    file.write(f"\n{rsync_command}")
    def add_to_remote_script(self, rsync_command):
        """Adds the rsync command to the remote shell script, avoiding duplicates."""
        sftp = self.get_sftp_connection()  # Establish SFTP connection
        try:
            # Use the remote base directory to derive the path
            remote_path = os.path.join(self.remote_base_dir, self.sh_script_path)  # Construct the full path
            
            # Open the file in read mode and check if the command already exists
            with sftp.open(remote_path, 'r') as file:
                script_content = file.read().decode()
                if rsync_command not in script_content:
                    with sftp.open(remote_path, 'a') as file:
                        file.write(f"\n{rsync_command}")
        except Exception as e:
            raise Exception(f"Failed to add command to remote script: {e}")
        finally:
            sftp.close()  # Close the SFTP connection to avoid resource leaks

    def add_to_script(self, rsync_command):
        """Adds the rsync command to the shell script, avoiding duplicates."""
        if self.use_remote:
            self.add_to_remote_script(rsync_command)
        else:
            self.add_to_local_script(rsync_command)

#################################################################################
    def remove_from_remote_script(self, pair):
        """Removes the rsync command from the remote shell script."""
        sftp = self.get_sftp_connection()  # Establish SFTP connection
        try:
            # Use the remote base directory to derive the path
            remote_path = os.path.join(self.remote_base_dir, self.sh_script_path)  # Construct the full path
            
            # Read the content of the remote file
            with sftp.open(remote_path, 'r') as file:
                script_content = file.read().decode()

                source = pair.get("source_dir", "")
                destination = pair.get("destination_dir", "")

                #updated_lines = [line for line in script_lines if source not in line and destination not in line]

                updated_content = '\n'.join(line for line in script_content.split('\n')
                                            if f"{source} {destination}" not in line)
            
            # Update the file with the new content
            with sftp.open(remote_path, 'w') as file:
                file.write(updated_content)
        except Exception as e:
            raise Exception(f"Failed to remove command from remote script: {e}")
        finally:
            sftp.close()  # Close the SFTP connection to avoid resource leaks
#################################################################################
    def purge_remote_script(self):
        """Removes the rsync command from the remote shell script."""
        sftp = self.get_sftp_connection()  # Establish SFTP connection
        try:
            # Use the remote base directory to derive the path
            remote_path = os.path.join(self.remote_base_dir, self.sh_script_path)  # Construct the full path
            
            # Update the file with the new content
            with sftp.open(remote_path, 'w') as file:
                file.write("")
        except Exception as e:
            raise Exception(f"Failed to purge remote script: {e}")
        finally:
            sftp.close()  # Close the SFTP connection to avoid resource leaks
############################################################################### 
    def remove_from_local_script(self, pair):
        """Removes the rsync command from the local shell script."""
        current_dir = os.getcwd()  # Get the current working directory
        local_path = os.path.join(current_dir, self.sh_script_path)  # Get the full local path
        
        # Read the content of the local file
        with open(local_path, 'r') as file:
            script_content = file.read()
            updated_content = '\n'.join(line for line in script_content.split('\n')
                                        if f"{pair.source_dir} {pair.destination_dir}" not in line)
        
        # Update the file with the new content
        with open(local_path, 'w') as file:
            file.write(updated_content)
###############################################################################
    def purge_local_script(self):
        """Removes the rsync command from the local shell script."""
        current_dir = os.getcwd()  # Get the current working directory
        local_path = os.path.join(current_dir, self.sh_script_path)  # Get the full local path               
        # Clear the content of the local file
        with open(local_path, 'w') as file:
            file.write("")
###############################################################################
    def remove_from_script(self, pair):
        """Removes the rsync command from the shell script."""
        if self.use_remote:
            self.remove_from_remote_script(pair)
        else:
            self.remove_from_local_script(pair)
    
    def purge_script(self):
        """Removes all rsync command from the shell script."""
        if self.use_remote:
            self.purge_remote_script()
        else:
            self.purge_local_script()
     
    def update_script(self, rsync_command, pair):
        """Updates the shell script with the specified rsync command."""
        self.remove_from_script(pair)
        self.add_to_script(rsync_command)

    def view_script(self):
        """View the content of the shell script."""
        if self.use_remote:
            return self.view_remote_script()
        else:
            return self.view_local_script()

    def view_local_script(self):
        """View the content of the local shell script."""
        current_dir = os.getcwd()  # Get the current working directory
        local_path = os.path.join(current_dir, self.sh_script_path)  # Get the full local path
        
        with open(local_path, 'r') as file:
            script_content = file.read()
        if not script_content:
            script_content = "No commands added yet"
        return script_content

    def view_remote_script(self):
        """View the content of the remote shell script."""
        try:
            # Use SFTP to view the content of the remote file
            sftp = self.get_sftp_connection()
            remote_path = os.path.join(self.remote_base_dir, self.sh_script_path)
            with sftp.open(remote_path, 'r') as file:
                script_content = file.read().decode()
            if not script_content:
                script_content = "No commands added yet"
            return script_content
        except Exception as e:
            raise Exception(f"Failed to view remote script: {e}")
        finally:
            sftp.close()  # Close the SFTP connection to avoid resource leaks
    
    def execute_remote_script(self):
        """Executes the remote shell script."""
        try:
            # Use ssh to execute the script
            ssh = self.get_ssh_connection()
            ssh.exec_command(f"bash {self.sh_script_path}")
        except Exception as e:
            raise Exception(f"Failed to execute remote script: {e}")
        finally:
            ssh.close()  # Close the SSH connection to avoid resource leaks
        return "Shell script executed successfully"
            
    def execute_local_script(self):
        """Executes the local shell script."""
        current_dir = os.getcwd()  # Get the current working directory
        local_path = os.path.join(current_dir, self.sh_script_path)  # Get the full local path
        subprocess.run(["bash", local_path])
        return "Shell script executed successfully"

    def execute_shell_script(self):
        """Executes the shell script."""
        if self.use_remote:
            return self.execute_remote_script()
        else:
            return self.execute_local_script()  
###############################################################################
################### CRONTAB FUNCTIONS #########################################
###############################################################################
    def add_to_remote_crontab_delete(self, rsync_command, schedule):
        """Adds the rsync command to the remote crontab with the specified schedule."""
        if not self.use_remote:
            raise Exception("Cannot add to remote crontab if not using remote")
        try:
            # Use ssh to edit the crontab table
            ssh = self.get_ssh_connection()
            stdin, stdout, stderr = ssh.exec_command("crontab -l")
            current_crontab = stdout.read().decode().splitlines()

            # Build the cron expression
            minute = schedule.get("minute", 0)
            hour = schedule.get("hour", 0)
            cron_expr = f"{minute} {hour} * * * {rsync_command}"

            # Add the new cron entry to the current crontab
            updated_crontab = current_crontab + [cron_expr]

            # Join the updated list with newlines to avoid f-string backslash issues
            crontab_content = "\n".join(updated_crontab)
            crontab_content += "\n" # Crontab need new line at the end

            # Write the crontab_content to a temporary file
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_file.write(crontab_content.encode())
                tmp_file_path = tmp_file.name
            print("tmp_file_path:", tmp_file_path)
            # Use ssh to update the crontab using the temporary file
            stdin, stdout, stderr = ssh.exec_command(f"crontab {tmp_file_path}")
            if stderr.read().decode():
                raise Exception(f"Failed to update crontab: {stderr.read().decode()}")
        except Exception as e:
            raise Exception(f"Failed to add command to remote crontab: {e}")

    
    def remove_from_remote_crontab_delete(self, pair):
        """Removes crontab entries matching the specified rsync command using SSH."""
        #flash(f" DEBUGRemoving from remote crontab pair: {pair}", "info")
        if not self.use_remote:
            return
        try:
            # Use ssh to edit the crontab table
            ssh = self.get_ssh_connection()
            stdin, stdout, stderr = ssh.exec_command("crontab -l")
            current_crontab = stdout.read().decode().splitlines()

            source = pair.get("source_dir", "")
            destination = pair.get("destination_dir", "")
            updated_crontab = []
            for line in current_crontab:
                if source in line and destination in line:
                    print(f"Removed command from crontab: {line}")
                    flash(f"Removed command from crontab: {line}", "info")
                    continue
                else:
                    updated_crontab.append(line)

            # Join the updated list with newlines to avoid f-string backslash issues
            crontab_content = "\n".join(updated_crontab)
            crontab_content += "\n" # Crontab need new line at the end

            # Write the crontab_content to a temporary file
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_file.write(crontab_content.encode())
                tmp_file_path = tmp_file.name

            # Use ssh to update the crontab using the temporary file
            stdin, stdout, stderr = ssh.exec_command(f"crontab {tmp_file_path}")

            if stderr.read().decode():
                flash(f"Failed to remove command from crontab, stderr.read().decode(): {stderr.read().decode()}", "danger")
                raise Exception(f"Failed to update crontab: {stderr.read().decode()}")
        except Exception as e:
            flash(f"Failed to remove command from crontab: {e}", "danger")
            raise Exception(f"Failed to remove command from remote crontab: {e}")

    
    def remove_from_local_crontab_delete(self, pair):
        """Removes crontab entries matching the specified rsync command."""
        try:
            # Use ssh to edit the crontab table
            source = pair.get("source_dir", "")
            destination = pair.get("destination_dir", "")
            crontab_content = []
            with open("/etc/crontab", "r") as crontab_file:
                for line in crontab_file:
                    if source not in line and destination not in line:
                        crontab_content.append(line)
            with open("/etc/crontab", "w") as crontab_file:
                crontab_file.write("".join(crontab_content))
        except Exception as e:
            flash(f"Failed to remove command from crontab: {e}", "danger")
            raise Exception(f"Failed to remove command from crontab: {e}")

    def remove_from_crontab(self, pair):
        if self.use_remote:
            self.update_crontab(pair, rsync_command=None, schedule=None)
            return


    def update_crontab(self, pair, rsync_command=None, schedule=None):
        """Updates crontab entries matching the specified rsync command using SSH."""
        if not self.use_remote:
            raise Exception("use_remote must be True to update crontab")

        try:
            # get the current contant
            ssh = self.get_ssh_connection()
            stdin, stdout, stderr = ssh.exec_command("crontab -l")
            current_content = stdout.read().decode().splitlines()          

            # remove the current command from the content
            source = pair.get("source_dir", "")
            destination = pair.get("destination_dir", "")
            updated_content = []
            for line in current_content:
                if source in line and destination in line:
                    continue
                else:
                    updated_content.append(line)
            # remove empty lines from the end
            while len(updated_content) > 1 and updated_content[-1].strip() == "":
                updated_content.pop()

            # add the new command to the content
            if rsync_command is not None:
                minute = schedule.get("minute", 0)
                if schedule is None:
                    schedule = {}
                    minute = 0
                    hour = 0
                else:
                    minute = schedule.get("minute", 0)
                    hour = schedule.get("hour", 0)
                cron_expr = f"{minute} {hour} * * * {rsync_command}"
                updated_content.append(cron_expr)

            updated_content.append('\n') # Crontab needs new line at the end


            updated_content = "\n".join(updated_content)

            # Write the crontab_content to the crontab
            stdin, stdout, stderr = ssh.exec_command(f"echo '{updated_content}' | crontab -")                    
            stderr_output = stderr.read().decode()
            if stderr_output:
                flash(f"in update_crontab stderr after echo: {stderr_output}", "info")
            
        except Exception as e:
            flash(f"Exception in update crontab: {e}", "danger")
            raise Exception(f"Failed to add command to remote crontab: {e}")
        flash(f"Successful crontab update", "info")
    
    def display_remote_crontab(self):
        """Display the content of the remote crontab using SSH."""
        try:
            ssh = self.get_ssh_connection()
            stdin, stdout, stderr = ssh.exec_command("crontab -l")
            output = stdout.read().decode()
            error = stderr.read().decode()
            if error:
                flash(f"Crontab stderr: {error} ", "danger")
                return [f"{error}, it may need to be manually created (i.e. crontab -e)"]
            # Filter the output to only include lines containing "rsync"
            # Extract the `rsync` entries from the crontab
            rsync_entries = [
                line for line in output.splitlines()
                if "rsync" in line  # Filtering lines with `rsync`
            ]
            if rsync_entries == []:
                return ["No rsync crontab entries found."]
            return rsync_entries
        except Exception as e:
            raise Exception(f"Failed to display remote crontab: {e}")


    @staticmethod
    def display_local_crontab():
        """Display the content of the local crontab."""
        try:
            stdin, stdout, stderr = subprocess.Popen(["crontab", "-l"], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
            output = stdout.decode()
            if stderr.decode():
                raise Exception(f"Failed to read local crontab: {stderr.decode()}")
            # Filter the output to only include lines containing "rsync"
            output = "\n".join([line for line in output.splitlines() if "rsync" in line])
            if "rsync" not in output:
                return "No crontab entries found."
            return output

        except Exception as e:
            raise Exception(f"Failed to display local crontab: {e}")

    def view_crontab(self):
        """Display the content of the local and remote crontab using SSH."""
        if self.use_remote:
            return self.display_remote_crontab()
        else:
            return self.display_local_crontab()
