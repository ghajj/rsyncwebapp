import os
import yaml
import subprocess
from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify
from ssh_connection import SSHConnection

smb_shares_bp = Blueprint('smb_shares', __name__)

def save_smb_shares_to_server(ssh, remote_path, data):
    ssh.write_yaml_file(remote_path, data)

def load_smb_shares_from_server(ssh, remote_path):
    return ssh.read_yaml_file(remote_path)

def load_netbios_names_from_server(ssh, remote_path):
    return ssh.read_yaml_file(remote_path)

def scan_network(smb_username, smb_password, type="", verbose=True):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    server = session.get("server")
    username = session.get("username")
    password = session.get("password")
    port = session.get("port", 22)  # Default SSH port
    private_key_path = 'private_key_path' in session and session.get("private_key_path") or None

    netbios_path = f"/home/{username}/rsyncwebapp/netbios_names.yaml"
    smb_shares_path = f"/home/{username}/rsyncwebapp/smb_shares.yaml"

    try:
        with SSHConnection(server, username, password=password, private_key_path=private_key_path) as ssh:
            if not ssh.file_exists(netbios_path):
                return {"error": "No 'netbios_names.yaml' file found on the server. Use --rescan_netbios to generate it."}

            netbios_names = load_netbios_names_from_server(ssh, netbios_path)
            if not netbios_names:
                return {"error": "No NetBIOS names found in 'netbios_names.yaml'."}

            smb_shares = {}
            for ip_str, netbios_name in netbios_names.items():
                smb_command = f"smbclient -L //{ip_str} -U {smb_username}%{smb_password}"
                if verbose:
                    print(f"Command: {smb_command}")
                    print(f"Scanning {ip_str} (NetBIOS name: {netbios_name})...")

                try:
                    stdout, stderr, return_code = ssh.run_command(smb_command, timeout=60)

                    if return_code == 0:
                        start_processing = False
                        for line in stdout.splitlines():
                            if line.startswith('\t--------'):
                                start_processing = True
                                continue
                            if start_processing and line.strip():
                                parts = line.split(maxsplit=2)
                                if len(parts) >= 2:
                                    share_name = parts[0]
                                    share_type = parts[1]
                                    share_comment = parts[2] if len(parts) == 3 else ''
                                    if ip_str not in smb_shares:
                                        smb_shares[ip_str] = []
                                    if (type == 'Disk' and share_type == type) or type == '':
                                        smb_shares[ip_str].append({
                                            'NetBIOS Name': netbios_name,
                                            'IP': ip_str,
                                            'Share Name': share_name,
                                            'Share Type': share_type,
                                            'Share Comment': share_comment
                                        })

                    else:
                        if verbose:
                            print(f"No accessible shares on {ip_str} or error occurred.")
                            print(stderr)
                except subprocess.TimeoutExpired:
                    if verbose:
                        print(f"Scanning {ip_str} timed out.")
                except Exception as e:
                    if verbose:
                        print(f"An error occurred while scanning {ip_str}: {e}")

            # Save SMB shares to a YAML file on the server
            with SSHConnection(server, username, password=password, private_key_path=private_key_path) as ssh:
                save_smb_shares_to_server(ssh, smb_shares_path, smb_shares)

            print(f"SMB shares saved to '{smb_shares_path}'")
            return smb_shares

    except Exception as e:
        return {"error": f"An error occurred: {e}"}

@smb_shares_bp.route('/scan_shares', methods=['GET', 'POST'])
def scan_shares():
    if 'logged_in' not in session:
        return redirect(url_for('login'))  # Ensure user is logged in

    if request.method == 'POST':
        smb_username = request.form.get('username')
        smb_password = request.form.get('password')
        share_type = request.form.get('share_type', '')
        verbose = request.form.get('verbose') == 'on'
        
        try:
            smb_shares = scan_network(smb_username, smb_password, share_type, verbose)
            if "error" in smb_shares:
                flash(smb_shares["error"], "danger")
                return redirect(url_for('.scan_shares'))

            return redirect(url_for('.smb_shares_results'))

        except Exception as e:
            flash(f"An error occurred: {e}", "danger")
            return redirect(url_for('.scan_shares'))

    return render_template('scan_shares.html')
##################################################################################
@smb_shares_bp.route('/smb_shares_results_old')
def smb_shares_results_old():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    server = session.get("server")
    username = session.get("username")
    password = session.get("password")
    port = session.get("port", 22)  # Default SSH port
    private_key_path = 'private_key_path' in session and session.get("private_key_path") or None
    
    smb_shares_path = f"/home/{username}/rsyncwebapp/smb_shares.yaml"

    try:
        with SSHConnection(server, username, password=password, private_key_path=private_key_path) as ssh:
            smb_shares = load_smb_shares_from_server(ssh, smb_shares_path)

        if not smb_shares:
            return "No results found. Please run a scan first."

        return render_template('smb_shares_results.html', smb_shares=smb_shares)

    except Exception as e:
        flash(f"An error occurred while fetching results: {e}", "danger")
        return redirect(url_for('.scan_shares'))

