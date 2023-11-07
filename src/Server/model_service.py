from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import gpt4all
from ReqResBody import Request
import os
from transformers import MBartForConditionalGeneration, MBart50TokenizerFast
from nameTitleRequest import nameTitleRequest
from correctGrammar import correctGrammarRequest
from nltk.translate.bleu_score import sentence_bleu

from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

correction_model = AutoModelForSeq2SeqLM.from_pretrained("./v5/model")
correction_tokenizer = AutoTokenizer.from_pretrained("./v5/tokenizer")

if not os.path.exists('./translation_model'):
    translation_model = MBartForConditionalGeneration.from_pretrained("facebook/mbart-large-50-many-to-many-mmt")
    translation_model.save_pretrained('./translation_model/')
if not os.path.exists('./tokenizer'):
    tokenizer = MBart50TokenizerFast.from_pretrained("facebook/mbart-large-50-many-to-many-mmt")
    tokenizer.save_pretrained('./tokenizer/')

translation_model = MBartForConditionalGeneration.from_pretrained("./translation_model/")
tokenizer = MBart50TokenizerFast.from_pretrained("./tokenizer/")

app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:3000",
    '*'
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

model = gpt4all.GPT4All(model_name = "gpt4all-falcon-q4_0", model_path = '.', allow_download=False)

template_chat = """This is a conversation between human and AI. 
I just want the answer from the AI not an entire conversation. 

Here are the previous conversations
{context}

Human: {input}
AI:
"""

template_title = """
"{question}"
What is the main topic of this conversation? Use the conversation details given. Don't be too creative.
Give only the topic and it should be one liner.
"""

def translate(txt, src, to):
    tokenizer.src_lang = src
    encoded_en = tokenizer(txt, return_tensors="pt")
    generated_tokens = translation_model.generate(**encoded_en, forced_bos_token_id=tokenizer.lang_code_to_id[to])
    return tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)[0]

def correct(text):
    hindi_text = translate(text, "hi_IN", "en_XX")
    if hindi_text != text:
        inputs = correction_tokenizer(text, return_tensors="pt")
        max_length = 200  # Adjust as needed
        generated = correction_model.generate(inputs["input_ids"], max_length=max_length, num_return_sequences=1)
        corrected_text = correction_tokenizer.decode(generated[0], skip_special_tokens=True)
        corrected_text_2 = translate(translate(hindi_text, "hi_IN", "en_XX"), "en_XX", "hi_IN")
        score = sentence_bleu([corrected_text_2.split()], corrected_text.split())
        if score <= 0.8:
            return corrected_text_2
        return corrected_text
    return ''

@app.post('/api/nameTitle')
async def nameTitle(request : nameTitleRequest):
    print("Renaming!!")
    question = request.question
    return model.generate(template_title.format(question = question))

@app.post('/api/inference')
async def inference(request : Request):
    print(request)
    input_req = request.input
    context = request.context
    english_input = translate(input_req, "hi_IN", "en_XX")
    res = model.generate(template_chat.format(context = context, input = english_input), max_tokens=1024)
    context += ("Human: " + english_input + '\n' + "AI: " + res + '\n')
    return {
        "result" : translate(res, "en_XX", "hi_IN"),
        "context" : context
    }

@app.post('/api/correctGrammar')
async def correct_grammar(request : correctGrammarRequest):
    text = request.text
    return correct(text)
    

if __name__ == '__main__':
    app.run()
