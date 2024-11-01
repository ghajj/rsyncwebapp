from flask import Blueprint, render_template, redirect, url_for, request, flash, session
import os
import yaml
from yaml_handler import YAMLHandler

server_management_blueprint = Blueprint('server_management', __name__)


@server_management_blueprint.route('/servers', methods=['GET', 'POST'])
def servers():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    yaml_handler = YAMLHandler(use_remote=True)
    data = yaml_handler.load_yaml()
    servers = data.keys()

    if request.method == 'POST':
        old_name = request.form.get('old_name')
        new_name = request.form.get('new_name')
        if old_name in data:
            data[new_name] = data.pop(old_name)
            yaml_handler.save_yaml(data)
            flash(f"Server '{old_name}' renamed to '{new_name}'", 'success')
        else:
            flash(f"Server '{old_name}' not found", 'danger')
        return redirect(url_for('server_management.servers'))

    return render_template('server_management.html', servers=servers)

@server_management_blueprint.route('/delete_server/<server_name>', methods=['POST'])
def delete_server(server_name):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    yaml_handler = YAMLHandler(use_remote=True)
    if yaml_handler.delete_server(server_name):
        flash(f"Server {server_name} deleted successfully", "success")
    else:
        flash(f"Server {server_name} not found", "danger")

    return redirect(url_for('server_management.servers'))

