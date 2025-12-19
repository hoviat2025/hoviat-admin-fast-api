# 1. Base Image
FROM python:3.11-slim

# 2. Set Environment Variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 3. Set Work Directory
WORKDIR /code

# 4. Install Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# 5. Copy the entire project
# This copies app/, scripts/, and everything else not in .dockerignore
COPY . .

# 6. Run the Application
# We use host 0.0.0.0 to be accessible outside the container
# We default to port 8000, but some cloud providers (like Heroku/Railway) 
# might override this via an environment variable.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]