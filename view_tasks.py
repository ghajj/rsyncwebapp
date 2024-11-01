from flask import Blueprint, render_template, redirect, url_for, flash, session
import os
import subprocess  # For running system commands
from shAndCrontab import SHAndCRONTABHandler

# Blueprint for viewing the shell script and crontab entries
view_tasks_blueprint = Blueprint("view_tasks", __name__)


# Route to execute the shell script
@view_tasks_blueprint.route("/execute_shell_script")
def execute_shell_script():
    # Execute the shell script
    shAndCrontab = SHAndCRONTABHandler(use_remote=True)
    shAndCrontab.execute_shell_script()

    flash("Shell script executed successfully", 'success')
    script_content = shAndCrontab.view_script()
    return render_template(
                "view_shell_script.html", 
                script_content=script_content, 
                script_name=shAndCrontab.sh_script_path,  
                script_full_path=shAndCrontab.sh_script_path
            )  

# Route to view the content of the shell script
@view_tasks_blueprint.route("/view_shell_script")
def view_shell_script():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    shAndCrontab = SHAndCRONTABHandler(use_remote=True)
    script_content = shAndCrontab.view_script()
    return render_template(
                "view_shell_script.html", 
                script_content=script_content, 
                script_name=shAndCrontab.sh_script_path,  
                script_full_path=shAndCrontab.sh_script_path
            )    
# Route to view the `rsync` entries in the crontab
@view_tasks_blueprint.route("/view_crontab")
def view_crontab():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    shAndCrontab = SHAndCRONTABHandler(use_remote=True)
    rsync_entries = shAndCrontab.view_crontab()
    return render_template("view_crontab.html", rsync_entries=rsync_entries)

@view_tasks_blueprint.route("/purge_script")
def purge_script():

    shAndCrontab = SHAndCRONTABHandler(use_remote=True)
    shAndCrontab.purge_script()
    flash("Shell script purged successfully", 'success')
    script_content = shAndCrontab.view_script()
    return render_template(
                "view_shell_script.html", 
                script_content=script_content, 
                script_name=shAndCrontab.sh_script_path,  
                script_full_path=shAndCrontab.sh_script_path
            )