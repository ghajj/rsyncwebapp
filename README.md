
---

# RsyncWebApp

**RsyncWebApp** is a remote server rsync configuration tool designed to streamline the setup and management of rsync tasks on remote servers. This app allows you to log in to a remote server, configure rsync tasks, and save them to a shell script or directly to `crontab` for automated execution. Additionally, RsyncWebApp can discover SMB shares and generate mount scripts for easier access and management of shared network resources.

## Features (The app has not been fully tested, please test before adoption).

- **Remote Rsync Configuration**: Log on to a remote server and configure rsync tasks for data synchronization.
- **Save to Shell or Crontab**: Save tasks to a shell script or directly to `crontab` for scheduled execution on the server.
- **Execute Commands Remotely**: Execute saved shell or crontab commands directly on the remote server.
- **SMB Share Discovery**: Discover available SMB shares and create mount scripts to connect to these shares.
- **Docker Deployment**: Quickly deploy the app using the included `docker-compose.yml` file.

## Getting Started

### Prerequisites

- **Docker** and **Docker Compose**: Ensure Docker and Docker Compose are installed on your system to use the containerized deployment option.
- **Python 3.x** and **Flask**: If running the app directly, you'll need Python 3.x and Flask installed.

### Installation and Setup

#### 1. Clone the Repository
Clone this repository to your local machine:
   ```bash
   git clone https://github.com/yourusername/rsyncwebapp.git
   cd rsyncwebapp
   ```
   Create secrets.env in the app root directory with this content
   ```bash
   SECRET_KEY='yoursupersecretkeycombination'
   ```


#### 2. Docker Deployment
To deploy using Docker Compose:
   - Start the app with the following command:
     ```bash
     docker-compose up -d
     ```
   - The app will be accessible on the ports specified in the `docker-compose.yml` file. Adjust port mappings if needed to avoid conflicts.

#### 3. Manual Deployment
If you prefer to run the app directly with Python and Flask:
   - Install the necessary dependencies:
     ```bash
     pip install -r requirements.txt
     ```
   - Start the Flask app:
     ```bash
     python app.py
     ```
   - By default, Flask will serve the app on port 5003, but this can be customized in `app.py`.

#### 4. For dev:
   ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install --no-cache-dir -r requirements.txt
    python app.py

   ```
### Usage

1. **Login to Remote Server**
   - Authenticate with a remote server using your credentials. This will allow you to set up rsync tasks and execute commands on the remote server.

2. **Configure Rsync Task**
   - Once logged in, define the rsync options, source, and destination paths. Customize rsync flags for options like `--delete` to remove extraneous files, `--archive` to preserve permissions, and more.

3. **Save and Execute**
   - Choose to save the rsync task to a shell script or directly to `crontab`. 
   - For saved tasks:
     - **Shell Script**: This creates a `.sh` file that you can execute manually or with a scheduler.
     - **Crontab**: Save tasks directly to the server’s `crontab` for automatic execution based on your specified schedule.

4. **Discover SMB Shares**
   - Use the SMB discovery tool to scan for available SMB shares within your network.
   - Generate mount scripts to easily mount SMB shares on your server or local machine.

5. **Files**
   - All yaml and shell files are in the /home/user/rsyncwebapp directory.

### Configuration

- The application’s exposed ports, network configuration, and environment variables can be adjusted within the `docker-compose.yml` file.
- The default Flask server port can also be configured in `app.py` if running outside of Docker.

### Example Docker Compose Configuration

Here’s a snippet of what your `docker-compose.yml` might look like:

```yaml
services:
  rsyncwebapp:
    hostname: rsyncwebapp-container
    build: .  # Build the Docker image from the current directory
    container_name: rsyncwebapp
    ports:
      - "8003:5003/tcp"  # Map the container port to the host port
    environment:
      FLASK_ENV: 'production'
      FLASK_APP: "app.py"
      FLASK_DEBUG: "0"
    env_file:
      - secrets.env
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /etc/localtime:/etc/localtime:ro
      - /etc/timezone:/etc/timezone:ro
      - .:/app  # Mount the current directory to the container's `/app`

```

To change the default port or environment variables, simply edit this file before running `docker-compose up`.

## Contributing

Contributions are welcome! If you'd like to contribute, please fork the repository and submit a pull request with your changes. You can also open an issue to discuss any improvements or new features.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **Flask** for the web framework.
- **Docker** and **Docker Compose** for containerization.
- **Rsync** and **SMB tools** for the core functionality.

---

**RsyncWebApp** is your streamlined solution for managing rsync tasks and SMB shares on remote servers.