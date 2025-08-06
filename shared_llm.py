from llama_cpp import Llama

llm = Llama(
    model_path="./models/phi-2.Q2_K.gguf",
    n_ctx=1024,
    n_threads=4 
)