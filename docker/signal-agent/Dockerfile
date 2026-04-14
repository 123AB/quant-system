FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir --upgrade pip setuptools

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY src/ ./src/

ENV TZ=Asia/Shanghai
CMD ["python", "-m", "src.signal_agent.main"]
