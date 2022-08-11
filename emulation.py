from abc import ABC, abstractmethod
from typing import NamedTuple

import os
import subprocess
import time

from mininet.topo import Topo


class LinkConfig(NamedTuple):
    start_time: int = 0
    bandwidth: int = 1000000
    loss: float = 0.0
    delay: int = 0
    latency: int = 300

    def get_log_line(self):
        return ','.join([
            str(x) for x in [
                self.start_time,
                self.bandwidth,
                self.loss,
                self.delay,
                self.latency,
            ]])


class DumbbellTopo(Topo):
    def build(self, n=2):
        left_switch = self.addSwitch('ls1')
        right_switch = self.addSwitch('rs1')
        self.addLink(left_switch, right_switch)

        for h in range(n):
            left_host = self.addHost('l{}'.format(h), cpu=.5 / n)
            self.addLink(left_host, left_switch)
            right_host = self.addHost('r{}'.format(h), cpu=.5 / n)
            self.addLink(right_host, right_switch)


class Emulation(ABC):
    @property
    def runtime(self):
        return self._runtime

    @abstractmethod
    def topology(self):
        pass

    def __init__(self, log_dir):
        self._log_dir = log_dir
        self._log_file = os.path.join(self._log_dir, 'link.log')
        self._queue = None

    @staticmethod
    @abstractmethod
    def builders(config):
        pass

    @abstractmethod
    def config_json(self):
        pass

    @abstractmethod
    def init_link_emulation(self, net):
        pass

    @abstractmethod
    def schedule_link_emulation(self, start_time):
        pass

    @abstractmethod
    def get_link_update_cmds(config: LinkConfig):
        pass

    def tcpdump(self, net, log_dir):
        pass

    def set_log_queue(self, queue):
        self._queue = queue

    def close_link_emulation(self):
        if self._last_config is not None:
            t = int(time.time() * 1000)
            with open(self._log_file, 'a') as log:
                log.write('{},{}\n'.format(
                    t, self._last_config.get_log_line()))

    def update_link(self, config: LinkConfig):
        cmds = self.get_link_update_cmds(config)
        t = int(time.time() * 1000)
        self._last_config = config
        for cmd in cmds:
            subprocess.run(cmd.split(' '))
            if self._queue is not None:
                self._queue.put(cmd)
        with open(self._log_file, 'a') as log:
            log.write('{},{}\n'.format(t, config.get_log_line()))


class EmulationBuilder():
    @abstractmethod
    def build(self, log_dir):
        pass
