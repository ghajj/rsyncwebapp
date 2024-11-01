import datetime
import stat
from flask import Blueprint, render_template, redirect, request, session, url_for, flash
import os
import glob

import paramiko  # For scanning files with specific patterns
from yaml_handler import YAMLHandler
# Create a new blueprint for scanning and managing log files
log_blueprint = Blueprint("logs", __name__)

def sftp_exists(sftp, path):
    """Check if a file or directory exists on the SFTP server."""
    try:
        sftp.stat(path)
        return True
    except FileNotFoundError:
        return False

def create_sftp_directory(sftp, path):
    """Recursively create directories on the SFTP server."""
    parts = path.split('/')
    for i in range(1, len(parts) + 1):
        dir_path = '/'.join(parts[:i])
        if dir_path and not sftp_exists(sftp, dir_path):
            sftp.mkdir(dir_path)
# Establish an SFTP connection
def get_sftp_connection():
    server = session.get("server")
    username = session.get("username")
    password = session.get("password")
    port = session.get("port", 22)  # Default SSH port

    if not server or not username or not password:
        raise ValueError("Incomplete connection details.")

    # Establish SSH connection
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(server, username=username, password=password, port=port)

    # Open SFTP session
    sftp = ssh.open_sftp()
    return sftp

# Route to browse and select a directory for log files
@log_blueprint.route("/browse_for_log_location", methods=['GET', 'POST'])
def browse_for_log_location():
    if 'logged_in' not in session:
        return redirect(url_for('login'))  # Redirect if not logged in

    # Retrieve the current browsing path, default to the root directory
    current_path = request.args.get("path", "/")
    page_title = "Select Logs Location Directory"

    sftp = None
    try:
        sftp = get_sftp_connection()  # Get the SFTP connection
        
        current_path = request.args.get("path", "/")  # Default to root
        directory_contents = sftp.listdir_attr(current_path)

        directories = [
            {"name": item.filename, "is_directory": stat.S_ISDIR(item.st_mode)}
            for item in directory_contents
        ]

        if request.method == 'POST':
            # The user selected a directory to set as the log file location
            selected_path = request.form.get("selected_path", "")
            if selected_path.startswith('//'):
                selected_path = selected_path[1:]
                session["new_log_files_dir"] = selected_path  # Store in session
                flash(f"Log files directory set to: {selected_path}", "success")
                
            if sftp_exists(sftp, selected_path):
                session["new_log_files_dir"] = selected_path  # Store in session
                flash(f"Log files directory set to: {selected_path}", "success")
            else:
                create_sftp_directory(sftp, selected_path)
                if sftp_exists(sftp, selected_path):
                    session["new_log_files_dir"] = selected_path  # Store in session
                    flash(f"Log files directory created and set to: {selected_path}", "success")
                else:
                    flash("Failed to create the new selected directory.", "danger")


                # Save the log file location to the YAML file
            if sftp_exists(sftp, selected_path):
                yaml_handler = YAMLHandler(use_remote=True)
                yaml_data = yaml_handler.load_yaml()
                server = session.get('server', '')
                yaml_data[server]["log_files_dir"]= selected_path 
                yaml_handler.save_yaml(yaml_data)
                
                return redirect(url_for("logs.list_logs"))  # Redirect to the list of logs

        return render_template("browse.html", page_title=page_title, current_path=current_path, directories=directories)

    except Exception as e:
        flash(f"An error occurred while browsing directories: {e}", "danger")
        return redirect(url_for("index"))  # Redirect to the main page on error# Route to list available log files
    finally:
        if sftp:
            sftp.close()

#################################################################################
#################################################################################

