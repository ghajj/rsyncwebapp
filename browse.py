from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import paramiko
import stat
from yaml_handler import YAMLHandler  # Import YAML functions

# Blueprint for browsing directories
browse_blueprint = Blueprint("browse", __name__)

def get_diff_words(str1, str2):
    words1 = str1.split('/')
    words2 = str2.split('/')

    set1 = set(words1)
    set2 = set(words2)
    
    diff1 = sorted(set1 - set2, key=lambda x: words1.index(x))  # Words in str1 but not in str2, in order of appearance in str1
    diff2 = sorted(set2 - set1, key=lambda x: words2.index(x))  # Words in str2 but not in str1, in order of appearance in str2
    
    diff_words = '_'.join(diff1 + diff2)
    
    return diff_words

@browse_blueprint.route("/", methods=['GET', 'POST'])
def browse():
    if 'logged_in' not in session:
        return redirect(url_for('login'))  # Ensure 'login' endpoint exists

    server = session.get('server', '')
    username = session.get('username', '')
    private_key_path = session.get('private_key_path', '')
    passphrase = session.get('passphrase', '')
    password = session.get('password', '')

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    if "source_dir" not in session:
        page_title = "Select Source Directory" #starting page title for browse
    else:
        page_title = "Select Destination Directory"

    try:
        if private_key_path:
            pkey = paramiko.RSAKey.from_private_key_file(private_key_path, password=passphrase)
            ssh.connect(server, username=username, pkey=pkey)
        else:
            ssh.connect(server, username=username, password=password)

        sftp = ssh.open_sftp()

        current_path = request.args.get("path", "/")  # Default to root
        directory_contents = sftp.listdir_attr(current_path)

        directories = [
            {"name": item.filename, "is_directory": stat.S_ISDIR(item.st_mode)}
            for item in directory_contents
        ]

        sftp.close()

        if request.method == 'POST':
            selected_path = request.form.get("selected_path", "")
            if selected_path.startswith('//'):
                selected_path = selected_path[1:]

            if "source_dir" not in session:
                session["source_dir"] = selected_path
                flash(f"Source directory selected: {selected_path}", "success")
                return redirect(url_for("browse.browse"))  # Return to browse more
            else:
                source_dir = session.pop("source_dir", "")
                # Create a YAMLHandler instance with remote handling
                yaml_handler = YAMLHandler(use_remote=True)
                # Load YAML data
                yaml_data = yaml_handler.get_or_create_default_settings()  # Load YAML data


                # Ensure source_dir and destination_dir have a trailing slash for rsync
                source_dir = source_dir.rstrip('/') + '/'
                selected_path = selected_path.rstrip('/') + '/'

                pair_name = get_diff_words(source_dir, selected_path)

                yaml_data[server]['pairs'].append({"source_dir": source_dir, "destination_dir": selected_path, "task_name": pair_name})
                yaml_handler.save_yaml(yaml_data)  # Save the pair in YAML

                flash(f"Saved directory pair: {source_dir} and {selected_path}", "success")
                return redirect(url_for('index'))  # Redirect to the main page with correct endpoint

        return render_template("browse.html", page_title=page_title, current_path=current_path, directories=directories)

    except paramiko.SSHException as e:
        flash(f"Failed to retrieve directories: {e}", "danger")
        return redirect(url_for('login'))

    except Exception as e:
        flash(f"Unexpected error: {e}", "danger")
        return redirect(url_for('login'))
