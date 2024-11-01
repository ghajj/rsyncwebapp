from flask import Flask, render_template, request, redirect, url_for, flash, session
import paramiko
from flask_session import Session
import os
import logging
from yaml_handler import YAMLHandler  # Import the refactored YAML handler
from shAndCrontab import SHAndCRONTABHandler


from browse import browse_blueprint  # Blueprint for browsing directories
from configure import configure_blueprint  # Blueprint for configuring directory pairs
from logs import log_blueprint  # Import the blueprint for managing log files
from view_tasks import view_tasks_blueprint
from server_management import server_management_blueprint

from netbios import netbios_bp
from smb_shares import smb_shares_bp

app = Flask(__name__)

app.config['ENV'] = os.environ.get("FLASK_ENV", "development")

logging.basicConfig(filename='app.log', level=logging.DEBUG)

app.secret_key = os.environ.get("SECRET_KEY", "default_secret_key")
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

app.register_blueprint(browse_blueprint, url_prefix="/browse")
app.register_blueprint(configure_blueprint, url_prefix="/configure")
app.register_blueprint(log_blueprint, url_prefix="/logs")  # Optional prefix for the blueprint
app.register_blueprint(view_tasks_blueprint, url_prefix="/view_tasks")
app.register_blueprint(server_management_blueprint, url_prefix="/server_management")
# Register the NetBIOS blueprint
app.register_blueprint(netbios_bp, url_prefix='/netbios')
app.register_blueprint(smb_shares_bp)

@app.route('/')
def index():

    flash(f"app Environment = {app.config['ENV']}",'info')

    if 'logged_in' not in session:
        return redirect(url_for('login'))

    hostname = os.uname().nodename

    server = session.get('server', '')
    # Create a YAMLHandler instance with remote handling
    yaml_handler = YAMLHandler(use_remote=True)
    # Load YAML data
    yaml_data = yaml_handler.get_or_create_default_settings()  # Load YAML data

    log_files_dir = yaml_data[server].get('log_files_dir', None)
    # Get the directory pairs for the logged-in server
    if log_files_dir is None:
        log_files_dir = '/home/'+session['username']+'/rsyncwebapp'
        yaml_data[server]['log_files_dir'] = log_files_dir
        yaml_handler.save_yaml(yaml_data)

    pairs = yaml_data[server].get('pairs', [])
    if not pairs:
        pairs = []
        yaml_data[server]['pairs'] = pairs
        yaml_handler.save_yaml(yaml_data)

    # get server information
    server_data = yaml_data.get(server, []) 

    # get server information
    server_data = yaml_data.get(server, [])
    return render_template('index.html', hostname=hostname, server=server, logfiles=log_files_dir, server_data=pairs, enumerate=enumerate)  # Pass 'enumerate'

@app.route('/remove_pair/<int:pair_index>', methods=['GET'])
def remove_pair(pair_index):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    server = session.get('server', '')
    # Create a YAMLHandler instance with remote handling
    yaml_handler = YAMLHandler(use_remote=True)
    # Load YAML data
    yaml_data = yaml_handler.load_yaml()

    if server in yaml_data:
        directory_pairs = yaml_data[server].get('pairs', [])
        if 0 <= pair_index < len(directory_pairs):
            #remove from crontab and shell script if they exist
            shAndCrontab = SHAndCRONTABHandler(use_remote=True)
            shAndCrontab.remove_from_crontab(directory_pairs[pair_index])
            shAndCrontab.remove_from_script(directory_pairs[pair_index])

            del directory_pairs[pair_index]  # Remove the pair
            yaml_handler.save_yaml(yaml_data)  # Persist changes
            flash("Pair removed successfully", "info")
        else:
            flash("Invalid pair index", "warning")
    else:
        flash("Server not found", "warning")

    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    hostname = os.uname().nodename
    if request.method == 'POST':
        server = request.form.get('server', 'hp-debian').strip()
        username = request.form.get('username', 'ghassan').strip()
        password = request.form.get('password', '').strip()
        private_key_path = request.form.get('private_key_path', '').strip()
        passphrase = request.form.get('passphrase', '').strip()

        if not server or not username:
            flash("Server and username are required.", "warning")
            return render_template('login.html', hostname=hostname)

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            if private_key_path:
                if not passphrase:
                    flash("Passphrase is required for encrypted private keys.", 'warning')
                    return render_template('login.html')

                pkey = paramiko.RSAKey.from_private_key_file(private_key_path, password=passphrase)
                ssh.connect(server, username=username, pkey=pkey)
            else:
                ssh.connect(server, username=username, password=password)

            # Create the app directory to store the app files
            stdin, stdout, stderr = ssh.exec_command(f"mkdir -p /home/{username}/rsyncwebapp")
            error = stderr.read().decode().strip()
            if error:
                flash(f"Directory creation failed: {error}", "danger")
                return render_template('login.html', hostname=hostname)

            # Store session information
            session['logged_in'] = True
            session['server'] = server
            session['username'] = username
            session['password'] = password
            session['private_key_path'] = private_key_path
            session['passphrase'] = passphrase

            # Assuming YAMLHandler class and yaml operations are defined elsewhere
            yaml_handler = YAMLHandler(use_remote=True)
            yaml_handler.ensure_yaml_file()

            yaml_data = yaml_handler.load_yaml()  # Load YAML data

            return redirect(url_for('index'))
        
        except paramiko.AuthenticationException:
            flash("Invalid username or password.", "danger")
            return render_template('login.html', hostname=hostname)
        
        except paramiko.SSHException as e:
            flash(f"SSH connection failed: {e}", "danger")
            return render_template('login.html', hostname=hostname)
        
        except Exception as e:
            flash(f"Login failed: {e}", "danger")
            return render_template('login.html', hostname=hostname)

    return render_template('login.html', hostname=hostname)
    
@app.route('/logout')
def logout():
    session.clear()  # Clear session data
    return redirect(url_for('login'))

if __name__ == '__main__':
    logging.info("app config: %s\n ", app.config)
    
    app.run(debug=True, host='0.0.0.0', port=5003)
