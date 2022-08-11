from typing import NamedTuple

import itertools
import os

from flow import Flow, FlowBuilder


class RTPoverQUICSenderConfig(NamedTuple):
    cmd: str = './third_party/rtp-over-quic/rtp-over-quic'
    input: str = ''
    cpu_profile: bool = False
    goroutine_profile: bool = False
    heap_profile: bool = False
    allocs_profile: bool = False
    block_profile: bool = False
    mutex_profile: bool = False


class RTPoverQUICReceiverConfig(NamedTuple):
    cmd: str = './third_party/rtp-over-quic/rtp-over-quic'
    output: str = 'out.y4m'
    cpu_profile: bool = False
    goroutine_profile: bool = False
    heap_profile: bool = False
    allocs_profile: bool = False
    block_profile: bool = False
    mutex_profile: bool = False


class RTPCongestionControlConfig(NamedTuple):
    rtcp_feedback: str = 'rfc8888'
    local_rfc8888: bool = False
    rtp_cc: str = 'scream'


class RTPTransportConfig(NamedTuple):
    protocol: str = 'quic'
    cc: str = 'reno'


class RTPoverQUICCommonConfig(NamedTuple):
    sender_config: RTPoverQUICSenderConfig
    receiver_config: RTPoverQUICReceiverConfig
    rtp_cc: RTPCongestionControlConfig
    transport: RTPTransportConfig
    codec: str = 'h264'
    stream: bool = False


class RTPoverQUICBuilder(FlowBuilder):
    def __init__(
            self,
            server_node,
            receiver_node,
            delay,
            config):
        self._server_node = server_node
        self._receiver_node = receiver_node
        self._delay = delay
        self._config = config

    def build(self, id, log_dir):
        return RTPoverQUIC(
                id,
                self._server_node,
                self._receiver_node,
                self._delay,
                log_dir,
                self._config,
                )


class RTPoverQUIC(Flow):
    def __init__(
                self,
                id,
                server_node: str,
                receiver_node: str,
                delay: int,
                log_dir: str,
                config: RTPoverQUICCommonConfig,
            ):
        Flow.__init__(
                self, id, server_node, receiver_node, delay, log_dir)
        self._config = config

    @staticmethod
    def builders(
            server_node,
            receiver_node,
            delay,
            config,
            ) -> [FlowBuilder]:
        codecs = config['codec']
        streams = config['stream']
        transports = config['transport']
        rtp_ccs = config['rtp_cc']
        configs = itertools.product(
                codecs, streams, transports, rtp_ccs)

        return [RTPoverQUICBuilder(
            server_node,
            receiver_node,
            delay,
            RTPoverQUICCommonConfig(
                sender_config=RTPoverQUICSenderConfig(
                    **config.get('sender_config', {})),
                receiver_config=RTPoverQUICReceiverConfig(
                    **config.get('receiver_config', {})),
                rtp_cc=RTPCongestionControlConfig(**c[3]),
                transport=RTPTransportConfig(**c[2]),
                codec=c[0],
                stream=c[1],
                ),
            ) for c in configs]

    def config_json(self):
        return self._config._asdict()

    def client_cmd(self, addr, port):
        cmd = [
                self._config.sender_config.cmd,
                'send',
                '--addr', '{}:{}'.format(addr, port),
                '--source', self._config.sender_config.input,
                '--rtp-dump', '{}/sender_rtp.log'.format(
                        self._log_dir),
                '--rtcp-dump', '{}/sender_rtcp.log'.format(
                    self._log_dir),
                '--cc-dump', '{}/cc.log'.format(self._log_dir),
                '--qlog', '{}'.format(self._log_dir),
                '--transport', self._config.transport.protocol,
                '--rtp-cc', self._config.rtp_cc.rtp_cc,
            ]
        if self._config.stream:
            cmd.append('--stream')
        if self._config.rtp_cc.local_rfc8888:
            cmd.append('--local-rfc8888')
        if self._config.transport.protocol == 'quic':
            cmd.append('--quic-cc')
            cmd.append(self._config.transport.cc)
        if self._config.transport.protocol == 'tcp':
            cmd.append('--tcp-congestion')
            cmd.append(self._config.transport.cc)
        if self._config.sender_config.cpu_profile:
            cmd.append('--pprof-cpu')
            cmd.append('{}/sender_cpu.pprof'.format(
                self._log_dir))
        if self._config.sender_config.goroutine_profile:
            cmd.append('--pprof-goroutine')
            cmd.append('{}/sender_goroutine.pprof'.format(
                self._log_dir))
        if self._config.sender_config.heap_profile:
            cmd.append('--pprof-heap')
            cmd.append('{}/sender_heap.pprof'.format(
                self._log_dir))
        if self._config.sender_config.allocs_profile:
            cmd.append('--pprof-allocs')
            cmd.append('{}/sender_allocs.pprof'.format(
                self._log_dir))
        if self._config.sender_config.block_profile:
            cmd.append('--pprof-block')
            cmd.append('{}/sender_block.pprof'.format(
                self._log_dir))
        if self._config.sender_config.mutex_profile:
            cmd.append('--pprof-mutex')
            cmd.append('{}/sender_mutex.pprof'.format(
                self._log_dir))

        return cmd

    def server_cmd(self, addr, port):
        cmd = [
            self._config.receiver_config.cmd,
            'receive',
            '--addr', '{}:{}'.format(addr, port),
            '--sink', os.path.join(
                self._log_dir, self._config.receiver_config.output),
            '--rtp-dump', '{}/receiver_rtp.log'.format(
                self._log_dir),
            '--rtcp-dump', '{}/receiver_rtcp.log'.format(
                self._log_dir),
            '--qlog', '{}'.format(
                self._log_dir),
            '--transport', self._config.transport.protocol,
            '--rtcp-feedback', self._config.rtp_cc.rtcp_feedback,
            ]
        if self._config.receiver_config.cpu_profile:
            cmd.append('--pprof-cpu')
            cmd.append('{}/receiver_cpu.pprof'.format(
                self._log_dir))
        if self._config.receiver_config.goroutine_profile:
            cmd.append('--pprof-goroutine')
            cmd.append('{}/receiver_goroutine.pprof'.format(
                self._log_dir))
        if self._config.receiver_config.heap_profile:
            cmd.append('--pprof-heap')
            cmd.append('{}/receiver_heap.pprof'.format(
                self._log_dir))
        if self._config.receiver_config.allocs_profile:
            cmd.append('--pprof-allocs')
            cmd.append('{}/receiver_allocs.pprof'.format(
                self._log_dir))
        if self._config.receiver_config.block_profile:
            cmd.append('--pprof-block')
            cmd.append('{}/receiver_block.pprof'.format(
                self._log_dir))
        if self._config.receiver_config.mutex_profile:
            cmd.append('--pprof-mutex')
            cmd.append('{}/receiver_mutex.pprof'.format(
                self._log_dir))
        return cmd