################################################################################
@smb_shares_bp.route('/smb_shares_results')
def smb_shares_results():
    mount_script_content = ""
    smb_shares = ""
    # Retrieve SSH session data
    server = session.get("server")
    username = session.get("username")
    password = session.get("password")
    private_key_path = session.get("private_key_path")

    # Define remote script path
    script_path = f"/home/{username}/rsyncwebapp/mount_smb_shares.sh"
    smb_shares_path = f"/home/{username}/rsyncwebapp/smb_shares.yaml"

    # Use SSH to read the script contents
    try:
        with SSHConnection(server, username, password=password, private_key_path=private_key_path) as ssh:
            # Read the script content if it exists
            if ssh.file_exists(script_path):
                mount_script_content = ssh.read_yaml_file(script_path)
            else:
                flash("Mount script not found on the server.", "warning")
            
            smb_shares = load_smb_shares_from_server(ssh, smb_shares_path)


    except Exception as e:
        flash(f"An error occurred while retrieving smb shares data: {e}", "danger")

    return render_template("smb_shares_results.html", smb_shares=smb_shares, mount_script_content=mount_script_content)

#################################################################################################
@smb_shares_bp.route('/mount_share_old', methods=['POST'])
def mount_share_old():
    if 'logged_in' not in session:
        return redirect(url_for('login'))  # Ensure user is logged in
    
    ip = request.form.get('ip')
    share_name = request.form.get('share_name')
    netbios_name = request.form.get('netbios_name')
    mount_point = f"/mnt/{netbios_name}/{share_name}"  # Define a mount point (ensure this path is writable and exists)

    server = session.get("server")
    username = session.get("username")
    password = session.get("password")
    private_key_path = 'private_key_path' in session and session.get("private_key_path") or None
    
    mount_command = f"mount -t cifs //{ip}/{share_name} {mount_point} user"

    try:
        with SSHConnection(server, username, password=password, private_key_path=private_key_path) as ssh:
            stdout, stderr, return_code = ssh.run_command(mount_command)

            if return_code != 0:
                flash(f"Failed to mount {share_name} at {mount_point}: {stderr}", "danger")
            else:
                flash(f"Successfully mounted {share_name} at {mount_point}", "success")
                
    except Exception as e:
        flash(f"An error occurred while mounting {share_name}: {e}", "danger")

    return redirect(url_for('.smb_shares_results'))


@smb_shares_bp.route('/mount_share', methods=['POST'])
def mount_share():
    # Get data from the form
    ip = request.form.get('ip')
    netbios_name = request.form.get('netbios_name')
    share_name = request.form.get('share_name')
    
    # Retrieve session data for SSH
    server = session.get("server")
    username = session.get("username")
    password = session.get("password")
    private_key_path = session.get("private_key_path")
    smb_username = session.get("smb_username")  # assuming stored in session
    smb_password = session.get("smb_password")  # assuming stored in session
    
    # Define remote script path and mount command
    script_path = f"/home/{username}/rsyncwebapp/mount_smb_shares.sh"
    mount_point = f"/mnt/{netbios_name}/{share_name}"
    dir_create_command = f"mkdir -p {mount_point}"    
    mount_command = f"sudo mount -t cifs -o username={smb_username},password={smb_password} //{ip}/{share_name} {mount_point}\n"
    dir_create_command = f"sudo mkdir -p {mount_point}"
    # Use SSH to interact with the remote server
    try:
        with SSHConnection(server, username, password=password, private_key_path=private_key_path) as ssh:
            # Check if the script file exists
            if not ssh.file_exists(script_path):
                # Create the script with a shebang if it doesn't exist
                ssh.run_command(f"echo '#!/bin/bash' > {script_path}")
                ssh.run_command(f"chmod +x {script_path}")

            # Append the dir create to the script file
            ssh.run_command(f"echo '{dir_create_command}\n' >> {script_path}")
            # Append the mount command to the script file
            ssh.run_command(f"echo '{mount_command}' >> {script_path}")

        flash(f"Mount command for {share_name} added to script '{script_path}' on the server.", "success")
    
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")    
    return redirect(url_for('smb_shares.smb_shares_results'))
#################################################################################
#################################################################################
@smb_shares_bp.route('/clear_mount_script', methods=['POST'])
def clear_mount_script():
    # Retrieve SSH session data
    server = session.get("server")
    username = session.get("username")
    password = session.get("password")
    private_key_path = session.get("private_key_path")
    
    # Define remote script path
    script_path = f"/home/{username}/rsyncwebapp/mount_smb_shares.sh"

    # Use SSH to clear the script content
    try:
        with SSHConnection(server, username, password=password, private_key_path=private_key_path) as ssh:
            # Overwrite the file with an empty string
            ssh.run_command(f"echo '' > {script_path}")
            flash("Mount script cleared successfully.", "success")
    
    except Exception as e:
        flash(f"An error occurred while clearing the mount script: {e}", "danger")
    
    return redirect(url_for('smb_shares.smb_shares_results'))
