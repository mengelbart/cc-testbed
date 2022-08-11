import itertools
import os
import sched
import subprocess
import time

from emulation import DumbbellTopo, Emulation, EmulationBuilder, LinkConfig


class VariableAvailableCapacityBuilder(EmulationBuilder):
    def __init__(self, loss, delay, latency):
        self._loss = loss
        self._delay = delay
        self._latency = latency

    def build(self, log_dir):
        return VariableAvailableCapacity(
                log_dir,
                self._loss,
                self._delay,
                self._latency,
            )


class VariableAvailableCapacity(Emulation):
    def __init__(self, log_dir, loss=0, delay=0, latency=300):
        Emulation.__init__(self, log_dir)
        self._tc_cmd = 'add'
        self._reference_bandwidth = 1.0
        self._runtime = 100
        self._link_configs = [
                    LinkConfig(0, 1000000, loss, delay, latency),
                    LinkConfig(40, 2500000, loss, delay, latency),
                    LinkConfig(60, 600000, loss, delay, latency),
                    LinkConfig(80, 1000000, loss, delay, latency),
                ]
        self._remaining_configs = self._link_configs

    def topology(self):
        return DumbbellTopo(n=1)

    @staticmethod
    def builders(config):
        loss_configs = config.get('loss', [0])
        delay_configs = config.get('delay', [0])
        latency_configs = config.get('latency', [0])
        configs = itertools.product(
                loss_configs, delay_configs, latency_configs)

        emulation_builders: [VariableAvailableCapacityBuilder] = []
        for i, config in enumerate(configs):
            emulation_builders.append(VariableAvailableCapacityBuilder(
                config[0], config[1], config[2],
            ))
        return emulation_builders

    def config_json(self):
        return {
                'runtime': self._runtime,
                'link_configs': [x._asdict() for x in self._link_configs],
                }

    def init_link_emulation(self, net):
        s1, s2 = net.getNodeByName('ls1', 'rs1')
        self.s1_iface = s1.intf('ls1-eth2')
        self.s2_iface = s2.intf('rs1-eth2')

        config = self._remaining_configs[0]
        self.update_link(config)
        self._remaining_configs = self._remaining_configs[1:]
        self._tc_cmd = 'change'

    def get_link_update_cmds(self, config):
        cmds = []
        for iface in [self.s1_iface, self.s2_iface]:
            qdisc_cmd = 'tc qdisc ' \
                        '{} dev {} root handle 1: ' \
                        'tbf rate {}bit burst 15000 ' \
                        'latency {}ms'.format(
                                self._tc_cmd,
                                iface,
                                config.bandwidth,
                                config.latency)

            netem_cmd = 'tc qdisc ' \
                        '{} dev {} parent 1: handle 2: ' \
                        'netem delay {} ' \
                        'loss {}'.format(
                                self._tc_cmd,
                                iface,
                                config.delay,
                                config.loss)

            cmds.append(qdisc_cmd)
            cmds.append(netem_cmd)

        return cmds

    def update_link_func(self, config):
        def f():
            self.update_link(config)
        return f

    def schedule_link_emulation(self, start_time):
        scheduler = sched.scheduler(time.time, time.sleep)
        for config in self._remaining_configs:
            scheduler.enterabs(
                    start_time + config.start_time,
                    0,
                    self.update_link_func(config),
                )
        scheduler.run()

    def tcpdump(self, net):
        s1, s2 = 'ls1-eth1', 'rs1-eth1'
        template = 'tcpdump ip -i {} -s 88 -w {}'
        FNULL = open(os.devnull, 'w')
        for s in [s1, s2]:
            cmd = template.format(
                    s,
                    os.path.join(self._log_dir, '{}.pcap'.format(s)))
            subprocess.Popen(cmd.split(' '), stderr=FNULL)
