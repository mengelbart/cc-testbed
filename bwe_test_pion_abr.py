from typing import NamedTuple

from flow import Flow, FlowBuilder


class PionABRConfig(NamedTuple):
    cmd: str = './third_party/bwe-test-pion/bwe-test-pion'


class PionABRBuilder(FlowBuilder):
    def __init__(
            self,
            delay,
            config):
        self._delay = delay
        self._config = config

    def build(self, id, server_node, receiver_node, log_dir):
        return PionABR(
            id,
            server_node,
            receiver_node,
            self._delay,
            log_dir,
            self._config,
        )


class PionABR(Flow):
    def __init__(self, id, server_node, receiver_node, delay, log_dir, config):
        Flow.__init__(self, id, server_node, receiver_node, delay, log_dir)
        self._config = config

    @staticmethod
    def builders(
            delay,
            config,
            ):
        return [PionABRBuilder(
            delay,
            PionABRConfig(**config),
        )]

    def config_json(self):
        return {
            'name': 'bwe-test-pion-abr',
            'config': self._config._asdict(),
            'log_dir': self._log_dir,
            'id': self._id,
            'parameters': {
                'id': self._id,
            },
        }

    def server_cmd(self, addr, port):
        cmd = [
            self._config.cmd,
            '-mode', 'receiver',
            '-addr', f'{addr}:{port}',
            '-rtcp-inbound-log',
            f'{self._log_dir}/receiver_inbound.rtcp',
            '-rtcp-outbound-log',
            f'{self._log_dir}/receiver_outbound.rtcp',
            '-rtp-log', f'{self._log_dir}/receiver.rtp',
        ]
        return cmd

    def client_cmd(self, addr, port):
        cmd = [
            self._config.cmd,
            '-mode', 'sender',
            '-addr', f'{addr}:{port}',
            '-rtcp-inbound-log',
            f'{self._log_dir}/sender_inbound.rtcp',
            '-rtcp-outbound-log',
            f'{self._log_dir}/sender_outbound.rtcp',
            '-rtp-log', f'{self._log_dir}/sender.rtp',
            '-cc-log', f'{self._log_dir}/cc.gcc',
        ]
        return cmd
