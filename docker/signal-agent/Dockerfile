FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir pip --upgrade

COPY pyproject.toml .
RUN pip install --no-cache-dir . 2>/dev/null || pip install --no-cache-dir akshare redis psycopg[binary] pandas httpx apscheduler langgraph langchain-openai langchain-anthropic langchain-core

COPY src/ ./src/

ENV TZ=Asia/Shanghai
CMD ["python", "-m", "src.signal_agent.main"]
