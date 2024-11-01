# Use an official Python runtime as a parent image
#Choose a lightweight base image
FROM python:3.9-slim  


# Install ps package for process management
RUN apt-get update && apt-get install -y procps
# Set the working directory in the container
# Change this to your application's directory
WORKDIR /app  

# Copy the requirements file into the container
# Assumes you have a `requirements.txt` file with dependencies
COPY requirements.txt .  

# Install any dependencies specified in the requirements file
RUN pip install --no-cache-dir -r requirements.txt  

# Copy the current directory contents into the container
COPY *.py .
COPY ./templates ./templates

# Set the environment variables
ENV FLASK_APP=app.py
# Expose the port the app runs on
EXPOSE 5003

# Run the Flask app
#CMD ["flask", "run", "--host=0.0.0.0", "--port=5003"]
# Command to run the application with Gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:5003", "app:app"]