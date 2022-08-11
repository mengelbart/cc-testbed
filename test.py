#!/usr/bin/env python

import argparse
import itertools
import json
import os
import time
import yaml

from pathlib import Path
from typing import NamedTuple
from threading import Event, Thread
from queue import Queue

from mininet.clean import cleanup
from mininet.log import setLogLevel
from mininet.net import Mininet

import flow
import emulation

PORT = 4242


class TestConfig(NamedTuple):
    log_dir: str
    flows: flow.Flow
    emulation: emulation.Emulation


def timestamp(t):
    return time.strftime('%X', time.localtime(t))


def run_at(at, func):
    t = time.time()
    delay = at - t
    if delay < 0:
        return func()
    time.sleep(delay)
    return func()


class Test:
    def __init__(self, config):
        self.flows: flow.Flow = config.flows
        self.emulation: emulation.Emulation = config.emulation
        self._log_dir = config.log_dir

    def setup_network(self):
        topo = self.emulation.topology()
        self.net = Mininet(topo=topo, autoStaticArp=True)
        self.net.start()

    def start_flows(self, q, e):
        self.server_threads = []
        self.client_threads = []
        for f in self.flows:
            host = self.net.getNodeByName(f.server_node)
            t = Thread(
                    target=f.start_server,
                    args=(q, e, host, host.IP(), PORT),
                )
            t.start()
            self.server_threads.append(t)

        self.emulation.set_log_queue(q)
        self.emulation.tcpdump(self.net)
        self.emulation.init_link_emulation(self.net)
        self.start_time = time.time()

        emulation_thread = Thread(
                target=self.emulation.schedule_link_emulation,
                args=(self.start_time, ))
        emulation_thread.daemon = True
        emulation_thread.start()
        print('{} servers started'.format(timestamp(self.start_time)))

        # TODO: Sort flows by delay?
        for f in self.flows:
            host = self.net.getNodeByName(f.receiver_node)
            server = self.net.getNodeByName(f.server_node)
            at = self.start_time + f.delay
            print('{} schedule flow at: {}'.format(
                timestamp(time.time()), timestamp(at)))
            t = Thread(
                    target=run_at,
                    args=(
                        at,
                        lambda: f.start_client(q, e, host, server.IP(), PORT)))
            t.start()
            self.client_threads.append(t)

    def log_output_from_queue(self, q):
        while True:
            item = q.get()
            if item is None:
                break
            print('{}: {}'.format(timestamp(time.time()), item))

    def write_meta_info(self):
        flows = []
        for f in self.flows:
            flows.append(f.config_json())

        config = {
                'start_time': self._start_time,
                'end_time': self._end_time,
                'emulation': self.emulation.config_json(),
                'flows': flows,
            }
        Path(self._log_dir).mkdir(parents=True, exist_ok=True)
        with open(os.path.join(self._log_dir, 'config.json'), 'w') as file:
            json.dump(config, file)

    def teardown_network(self):
        self.net.stop()
        cleanup()

    def run(self):
        io_queue = Queue()
        end_event = Event()
        iot = Thread(target=self.log_output_from_queue, args=(io_queue, ))
        iot.start()
        try:
            self.setup_network()
            self.start_flows(io_queue, end_event)

            end_time = self.start_time + self.emulation.runtime
            print('{} run until {}'.format(
                timestamp(time.time()), timestamp(end_time)))
            elapsed_time = time.time() - self.start_time
            if elapsed_time > self.emulation.runtime:
                print('error: scheduling delay larger than total runtime')

            sleep_time = self.emulation.runtime - elapsed_time
            print('{} sleep {}'.format(timestamp(time.time()), sleep_time))
            time.sleep(sleep_time)
            print('{} sleep done'.format(timestamp(time.time())))
            self.end_time = time.time()
            self.write_meta_info()
        except Exception as e:
            print(e)
        finally:
            end_event.set()
            print('cleaining up')
            for thread in self.server_threads:
                thread.join()
                print('joined server')
            for thread in self.client_threads:
                thread.join()
                print('joined client')
            io_queue.put(None)
            iot.join()
            print('joined iot')
            self.teardown_network()


def parse_flow_builders(flows):
    flow_sets: [[flow.FlowBuilder]] = [[]] * len(flows)
    for i, f in enumerate(flows):
        mod = __import__(f['module'])
        flow_class = getattr(mod, f['name'])
        flow_builders = flow_class.builders(
                f['server_node'],
                f['receiver_node'],
                f['delay'],
                f['config'],
            )
        flow_sets[i] = flow_builders

    product = itertools.product(*flow_sets)
    return list(product)


def parse_emulation_builders(emulation):
    mod = __import__(emulation['module'])
    emulation_class = getattr(mod, emulation['name'])
    return emulation_class.builders(emulation['config'])


def parse_test_config(file_name, data_dir):
    file = Path(file_name)
    if file.is_file():
        with open(file) as f:
            configs = yaml.safe_load(f)

    tests = []
    for config_id, config in enumerate(configs):
        config_dir = os.path.join(data_dir, str(config_id))
        emu_builders = parse_emulation_builders(config['emulation'])
        flow_builders = parse_flow_builders(config['flows'])
        emu_x_flows = itertools.product(emu_builders, flow_builders)

        for id, x in enumerate(emu_x_flows):
            emu_name = 'e-{}'.format(id)
            emu_dir = os.path.join(config_dir, emu_name)
            emulation = x[0].build(emu_dir)
            flows = [f.build(
                i,
                os.path.join(emu_dir, str(i)),
                ) for i, f in enumerate(x[1])]

            tc = TestConfig(data_dir, flows, emulation)
            tests.append(tc)
    return tests


def parse_test_args():
    parser = argparse.ArgumentParser(
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('--log-level', default='output',
                        choices=[
                            'debug',
                            'info',
                            'output',
                            'warning',
                            'warn',
                            'error',
                            'critical',
                        ],
                        help='log level for mininet')
    parser.add_argument('--data-dir', default='data/',
                        help='output directory for logfiles')
    parser.add_argument('-c', '--config-file', default='./config.yaml',
                        help='config file')
    args = parser.parse_args()
    return args


def main():
    args = parse_test_args()
    setLogLevel(args.log_level)
    test_configs = parse_test_config(args.config_file, args.data_dir)
    print('running {} test configs'.format(len(test_configs)))
    for i, test_config in enumerate(test_configs):
        print('running test config {}/{}'.format(i+1, len(test_configs)))
        Test(test_config).run()
        print()


if __name__ == "__main__":
    main()
