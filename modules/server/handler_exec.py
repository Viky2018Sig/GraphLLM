import json
import queue
import select
import socket
import tempfile
import traceback

import yaml
from modules.clients import get_client_config, Client
from modules.graph import GraphExecutor, GraphException
from modules.graph.json_parser import JsonParser
from modules.logging.logger import Logger
from websockets.frames import Opcode
from websockets.server import ServerProtocol


class WebExec():
    def __init__(self,send):
        self.t = None
        self.send_chunk = send
        logger = Logger(verbose=True, web_logger=False)


        parameters = {}
        parameters["repeat_penalty"] = 1.0
        parameters["penalize_nl"] = False
        parameters["seed"] = -1


        self.executor_config = {"client":None, "client_parameters":parameters,"logger":logger}


        self.logger = logger
        self.keep_running = False

    def event(self,t,a,v):
        #print(t,a,v)

        res = {"type": t, "data":a}
        resp = json.dumps(res) + "\n"
        encoded = resp
        self.send_chunk(encoded)

    def _run(self,args):
        self.logger.addListener(self)
        self.logger.log("start")
        last_error = None
        try:
            client_config = get_client_config()
            client = Client.make_client(client_config)
            client.connect()
            self.executor_config["client"] = client
            self.executor = GraphExecutor(self.executor_config)
            self.executor.load_config(args)
            self.executor([])
        except GraphException as e:
            if isinstance(e.saved_i,BrokenPipeError):
                print("client disconnected")
            else:
                last_error = e.saved_i
        except BrokenPipeError:
            print("client disconnected")
        except Exception as e:
            last_error = e

        try:
            if last_error:
                traceback.print_exception(last_error)
                self.logger.log("error",str(last_error))

            self.logger.log("stop")

        except Exception as e:
            print("stop exception:",e)
            pass
        finally:
            self.logger.poison()
            self.logger.deleteListeners()

    def run(self,filename):
        self._run([filename])


class ExecHandler():
    def __init__(self,server):
        self.server = server
        self.protocol = ServerProtocol()
        self.socket = server.request
        self.alive = False
        self.received_events = queue.Queue()


    def _receive(self, blocking = False):
        if not self.alive:
            return
        if not blocking:
            socket_list = [self.socket]
            read_sockets, write_sockets, error_sockets = select.select(socket_list, [], [],0)
            if len(read_sockets) == 0:
                return

        try:
            data = self.server.request.recv(65536)
        except OSError:  # socket closed
            data = b""
        if data:
            self.protocol.receive_data(data)
        else:
            self.protocol.receive_eof()
        events = self.protocol.events_received()

        for el in events:
            self.received_events.put(el)
            if el.opcode == Opcode.CLOSE:
                self.socket.shutdown(socket.SHUT_WR)
                self.alive= False
        return events

    def _send_queued_data(self):
        if not self.alive:
            return
        try:
            for el in self.protocol.data_to_send():
                self.server.wfile.write(el)
        except:
            self.alive = False
            raise

    def _send_close(self):
        self._receive()
        if self.alive:
            self.protocol.send_close()
            self._send_queued_data()
            self.alive = False

    def _send_text(self,text):
        self._receive()
        if self.alive:
            self.protocol.send_text(text.encode())
            self._send_queued_data()
        if not self.alive:
            raise BrokenPipeError("connection closed")

    def _handshake(self):
        headers = self.server.headers.items()
        headers = [i + ": " + v for i, v in headers]
        headers = "\r\n".join(headers) + "\r\n\r\n"
        request = self.server.requestline + "\r\n" + str(headers)

        self.protocol.receive_data(request.encode())
        request = self.protocol.events_received()[0]
        response = self.protocol.accept(request)
        self.protocol.send_response(response)
        self.alive = True
        self._send_queued_data()

    def exec(self):
        self.state = 1
        self._handshake()
        self._receive(blocking = True)
        event = self.received_events.get()
        json_graph = event.data.decode()

        with open(tempfile.gettempdir() + "/graph.json", "w") as f:
            a = json.loads(json_graph)
            f.write(json.dumps(a, indent=4))
        parser = JsonParser()
        parsed = parser.load(tempfile.gettempdir() + "/graph.json")
        with open(tempfile.gettempdir() + "/graph.yaml", "w") as f:
            f.write(yaml.dump(parsed, sort_keys=False))
        e = WebExec(self._send_text)
        e.run(tempfile.gettempdir() + "/graph.yaml")

        self._send_close()
        self.server.close_connection = True
        pass