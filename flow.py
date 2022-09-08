from abc import ABC, abstractmethod
from pathlib import Path
from subprocess import PIPE
from threading import Thread

import os


class Flow(ABC):
    @property
    def delay(self):
        return self._delay

    @property
    def server_node(self):
        return self._server_node

    @property
    def receiver_node(self):
        return self._receiver_node

    @abstractmethod
    def __init__(self, id, server_node, receiver_node, delay, log_dir):
        self._id = id
        self._server_node = server_node
        self._receiver_node = receiver_node
        self._delay = delay
        self._log_dir = log_dir

    @staticmethod
    @abstractmethod
    def builders(
            delay,
            config,
            ):
        pass

    @abstractmethod
    def server_cmd(self, addr, port):
        pass

    @abstractmethod
    def client_cmd(self, addr, port):
        pass

    @abstractmethod
    def config_json(self):
        pass

    def cleanup(self):
        pass

    def start_server(self, q, end_event, host, addr, port):
        Path(self._log_dir).mkdir(parents=True, exist_ok=True)
        cmd = self.server_cmd(addr, port)
        q.put('server_{}_cmd: {}'.format(self._id, cmd))
        proc = host.popen(cmd, stderr=PIPE, stdout=PIPE)
        threads = []
        streams = {'stdout': proc.stdout, 'stderr': proc.stderr}
        for name, stream in streams.items():
            comm = Thread(
                    target=communicate,
                    args=(
                        q,
                        self._id,
                        'server',
                        name,
                        self._log_dir,
                        stream))
            threads.append(comm)
            comm.start()

        end_event.wait()
        proc.kill()

        for t in threads:
            t.join()

    def start_client(self, q, end_event, host, addr, port):
        Path(self._log_dir).mkdir(parents=True, exist_ok=True)
        cmd = self.client_cmd(addr, port)
        q.put('client_{}_cmd: {}'.format(self._id, cmd))
        proc = host.popen(cmd, stderr=PIPE, stdout=PIPE)
        threads = []
        streams = {'stdout': proc.stdout, 'stderr': proc.stderr}
        for name, stream in streams.items():
            comm = Thread(
                    target=communicate,
                    args=(
                        q,
                        self._id,
                        'client',
                        name,
                        self._log_dir,
                        stream))
            threads.append(comm)
            comm.start()

        end_event.wait()
        proc.kill()

        for t in threads:
            t.join()


def communicate(q, id, endpoint, stream, log_dir, out):
    log_file_name = os.path.join(
            log_dir,
            '{}_out.log'.format(endpoint))
    with open(log_file_name, 'w') as log_file:
        for line in iter(out.readline, b''):
            q.put('{}_{}_out: {}'.format(
                endpoint,
                id,
                line.decode('utf-8').strip()))
            log_file.write('{}'.format(line))


class FlowBuilder():
    @abstractmethod
    def build(id, server_node, receiver_node, log_dir) -> Flow:
        pass
