# Use an official lightweight Python image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
# We also install 'gunicorn', which is an industry-standard production server for Python/Flask apps
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy the rest of the application code into the container
COPY . .

# Expose port 8080 (the port our app will run on inside the container)
EXPOSE 8080

# Copy the entrypoint script and make it executable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Command to run the app using Gunicorn (production server)
# Binding to 0.0.0.0 makes the server accessible from outside the container
CMD ["/entrypoint.sh"]
