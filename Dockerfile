# ---- Base: Selenium + Chrome + Chromedriver + Xvfb --------------------------
FROM selenium/standalone-chrome:4.33.0-20250606

# ---- Install Python 3.12 ----------------------------------------------------
USER root
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
        python3.12 \
        python3.12-venv \
        python3-pip \
        gosu \
    && ln -s /usr/bin/python3.12 /usr/local/bin/python \
    && rm -rf /var/lib/apt/lists/*

# ---- Create and use working dir --------------------------------------------
WORKDIR /app

# ---- Python deps ------------------------------------------------------------
COPY ./requirements.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ---- Project files ----------------------------------------------------------
COPY ./src ./src
COPY ./alembic.ini .
COPY ./alembic ./alembic
COPY ./scripts ./scripts

# ---- Selenium ---------------------------------------------------------------
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENV DISPLAY=:99

# ---- Expose FastAPI port (and optional noVNC) -------------------------------
EXPOSE 8000 7900

# ---- Default command --------------------------------------------------------
# CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
