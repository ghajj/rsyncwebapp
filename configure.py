from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
import os
import paramiko
from yaml_handler import YAMLHandler
from shAndCrontab import SHAndCRONTABHandler



configure_blueprint = Blueprint("configure", __name__)


def build_rsync_command(pair):
    # Define the path to the logfile for rsync output
    # Path to the shell script where rsync commands will be stored
    name = pair.get("task_name", "")
    name = name+"_"
    if current_app.config['ENV'] == 'production':
        LOGFILE_NAME = name+"rsyncwebapp$(date +%Y%m%d_%H%M%S).log"  
    else:
        LOGFILE_NAME = name+"rsyncwebapp_dev$(date +%Y%m%d_%H%M%S).log"  
    """Loads the YAML data and builds the rsync command."""
    yaml_data = YAMLHandler(use_remote=True).load_yaml()

    """Builds the rsync command with appropriate options and logfile redirection."""
    options = []
    rsync_options = pair.get("rsync_options", {})

    if rsync_options.get("recursive"):
        options.append("-r")
    if rsync_options.get("verbose"):
        options.append("-v")
    if rsync_options.get("quiet"):
        options.append("-q")
    if rsync_options.get("archive"):
        options.append("-a")
    if rsync_options.get("dry_run"):
        options.append("--dry-run")
    if rsync_options.get("delete"):
        options.append("--delete")
    if rsync_options.get("preserve_owner"):
        options.append("--owner")
    if rsync_options.get("preserve_group"):
        options.append("--group")
    if rsync_options.get("preserve_time"):
        options.append("--times")
    if rsync_options.get("prune_empty_dirs"):
        options.append("--prune-empty-dirs")
    if rsync_options.get("preserve_xattrs"):
        options.append("--xattrs")
    if rsync_options.get("log-file"):
        server = session.get('server', '')
        log_files_dir = yaml_data[server].get("log_files_dir", "")
        if log_files_dir:
            options.append("--log-file=" + log_files_dir + "/"+LOGFILE_NAME)    # Add any extra options if provided
    extra_options = pair.get("extra_options", "")
    if extra_options:
        options.append(extra_options)

    source = pair.get("source_dir", "")
    destination = pair.get("destination_dir", "")

    # Ensure source_dir and destination_dir have a trailing slash for rsync
    source = source.rstrip('/') + '/'
    destination = destination.rstrip('/') + '/'

    # Create a YAMLHandler instance with remote handling
    yaml_handler = YAMLHandler(use_remote=True)
    # Load YAML data
    yaml_data = yaml_handler.load_yaml()
    server = session.get('server', '')
    log_files_dir = yaml_data[server].get("log_files_dir", "")

    # Construct the rsync command with output redirection
    return f"rsync {' '.join(options)} {source} {destination} >> {log_files_dir+LOGFILE_NAME} 2>&1"

