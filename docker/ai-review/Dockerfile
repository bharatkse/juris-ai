FROM ollama/ollama:latest

RUN ollama serve & \
    pid=$! && \
    sleep 5 && \
    ollama pull qwen2.5-coder:3b && \
    kill $pid
