#!/usr/bin/python3
import sys
from utils.common import get_input,get_formatter,readfile,build_prompt
from utils.client import Client,DummyClient,GLMClient,ONNXClient
from utils.formatter import Formatter,PromptBuilder

from utils.graph_executor import GraphExecutor
import json

client = Client()
client.connect()

parameters = {}
parameters["repeat_penalty"] = 1.0
parameters["penalize_nl"] = False
parameters["seed"] = -1

#test
#parameters["seed"] = 0

executor_config = {"client":client, "client_parameters":parameters}

seqExec = GraphExecutor(executor_config)

cl_args = seqExec.load_config(sys.argv[1:])
res = seqExec(cl_args[1:])
print("Result:")
for el in res:
    print(json.dumps(el, indent=4))



