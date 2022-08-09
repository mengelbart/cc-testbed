from typing import NamedTuple

import os

from flow import Flow


class RTPoverQUICSenderConfig(NamedTuple):
    cmd: str = './third_party/rtp-over-quic/rtp-over-quic'
    transport: str = 'quic'
    rtp_cc: str = 'scream'
    quic_cc: str = 'newreno'
    stream: bool = False
    local_rfc8888: bool = False
    input: str = ''
    cpu_profile: bool = False
    goroutine_profile: bool = False
    heap_profile: bool = False
    allocs_profile: bool = False
    block_profile: bool = False
    mutex_profile: bool = False


class RTPoverQUICReceiverConfig(NamedTuple):
    cmd: str = './third_party/rtp-over-quic/rtp-over-quic'
    transport: str = 'quic'
    rtcp_feedback: str = 'rfc8888'
    output: str = 'out.y4m'
    cpu_profile: bool = False
    goroutine_profile: bool = False
    heap_profile: bool = False
    allocs_profile: bool = False
    block_profile: bool = False
    mutex_profile: bool = False


class RTPoverQUIC(Flow):
    def __init__(
                self,
                id,
                server_node: str,
                receiver_node: str,
                delay: int,
                log_dir: str,
                extra: dict,
            ):
        Flow.__init__(
                self, id, server_node, receiver_node, delay, log_dir, extra)
        self.sender_config = RTPoverQUICSenderConfig(**extra['sender_config'])
        self.receive_config = RTPoverQUICReceiverConfig(
                **extra['receiver_config'])

    def config(self):
        return {
                'sender': self.sender_config._asdict(),
                'receiver': self.receive_config._asdict(),
                }

    def client_cmd(self, addr):
        cmd = [
                self.sender_config.cmd,
                'send',
                '--addr', '{}'.format(addr),
                '--source', self.sender_config.input,
                '--rtp-dump', '{}/sender_rtp.log'.format(
                        self._log_dir),
                '--rtcp-dump', '{}/sender_rtcp.log'.format(
                    self._log_dir),
                '--cc-dump', '{}/cc.log'.format(self._log_dir),
                '--qlog', '{}'.format(self._log_dir),
                '--transport', self.sender_config.transport,
                '--rtp-cc', self.sender_config.rtp_cc,
                '--quic-cc', self.sender_config.quic_cc,
            ]
        if self.sender_config.stream:
            cmd.append('--stream')
        if self.sender_config.local_rfc8888:
            cmd.append('--local-rfc8888')
        if self.sender_config.cpu_profile:
            cmd.append('--pprof-cpu')
            cmd.append('{}/sender_cpu.pprof'.format(
                self._log_dir))
        if self.sender_config.goroutine_profile:
            cmd.append('--pprof-goroutine')
            cmd.append('{}/sender_goroutine.pprof'.format(
                self._log_dir))
        if self.sender_config.heap_profile:
            cmd.append('--pprof-heap')
            cmd.append('{}/sender_heap.pprof'.format(
                self._log_dir))
        if self.sender_config.allocs_profile:
            cmd.append('--pprof-allocs')
            cmd.append('{}/sender_allocs.pprof'.format(
                self._log_dir))
        if self.sender_config.block_profile:
            cmd.append('--pprof-block')
            cmd.append('{}/sender_block.pprof'.format(
                self._log_dir))
        if self.sender_config.mutex_profile:
            cmd.append('--pprof-mutex')
            cmd.append('{}/sender_mutex.pprof'.format(
                self._log_dir))

        return cmd

    def server_cmd(self, addr):
        cmd = [
            self.receive_config.cmd,
            'receive',
            '--addr', '{}'.format(addr),
            '--sink', os.path.join(self._log_dir, self.receive_config.output),
            '--rtp-dump', '{}/receiver_rtp.log'.format(
                self._log_dir),
            '--rtcp-dump', '{}/receiver_rtcp.log'.format(
                self._log_dir),
            '--qlog', '{}'.format(
                self._log_dir),
            '--transport', self.receive_config.transport,
            '--rtcp-feedback', self.receive_config.rtcp_feedback,
            ]
        if self.receive_config.cpu_profile:
            cmd.append('--pprof-cpu')
            cmd.append('{}/receiver_cpu.pprof'.format(
                self._log_dir))
        if self.receive_config.goroutine_profile:
            cmd.append('--pprof-goroutine')
            cmd.append('{}/receiver_goroutine.pprof'.format(
                self._log_dir))
        if self.receive_config.heap_profile:
            cmd.append('--pprof-heap')
            cmd.append('{}/receiver_heap.pprof'.format(
                self._log_dir))
        if self.receive_config.allocs_profile:
            cmd.append('--pprof-allocs')
            cmd.append('{}/receiver_allocs.pprof'.format(
                self._log_dir))
        if self.receive_config.block_profile:
            cmd.append('--pprof-block')
            cmd.append('{}/receiver_block.pprof'.format(
                self._log_dir))
        if self.receive_config.mutex_profile:
            cmd.append('--pprof-mutex')
            cmd.append('{}/receiver_mutex.pprof'.format(
                self._log_dir))
        return cmd
