import os
from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify, current_app
import datetime
import ipaddress
import yaml
import threading
from ssh_connection import SSHConnection

netbios_bp = Blueprint('netbios', __name__)

scan_progress = {"total": 0, "current": 0, "netbios_names": []}


def save_netbios_names_to_server(ssh, remote_path, data):
    ssh.write_yaml_file(remote_path, data)

def load_netbios_names_from_server(ssh, remote_path):
    return ssh.read_yaml_file(remote_path)

def get_netbios_name(ip, timeout, verbose, ssh):
    try:
        start_ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        command = f"nmblookup -A {ip}"
        stdout, stderr, return_code = ssh.run_command(command, timeout=timeout)

        end_ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        delta = datetime.datetime.strptime(end_ts, '%Y-%m-%d %H:%M:%S') - datetime.datetime.strptime(start_ts, '%Y-%m-%d %H:%M:%S')
        if verbose:
            print(f" Time-spent: {delta} seconds")
        if return_code == 0:
            for line in stdout.splitlines():
                if "<00>" in line and "GROUP" not in line:
                    return line.split()[0]
        return "Unknown"
    except Exception as e:
        return f"Error: {e}"

def scan_for_netbios_names(prefix, timeout, verbose, ssh, remote_path):
    netbios_names = {}
    print("Scanning for NetBIOS names..., this may take a while...")
    ips = list(ipaddress.ip_network(prefix).hosts())
    scan_progress["total"] = len(ips)
    scan_progress["current"] = 0
    
    for ip in ips:
        ip_str = str(ip)
        netbios_name = get_netbios_name(ip_str, timeout, verbose, ssh)
        if not netbios_name.__contains__("Error"):
            netbios_names[ip_str] = netbios_name
            scan_progress["netbios_names"].append({ip_str: netbios_name})
        if verbose:
            print(f"IP: {ip_str}, NetBIOS Name: {netbios_name}")
        scan_progress["current"] += 1

    # Save netbios_names to a YAML file
    try:
        save_netbios_names_to_server(ssh, remote_path, netbios_names)
        print(f"NetBIOS names and IPs saved to '{remote_path}'")
    except Exception as e:
        print(f"Failed to save NetBIOS names to server: {e}")
    
    return netbios_names

def run_scan(prefix, timeout, verbose, server, username, password, private_key_path):
    netbios_path = f"/home/{username}/rsyncwebapp/netbios_names.yaml"
    try:
        with SSHConnection(server, username, password=password, private_key_path=private_key_path) as ssh:
            scan_for_netbios_names(prefix, timeout, verbose, ssh, netbios_path)
    except Exception as e:
        print(f"An error occurred: {e}")

@netbios_bp.route('/scan_netbios', methods=['GET', 'POST'])
def scan_netbios():
    if 'logged_in' not in session:
        return redirect(url_for('login'))  # Ensure user is logged in
    
    if request.method == 'POST':
        prefix = request.form.get('prefix', '192.168.10.0/24')
        timeout = int(request.form.get('timeout', '1'))
        verbose = request.form.get('verbose') == 'on'
        
        # Collect data from session
        server = session.get("server")
        username = session.get("username")
        password = session.get("password")
        private_key_path = session.get("private_key_path")
        
        # Run the scan in a separate thread
        thread = threading.Thread(
            target=run_scan, 
            args=(prefix, timeout, verbose, server, username, password, private_key_path)
        )
        thread.start()
    
        return redirect(url_for('.scan_netbios'))  # Redirect to the same page to show progress

    return render_template('scan_netbios.html')

@netbios_bp.route('/get_scan_progress')
def get_scan_progress():
    return jsonify(scan_progress)

@netbios_bp.route('/netbios_results')
def netbios_results():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    server = session.get("server")
    username = session.get("username")
    password = session.get("password")
    private_key_path = session.get("private_key_path")
    netbios_path = f"/home/{username}/rsyncwebapp/netbios_names.yaml"

    try:
        with SSHConnection(server, username, password=password, private_key_path=private_key_path) as ssh:
            netbios_names = load_netbios_names_from_server(ssh, netbios_path)
    except Exception as e:
        flash(f"An error occurred while loading results: {e}", "danger")
        return redirect(url_for('.scan_netbios'))

    return render_template('netbios_results.html', netbios_names=netbios_names)
