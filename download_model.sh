#!/bin/bash
mkdir -p models
cd models
echo "Downloading Phi-2 Q2_K GGUF model..."
wget https://huggingface.co/TheBloke/phi-2-GGUF/resolve/main/phi-2.Q2_K.gguf
echo "Done. Model saved to models/phi-2.Q2_K.gguf"
