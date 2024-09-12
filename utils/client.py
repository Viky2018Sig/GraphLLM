
import json
import requests
from . import common
from .common import get_formatter,build_prompt,merge_params
from .formatter import Formatter
import time
import copy

DEFAULT_HOST="matteopc"

class ONNXClient(object):
    def __new__(cls, *args,**kwargs):
        print("loading subonnx")
        try:
           retval = object.__new__(ONNXClientInner,*args,**kwargs)
        except:
           from .client_onnx import ONNXClient as ONNXClientInner
           retval = object.__new__(ONNXClientInner,*args,**kwargs)
        retval.__init__(*args,**kwargs)
        return retval

class GLMClient(object):
    def __new__(cls, *args,**kwargs):
        print("loading subglm")
        try:
           retval = object.__new__(GLMClientInner,*args,**kwargs)
        except:
           from .client_glm import GLMClient as GLMClientInner
           retval = object.__new__(GLMClientInner,*args,**kwargs)
        retval.__init__(*args,**kwargs)
        return retval

class GrokClient(object):
    def __new__(cls, *args,**kwargs):
        print("loading subgrokclient")
        try:
           retval = object.__new__(GrokClientInner,*args,**kwargs)
        except:
           from .grokclient import GrokClient as GrokClientInner
           retval = object.__new__(GrokClientInner,*args,**kwargs)
        retval.__init__(*args,**kwargs)
        return retval

class DummyClient:

    def send_prompt(self,p,params=None):
        print(p.messages)
        return ["{ \"answer\": \"dummy response\"}"]

    def connect(self):
        pass

    def get_model_name(self):
        return ""

class Client:
    def __init__(self,host=DEFAULT_HOST):
        self.host = host
        self.port = 8080
        self.client_parameters = {}
        a = {}
        a["n_predict"] = 128 * 8
        a["stop"] = ["<|eom_id|>","<|eot_id|>","<|end|>", "<|im_end|>", "</s>","<end_of_turn>"]
        #        a["temperature"] = 0.0
        a["seed"] = -1
        a["cache_prompt"] = True
        a["stream"] = True
        # a["n_probs"] = 10
        # a["n_keep"] = -1
        # a["top_k"] = 5
        self.prompt_metadata= {}
        self.default_params = a


    def connect(self):
        props = self.get_server_props()
        model_path = props["default_generation_settings"]["model"]
        model_name = model_path.split("/")[-1]
        self.model_name = model_name
        self.formatter = Formatter()
        self.formatter.load_model(model_name)
        #get_formatter(props)

    def set_parameters(self,parameters):
        client_config_names=["host","port"]
        if "port" in parameters:
            self.port = parameters["port"]
        if "host" in parameters:
            self.host = parameters["host"]
            self.connect()
        else:
            self.parameters = parameters

    def get_model_name(self):
        return self.model_name

    def get_server_props(self):
        url = "http://" + self.host + ":" + str(self.port) + "/props"

        retries = 10
        while retries > 0:
            r = requests.get(url)
            resp = json.loads(r.content)
            retries -= 1
            if "error" in resp:
                print("server busy")
                time.sleep(2)
            else:
                break
        max_context = resp["default_generation_settings"]["n_ctx"]
        self.context_size = max_context
        return resp

    def ricevi(self,r1, pass_raw=False):
        a = 1
        for line in r1.iter_lines():
            # filter out keep-alive new lines
            a = a + 1
            if line:
                decoded_line = line.decode('utf-8')
                json_decoded = json.loads(decoded_line[6:])
                if ("stop" not in json_decoded) or json_decoded["stop"]:
                    self.prompt_metadata = json_decoded

                if "truncated" in json_decoded and (json_decoded["truncated"] or False):
                    del json_decoded["prompt"]
                    print(json.dumps(json_decoded,indent=4))
                    
                    raise Exception("truncated")
                if "content" not in json_decoded:
                    print(json_decoded)
                
                
                if pass_raw and len(json_decoded["content"]) > 0:
                    tmp_res = json_decoded['completion_probabilities']
                    #print(tmp_res)
                    if len(tmp_res) == 0:
                        continue
                    tmp_res = tmp_res[0]["probs"]
                    tmp_res = [ (el["tok_str"],el["prob"]) for el in tmp_res ]
                    tmp_res = str(tmp_res) + "\n"
                    #
                else:
                    tmp_res =json_decoded["content"]
                yield tmp_res

    def tokenize(self,p):
        url = "http://" + self.host + ":" + str(self.port) + "/tokenize"
        a={}
        a["content"] = p
        a["add_special"] = False
        js = json.dumps(a)
        headers = {"Content-Type": "application/json"}
        r = requests.post(url,data=js,headers=headers)
        r1 = r.text
        r2 = r1
        r3 = json.loads(r2)
        r4 = r3["tokens"]
        #print("tokens: ", len(r4))
        return r4
    
    def detokenize(self,p):
        url = "http://" + self.host + ":" + str(self.port) + "/detokenize"
        a={}
        a["tokens"] = p
        js = json.dumps(a)
        headers = {"Content-Type": "application/json"}
        r = requests.post(url,data=js,headers=headers)
        r1 = r.text
        r2 = r1
        r3 = json.loads(r2)
        #print(r3)
        return r3
    
    def _send_prompt_text(self, p, params):
        tokens = self.tokenize(p)
        #detokenized = self.detokenize(tokens)

        a = merge_params(self.default_params,params)
        a["prompt"] = tokens

        if len(tokens) +a["n_predict"] >= self.context_size:
            raise Exception("context size exceeded: " + str(len(tokens)) + " + " + str(a["n_predict"]))

        #a = {"messages":p}
        js = json.dumps(a)
        #print(a,"\n-\n" + p + "-")
        url = "http://" + self.host + ":" + str(self.port) +"/completion"
        headers = {"Content-Type": "application/json"}

        data = js
        r = requests.post(url,data=data,headers=headers,stream=True)
        pass_raw = "n_probs" in a
        g = self.ricevi(r,pass_raw)
        return g

    def _send_prompt_builder(self,p,params):
        prompt = p._build()
        return self._send_prompt_text(prompt,params)

    def apply_format_templates(self,prompt):
        return self.formatter.apply_format_templates(prompt)

    def send_prompt(self,p,params=None):
        if params is None:
            params = self.client_parameters
        if isinstance(p,str):
            return self._send_prompt_text(p,params)
        else:
            return self._send_prompt_builder(p,params)