@configure_blueprint.route("/<int:pair_index>", methods=['GET', 'POST'])
def configure(pair_index):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    server = session.get('server', '')
    # Create a YAMLHandler instance with remote handling
    yaml_handler = YAMLHandler(use_remote=True)
    # Load YAML data
    yaml_data = yaml_handler.load_yaml()  # Load the YAML data

    directory_pairs = yaml_data[server].get('pairs', [])

    if pair_index < 0 or pair_index >= len(directory_pairs):
        flash("Invalid pair index", "warning")
        return redirect(url_for('index'))
    
    # directory_pairs[pair_index] is linked to yaml_data
    # updating pair is effectively updating yaml_data with that index
    # Later saving yaml_data to yaml file will efectively save the pair update
    pair = directory_pairs[pair_index]

    # Initialize required keys with default values
    if "rsync_options" not in pair:
        pair["rsync_options"] = {
            "recursive": True,
            "verbose": False,
            "quiet": False,
            "archive": True,
            "dry_run": True,
            "delete": False,
            "preserve_owner": True,
            "preserve_group": True,
            "preserve_time": True,
            "prune_empty_dirs": True,
            "preserve_xattrs": True,
            "log-file": False,
        }
    if "schedule" not in pair:
        pair["schedule"] = {"hour": 0, "minute": 0}
    if "extra_options" not in pair:
        pair["extra_options"] = "--stats --exclude={.git/,__pycache__/,cache/,netdatacache/,flask_session/*,.npm/_cacache/,*.lock}"
    if "write_to_crontab" not in pair:
        pair["write_to_crontab"] = False
    if "write_to_shell_script" not in pair:
        pair["write_to_shell_script"] = True

    if request.method == 'POST':

        # Read the form data to update the configuration
        # in case we edited the paths
        pair["source_dir"] = request.form.get("source_dir")
        pair["destination_dir"] = request.form.get("destination_dir")
        pair["task_name"] = request.form.get("task_name")


        rsync_options = {
            "recursive": request.form.get("recursive") == "on",
            "verbose": request.form.get("verbose") == "on",
            "quiet": request.form.get("quiet") == "on",
            "archive": request.form.get("archive") == "on",
            "dry_run": request.form.get("dry_run") == "on",
            "delete": request.form.get("delete") == "on",
            "preserve_owner": request.form.get("preserve_owner") == "on",
            "preserve_group": request.form.get("preserve_group") == "on",
            "preserve_time": request.form.get("preserve_time") == "on",
            "prune_empty_dirs": request.form.get("prune_empty_dirs") == "on",
            "preserve_xattrs": request.form.get("preserve_xattrs") == "on",
            "log-file": request.form.get("log-file") == "on",
        }
        hour_raw = request.form.get("hour", "0")
        minute_raw = request.form.get("minute", "0")

        # Handle wildcard, with default values if invalid
        try:
            if hour_raw == "*":
                hour = "*"  # Every hour
            else:
                hour = int(hour_raw)  # Convert to integer

            if minute_raw == "*":
                minute = "*"  # Every minute
            else:
                minute = int(minute_raw)  # Convert to integer
        except ValueError:
            hour = 0  # Default if invalid
            minute = 0
            flash("Invalid hour or minute value. Defaulting to 0.", "warning")

        schedule = {
            "hour": hour,
            "minute": minute,
        }
        extra_options = request.form.get("extra_options", "")
        write_to_crontab = request.form.get("write_to_crontab") == "on"
        write_to_shell_script = request.form.get("write_to_shell_script") == "on"

        # Update the pair with new values
        pair["rsync_options"] = rsync_options
        pair["schedule"] = schedule
        pair["extra_options"] = extra_options
        pair["write_to_crontab"] = write_to_crontab
        pair["write_to_shell_script"] = write_to_shell_script

        yaml_handler.save_yaml(yaml_data)  # Persist changes to the YAML data

        rsync_command = build_rsync_command(pair)  # Build the rsync command with logfile redirection

        shAndCrontab = SHAndCRONTABHandler(use_remote=True)
        if write_to_crontab:
            # Add or update the crontab with the new schedule
            rsync_command_crontab = rsync_command.replace("%", "\\%")
            #flash(f"in configure.py rsync_command_crontab: {rsync_command_crontab}", "info")
            shAndCrontab.update_crontab(pair, rsync_command_crontab, schedule)  # Replace the current entry with the new one
        else:
            # Remove from crontab if disabled
            #flash(f"in configure.py before remove_from_crontab: { pair}", "info")
            shAndCrontab.remove_from_crontab(pair)

        if write_to_shell_script:
            # Add the command to the shell script
            shAndCrontab.update_script(rsync_command, pair)
        else:
            # Remove the command from the shell script
            shAndCrontab.remove_from_script(pair)
        
        return redirect(url_for('index'))

    return render_template("configure.html", pair=pair)  # Pass the configuration to the template
