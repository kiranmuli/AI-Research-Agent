FROM python:3.11-slim

WORKDIR /app

# Install only the libraries the web UI needs (keeps the image small; the
# optional LangChain/MCP extras are not required to run the web app).
RUN pip install --no-cache-dir \
    ollama \
    ddgs \
    requests \
    beautifulsoup4 \
    markdown \
    xhtml2pdf \
    flask

COPY . .

# Inside the container the server must listen on all interfaces. Ollama runs on
# the host, reachable at host.docker.internal on Docker Desktop (Windows/Mac);
# on Linux, run with:  --add-host host.docker.internal:host-gateway
ENV WEB_HOST=0.0.0.0 \
    WEB_PORT=5000 \
    OLLAMA_HOST=http://host.docker.internal:11434

EXPOSE 5000

CMD ["python", "web.py"]
