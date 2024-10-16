from ..formatter import PromptBuilder
from ..parser import solve_templates
from .common import send_chat,solve_placeholders
from ..common import readfile, merge_params
from functools import partial
from .common import GenericExecutor
from ..grammar import load_grammar

class LlmExecutor(GenericExecutor):
    def __init__(self,node_graph_parameters):
        super().__init__(node_graph_parameters)
        self.print_prompt=True
        self.print_response=True
        self.current_prompt="{}"
        self.client_parameters = None
        if "client" in node_graph_parameters:
           self.set_dependencies({"client":node_graph_parameters["client"]})
        self.logger = node_graph_parameters["logger"]
        self.path = node_graph_parameters.get("path","/")

    def set_parameters(self,args):
            executor_parameters = self.graph.client_parameters
            self._set_client_parameters(executor_parameters)
            new_obj = {}
            for key in ["stop", "n_predict","temperature","top_k"]:
                if key in args:
                    new_obj[key] = args[key]

            if "grammar" in args:
                grammarfile = args["grammar"]
                grammar = load_grammar(grammarfile)
                new_obj[grammar["format"]] = grammar["schema"]

            executor_parameters = merge_params(executor_parameters, new_obj)
            self._set_client_parameters(executor_parameters)

            for key in ["force_system","print_prompt","sysprompt","print_response"]:
                if key in args:
                    self._set_param(key,args[key])


    def set_dependencies(self,d):
        if "client" in d:
           client = d["client"]
           builder = PromptBuilder()
           builder.load_model(client.get_model_name())
           self.client = client
           self.builder=builder

    def _set_client_parameters(self,p):
        self.client_parameters = p

    def _set_param(self,key,value):
        if key in ["sysprompt"]:
            self.builder.set_param(key, value)
        elif key in ["force_system","sysprompt"]:
            self.builder.set_param(key, value)
        elif key == "print_prompt":
            self.print_prompt = value
        elif key == "print_response":
            self.print_response = value

    def set_template(self,cl_args=None):
        for i,el in enumerate(cl_args):
            try:
                cl_args[i] = readfile(el)
            except:
                pass
        new_prompt, _ = solve_templates(self.current_prompt,cl_args)
        self.current_prompt = new_prompt

    def get_prompt_len(self):
        return self.current_prompt.count("{}")

    def basic_exec(self,text_prompt):
        if text_prompt == "{p:eos}":
            self.builder.reset()
            return ["{p:eos}"]
        m = text_prompt
        client = self.client
        builder = self.builder
        if isinstance(m,tuple):
            messages = builder.add_request(m[1],m[0])
        else:
            messages = builder.add_request(m)

        if bool(self.print_prompt):
            x = self.print_prompt
            if isinstance(x, (int, float, complex)) and not isinstance(x, bool):
                self.print_prompt -= 1
            prompt = builder._build()
            print(prompt,end="")
        res = send_chat(builder,client,self.client_parameters,self.print_response,logger_print=partial(self.logger.log,"print",self.path))
        resp = [res,{"role":"assistant"}]

        if hasattr(client,"prompt_metadata") and "stopped_word" in client.prompt_metadata and client.prompt_metadata["stopped_word"] and client.prompt_metadata["stopping_word"] == "<|eom_id|>":
            messages = builder.add_response(str(res),"call")
            resp = [res, {"role":"call"}]
        else:
            messages = builder.add_response(str(res))
        return resp



class StatelessExecutor(LlmExecutor):
    def __init__(self,client):
        super().__init__(client)

    def __call__(self,prompt_args):
        m ,_ = solve_templates(self.current_prompt,prompt_args)
        m = solve_placeholders(m,prompt_args)
        self.builder.reset()

        res = self.basic_exec(m)
        return res

class StatefulExecutor(LlmExecutor):
    def __init__(self,client):
        super().__init__(client)

    def __call__(self,prompt_args):
        if len(prompt_args) > 0 and isinstance(prompt_args[0],tuple):
            m = prompt_args[0]
        else:
            m ,_ = solve_templates(self.current_prompt,prompt_args)
            m = solve_placeholders(m, prompt_args)
        self.current_prompt="{}"

        res = self.basic_exec(m)
        return res
