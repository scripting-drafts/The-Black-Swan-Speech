import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import warnings
import os

# Set environment variable to suppress warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Suppress specific tokenizer warnings
warnings.filterwarnings("ignore", message="Using pad_token, but it is not set yet")
warnings.filterwarnings("ignore", message=".*pad_token.*", category=UserWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="transformers")

class gpt_j_6B:
    def __init__(self):
        # Model Repository on huggingface.co
        model_id = "philschmid/gpt-j-6B-fp16-sharded"

        # Load Model and Tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_id,
            pad_token='<|endoftext|>',
            padding_side='left'
        )
        
        # Ensure pad token is properly set
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id
            
        # Print confirmation
        print(f"Pad token set to: {self.tokenizer.pad_token} (ID: {self.tokenizer.pad_token_id})")

        # we use device_map auto to automatically place all shards on the GPU to save CPU memory
        self.model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.float16, device_map="auto")
        print(f"model is loaded on device {self.model.device.type}")

    def get_payload(self, payload, **kwargs):
        while True:
            try:                
                if len(payload) > 0:
                    # Tokenize with attention mask and pad token
                    inputs = self.tokenizer(
                        payload, 
                        return_tensors="pt", 
                        padding=True, 
                        truncation=True,
                        return_attention_mask=True
                    )
                    input_ids = inputs.input_ids.to(self.model.device)
                    attention_mask = inputs.attention_mask.to(self.model.device)

                    # Extract generation parameters from kwargs
                    generation_kwargs = {
                        'do_sample': True,
                        'num_beams': 1,
                        'min_length': 16,
                        'max_new_tokens': kwargs.get('max_tokens', 128),
                        'temperature': kwargs.get('temperature', 1.0),
                        'top_p': kwargs.get('top_p', 1.0),
                        'attention_mask': attention_mask,
                        'pad_token_id': self.tokenizer.pad_token_id
                    }

                    logits = self.model.generate(input_ids, **generation_kwargs)
                    output = self.tokenizer.decode(logits[0].tolist()[len(input_ids[0]):], skip_special_tokens=True)
                    print(f"{output.strip()}")

                    return output.strip()

                else:
                    error = "Please enter a valid payload"
                    print(error)
                    return error
                    
            except KeyboardInterrupt:
                break
        return