from groq import Groq
import copy

class GrokClient():

    def __init__(self,dummy=None,api_key=""):
        print("grokclient init")
        self.api_key=api_key
        self.client = None
        self.prompt_metadata={}
        self.model_name="llama3-70b-8192"
        self.default_params={ "temperature":0.1, "max_tokens":1024//2, "stream":True, "stop":None}

    def send_prompt(self,p,params=None, callback=None):
        if isinstance(p,list):
            messages = p
        else:
            messages = p.messages
        #print(messages)
        user_params = params
        params = copy.deepcopy(self.default_params)
        if params:
            params["stop"] = user_params.get("stop",None)
        model_name = self.model_name
        completion = self.client.chat.completions.create( model=self.model_name, messages=messages,**params)
        return self.ricevi(completion,callback)

    def ricevi(self,completion,callback=None):
        res = ""
        for chunk in completion:
             
             val = chunk.choices[0].delta.content or ""
             res += val
             if callback:
                callback(val)
        return res

    def connect(self):
        if not self.client:
            self.client = Groq(api_key=self.api_key)

    def get_model_name(self):
        return "grok"



if __name__ == "__main__":
     client = GrokClient()
     client.connect()
     messages=[ { "role": "user", "content": "Hello, tell me your name" }]
     params={ "temperature":1, "max_tokens":1024, "top_p":1, "stream":True, "stop":None}
     result = client.send_prompt(messages,params)
     for el in result:
         print(el,end="")
     print("")

