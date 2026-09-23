FROM vllm/vllm-openai:latest

# It changes depending on the model: Qwen/Qwen2.5-VL-7B-Instruct أو meta-llama/Llama-3.2-11B-Vision-Instruct
ARG HF_MODEL_ID=Qwen/Qwen2.5-VL-7B-Instruct
ARG SERVED_NAME=Qwen2.5-VL-7B-Instruct
ENV HF_MODEL_ID=${HF_MODEL_ID}
ENV SERVED_NAME=${SERVED_NAME}

EXPOSE 8000

ENTRYPOINT ["sh", "-c", "python3 -m vllm.entrypoints.openai.api_server \
  --model $HF_MODEL_ID \
  --served-model-name $SERVED_NAME \
  --host 0.0.0.0 --port 8000 \
  --trust-remote-code"]