# Route to list available log files on a remote server
@log_blueprint.route("/logs", methods=['GET'])
def list_logs():
    try:
        sftp = get_sftp_connection()  # Establish the SFTP connection

        # Create a YAMLHandler instance with remote handling
        yaml_handler = YAMLHandler(use_remote=True)
        # Load YAML data
        yaml_data = yaml_handler.load_yaml()
        server = session.get('server', '')
        log_files_dir = yaml_data[server].get("log_files_dir", "")
        
        # List all .log files in the directory
        log_files = [f for f in sftp.listdir(log_files_dir) if f.endswith('.log')]
        
        log_files.sort(key=lambda f: sftp.stat(os.path.join(log_files_dir, f)).st_mtime, reverse=True)  # Sort by date modified, newest first


        log_files_with_info = []
        for log in log_files:
            file_path = os.path.join(log_files_dir, log)
            file_info = sftp.stat(file_path)  # Get file information
            modified_date = datetime.datetime.fromtimestamp(file_info.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            # Get the file size in a human-readable format
            file_size = file_info.st_size  # Retrieve the size in bytes
            file_size_str = f"{file_size / 1024:.2f} KB" if file_size < 1048576 else f"{file_size / 1048576:.2f} MB"  # Format size in KB or MB

            # Add information about each log file, including name, modified date, and size
            log_files_with_info.append({
                'name': log,
                'modified_date': modified_date,
                'size': file_size_str  # Add the file size to the information
            })
        if not log_files:
            flash("No log files found.", "info")
            message = "No log files found."
        else:
            message = f"{len(log_files)} log files found."

        server = session.get('server', '')
        log_files_dir = yaml_data[server].get("log_files_dir", "")
        return render_template("list_logs.html", log_files=log_files, message=message, 
                           log_files_location=log_files_dir, log_files_with_info=log_files_with_info)  # Pass log files to the template

    except Exception as e:
        flash(f"An error occurred while listing log files: {e}", "danger")
        return redirect(url_for("index"))  # Redirect to the main page on error

# Route to view a specific log file
@log_blueprint.route("/logs/view/<log_file>")
def view_log(log_file):
    try:
        sftp = get_sftp_connection()  # Establish the SFTP connection

        # Create a YAMLHandler instance with remote handling
        yaml_handler = YAMLHandler(use_remote=True)
        # Load YAML data
        yaml_data = yaml_handler.load_yaml()
        server = session.get('server', '')
        log_files_dir = yaml_data[server].get("log_files_dir", "")  # Get the log file location
        log_path = os.path.join(log_files_dir, log_file)

        # Check if the path is a regular file
        file_info = sftp.stat(log_path)
        if not stat.S_ISREG(file_info.st_mode):  # Ensure it's a regular file
            flash(f"'{log_path}' is not a valid log file.", "danger")
            return redirect(url_for("logs.list_logs"))

        # Read the file with explicit encoding
        with sftp.file(log_path, 'r', bufsize=4096) as file:
            # Read the content and decode it to convert from bytes to string
            content = file.read().decode("utf-8")  # Decode from bytes to string
        
        # Normalize newlines (optional, depending on the issue you're encountering)
        content = content.replace('\r\n', '\n').replace('\r', '\n')

        return render_template("view_log.html", log_file=log_file, log_content=content)

    except FileNotFoundError:
        flash(f"Log file '{log_file}' does not exist.")
        return redirect(url_for("logs.list_logs"))

    except Exception as e:
        flash(f"An error occurred while reading the log file: {e}", "danger")
        return redirect(url_for("logs.list_logs"))
    
# Route to delete a specific log file on a remote server
@log_blueprint.route("/logs/delete/<log_file>", methods=['POST'])
def delete_log(log_file):
    try:
        sftp = get_sftp_connection()  # Establish the SFTP connection

        # Create a YAMLHandler instance with remote handling
        yaml_handler = YAMLHandler(use_remote=True)
        # Load YAML data
        yaml_data = yaml_handler.load_yaml()
        server = session.get('server', '')
        log_files_dir = yaml_data[server].get("log_files_dir", "")  # Get the current log file location
        log_path = os.path.join(log_files_dir, log_file)

        # Check if the path represents a regular file
        try:
            file_info = sftp.stat(log_path)
            if not stat.S_ISREG(file_info.st_mode):  # Ensure it's a regular file
                flash(f"'{log_path}' is not a valid log file.", "danger")
                return redirect(url_for("logs.list_logs"))
        except FileNotFoundError:
            flash(f"Log file '{log_file}' does not exist.", "warning")
            return redirect(url_for("logs.list_logs"))

        # Delete the log file
        sftp.remove(log_path)  # Delete the remote log file
        flash(f"Log file '{log_file}' has been deleted.", "success")

    except Exception as e:
        flash(f"An error occurred while deleting the log file: {e}", "danger")

    return redirect(url_for("logs.list_logs"))  # Redirect back to the list of logs


@log_blueprint.route("/logs/delete_older_than", methods=['POST'])
def delete_logs_older_than():
    if 'logged_in' not in session:
        return redirect(url_for('login'))  # Redirect if not logged in

    if request.method == 'POST':
        try:
            sftp = get_sftp_connection()  # Establish the SFTP connection

            # Get the selected age threshold from the form
            age_threshold = request.form.get("age_threshold")
            print("Age threshold: ", age_threshold)
            if age_threshold is None:
                flash("Please select an age threshold.", "warning")
                return redirect(url_for("logs.list_logs"))

            delta = datetime.timedelta(days=int(age_threshold))
            print("delta: ", delta)
            if delta < datetime.timedelta(0):
                flash("Invalid age threshold selected.", "warning")
                return redirect(url_for("logs.list_logs"))

            # Calculate the cutoff date based on the current date and the age threshold
            cutoff_date = datetime.datetime.now() - delta

            # Get the log file location from session or YAML
   
            yaml_handler = YAMLHandler(use_remote=True)
            yaml_data = yaml_handler.load_yaml()
            server = session.get('server', '')
            log_files_dir = yaml_data[server].get("log_files_dir", "")
            if not log_files_dir:
                flash("Log files directory is not set.", "warning")
                return redirect(url_for("logs.browse_for_log_location"))

            # List all .log files in the directory
            log_files = [f for f in sftp.listdir(log_files_dir) if f.endswith('.log')]

            # Iterate through log files and delete those older than the cutoff date
            deleted_files = []
            for log_file in log_files:
                file_path = os.path.join(log_files_dir, log_file)
                file_info = sftp.stat(file_path)
                modified_date = datetime.datetime.fromtimestamp(file_info.st_mtime)
                if modified_date < cutoff_date:
                    sftp.remove(file_path)
                    deleted_files.append(log_file)

            flash(f"Deleted {len(deleted_files)} log files older than {age_threshold.replace('_', ' ')} days.", "success")

        except Exception as e:
            flash(f"An error occurred while deleting log files: {e}", "danger")

        return redirect(url_for("logs.list_logs"))

    return redirect(url_for("logs.list_logs"))  # Redirect back to the list of logs
