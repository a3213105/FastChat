"""
Inference code for ChatGLM.
Adapted from https://huggingface.co/THUDM/chatglm-6b/blob/main/modeling_chatglm.py.
"""
import re
import time
import torch
from transformers import TextIteratorStreamer
from threading import Thread
import gc

# @torch.inference_mode()
# def generate_stream_xft(
#     model,
#     tokenizer,
#     params,
#     device,
#     context_len=8192,
#     stream_interval=2,
#     judge_sent_end=False,
# ):
#     if model.model.rank == 0:
#         prompt = params["prompt"]#.strip()
#         temperature = float(params.get("temperature", 1.0))
#         repetition_penalty = float(params.get("repetition_penalty", 1.0))
#         top_p = float(params.get("top_p", 1.0))
#         max_new_tokens = int(params.get("max_new_tokens", 4096))
#         echo = params.get("echo", True)

#         inputs = tokenizer(prompt, return_tensors="pt", padding=model.config.padding).input_ids
#         input_echo_len = len(inputs[0])
#         max_len = max_new_tokens + input_echo_len
   
#         model.model.config(max_length=max_len, 
#                            num_beams=model.config.beam_width,
#                            length_penalty = repetition_penalty,
#                            num_return_sequences = model.config.num_return_sequences,
#                            early_stopping = model.config.early_stopping,
#                            eos_token_id = model.config.eos_token_id,
#                            pad_token_id = model.config.pad_token_id)
       
#         model.model.input(inputs)

#         if echo:
#         # means keep the prompt
#             output = prompt
#         else:
#             output = ""
#         output_tokens_count = 0
#         while not model.model.is_done():
#             next_tokens = model.model.forward()
#             output += tokenizer.decode(next_tokens[0])
#             output_tokens_count += len(next_tokens[0])
#             yield {
#                 "text": output,
#                 "usage": {
#                     "prompt_tokens": input_echo_len,
#                     "completion_tokens": output_tokens_count,
#                     "total_tokens": input_echo_len + output_tokens_count,
#                 },
#                 "finish_reason": None,
#             }
#             if output_tokens_count == max_new_tokens:
#                 break
#         generated_ids = model.model.finalize()
#         if output_tokens_count == max_new_tokens:
#             finish_reason = "length"
#         else :
#             finish_reason = "stop"
#         yield {
#             "text": output,
#             "usage": {
#                 "prompt_tokens": input_echo_len,
#                 "completion_tokens": output_tokens_count,
#                 "total_tokens": input_echo_len + output_tokens_count,
#             },
#             "finish_reason": finish_reason,
#         }


@torch.inference_mode()
def generate_stream_xft(
    model,
    tokenizer,
    params,
    device,
    context_len=8192,
    stream_interval=2,
    judge_sent_end=False,
):
    prompt = params["prompt"]#.strip()
    temperature = float(params.get("temperature", 1.0))
    repetition_penalty = float(params.get("repetition_penalty", 1.0))
    top_p = float(params.get("top_p", 1.0))
    max_new_tokens = int(params.get("max_new_tokens", 4096))
    echo = params.get("echo", True)

    inputs = tokenizer(prompt, return_tensors="pt", padding=model.config.padding).input_ids
    input_echo_len = len(inputs[0])
    max_len = max_new_tokens + input_echo_len

    decode_config = dict(skip_special_tokens=True, clean_up_tokenization_spaces=True)
    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, **decode_config)
    generation_kwargs = {
        "input_ids": inputs,
        "streamer": streamer,
        "max_length": max_len,
        "num_beams": model.config.beam_width,
        "length_penalty": repetition_penalty,
        "num_return_sequences": model.config.num_return_sequences,
        "early_stopping": model.config.early_stopping,
        "eos_token_id": model.config.eos_token_id,
        "pad_token_id": model.config.pad_token_id,
    }

    thread = Thread(target=model.model.generate, kwargs=generation_kwargs)
    thread.start()
    if echo:
    # means keep the prompt
        output = prompt
    else:
        output = ""
    for i, new_text in enumerate(streamer):
        output += new_text
        yield {
            "text": output,
            "usage": {
                "prompt_tokens": input_echo_len,
                "completion_tokens": i,
                "total_tokens": input_echo_len + i,
            },
            "finish_reason": None,
        }
    output = output.strip()
    if i == max_new_tokens - 1:
        finish_reason = "length"
    else :
        finish_reason = "stop"
    yield {
        "text": output,
        "usage": {
            "prompt_tokens": input_echo_len,
            "completion_tokens": i,
            "total_tokens": input_echo_len + i,
        },
        "finish_reason": finish_reason,
    }
    gc.collect()
