FROM python:3.10-slim

ENV SKLEARN_ALLOW_DEPRECATED_SKLEARN_PACKAGE_INSTALL=True
ENV LANG=C.UTF-8
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal
ENV ACCEPT_GEOS=1

COPY requirements.txt /app/requirements.txt
COPY packages.txt /app/packages.txt
COPY . /app
WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    g++ \
    curl \
    git \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    libxml2-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

EXPOSE 8501
ENTRYPOINT ["streamlit", "run", "Home.py", "--server.port=8501", "--server.address=0.0.0.0"]
