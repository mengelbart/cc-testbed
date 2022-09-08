import os

from flow import Flow, FlowBuilder


class Iperf3Builder(FlowBuilder):
    def __init__(
            self,
            delay,
            congestion_control_algorithm,
            duration,
            ):
        self._delay = delay
        self._congestion_control_algorithm = congestion_control_algorithm
        self._duration = duration

    def build(
            self,
            id,
            server_node,
            receiver_node,
            log_dir,
            ) -> Flow:
        return Iperf3(
                id,
                server_node,
                receiver_node,
                self._delay,
                log_dir,
                self._congestion_control_algorithm,
                self._duration,
        )


class Iperf3(Flow):
    def __init__(
            self,
            id,
            server_node,
            receiver_node,
            delay,
            log_dir,
            congestion_control_algorithm,
            duration,
            ):
        Flow.__init__(
                self, id, server_node, receiver_node, delay, log_dir)
        self._congestion_control_algorithm = congestion_control_algorithm
        self._duration = duration

    @staticmethod
    def builders(
            delay,
            config,
            ) -> [FlowBuilder]:
        return [
            Iperf3Builder(
                delay,
                cc, config['duration'],
                ) for
            cc in config['congestion_control_algorithm']
        ]

    def server_cmd(self, addr, port):
        cmd = [
                'iperf3',
                '--server',
                '--bind', addr,
                '--port', str(port),
                '--json',
                '--logfile', os.path.join(self._log_dir, 'server.iperf3'),
                ]
        return cmd

    def client_cmd(self, addr, port):
        cmd = [
                'iperf3',
                '--client', addr,
                '--port', str(port),
                '--time', str(self._duration),
                '--version4',
                '--linux-congestion', self._congestion_control_algorithm,
                '--json',
                '--logfile', os.path.join(self._log_dir, 'client.iperf3'),
                ]
        return cmd

    def config_json(self):
        return {
            'congestion_control_algorithm': self._congestion_control_algorithm,
            'duration': self._duration,
        }
