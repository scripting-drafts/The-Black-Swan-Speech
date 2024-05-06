import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

class gpt_j_6B:
    def __init__(self):
        # Model Repository on huggingface.co
        model_id = "philschmid/gpt-j-6B-fp16-sharded"

        # Load Model and Tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)

        # we use device_map auto to automatically place all shards on the GPU to save CPU memory
        self.model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=torch.float16, device_map="auto")
        print(f"model is loaded on device {self.model.device.type}")

    def get_payload(self, payload):
        while True:
            try:                
                if len(payload) > 0:
                    input_ids = self.tokenizer(payload, return_tensors="pt").input_ids.to(self.model.device)

                    logits = self.model.generate(input_ids, do_sample=True, num_beams=1, min_length=16, max_new_tokens=128)
                    output = self.tokenizer.decode(logits[0].tolist()[len(input_ids[0]):])
                    print(f"{output.strip()}")

                    return output.strip()

                else:
                    error = "Please enter a valid payload"
                    print(error)
                    return error
                    
            except KeyboardInterrupt:
                break
        return