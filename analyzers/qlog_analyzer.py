import json

import pandas as pd

from matplotlib.dates import DateFormatter
from matplotlib.ticker import EngFormatter


class QLOGAnalyzer():
    def __init__(self):
        self.inflight = []
        self.congestion = []
        self.dgram_tx = []
        self.stream_tx = []
        self.sums_tx = []
        self.dgram_rx = []
        self.stream_rx = []
        self.sums_rx = []
        self.rtt = []
        self.packet_loss = []

    def add_bytes_inflight(self, event):
        if (
                'name' in event and
                event['name'] == 'recovery:metrics_updated' and
                'data' in event and
                'bytes_in_flight' in event['data']
                ):

            self.inflight.append({
                'time': event['time'],
                'bytes_in_flight': event['data']['bytes_in_flight'],
            })

    def add_cwnd(self, event):
        if (
                'name' in event and
                event['name'] == 'recovery:metrics_updated' and
                'data' in event and
                'congestion_window' in event['data']
                ):

            self.congestion.append({
                'time': event['time'],
                'cwnd': event['data']['congestion_window'],
            })

    def add_rtt(self, event):
        if (
                'name' in event and
                event['name'] == 'recovery:metrics_updated'
                ):

            append = False
            sample = {'time': event['time']}
            if 'data' in event and 'smoothed_rtt' in event['data']:
                sample['smoothed_rtt'] = event['data']['smoothed_rtt']
                append = True
            if 'data' in event and 'min_rtt' in event['data']:
                sample['min_rtt'] = event['data']['min_rtt']
                append = True
            if 'data' in event and 'latest_rtt' in event['data']:
                sample['latest_rtt'] = event['data']['latest_rtt']
                append = True
            if append:
                self.rtt.append(sample)

    def add_tx_rates(self, event):
        if (
                'name' in event and
                event['name'] == 'transport:packet_sent' and
                'data' in event and
                'frames' in event['data']
                ):
            datagrams = [frame for frame in event['data']['frames'] if
                         frame['frame_type'] == 'datagram']
            stream_frames = [frame for frame in event['data']['frames']
                             if frame['frame_type'] == 'stream']

            if len(datagrams) > 0:
                s = sum([datagram['length'] for datagram in datagrams])
                self.dgram_tx.append({
                    'time': event['time'],
                    'bytes': s,
                })
                self.sums_tx.append({
                    'time': event['time'],
                    'bytes': s,
                })

            if len(stream_frames) > 0:
                s = sum([stream['length'] for stream in stream_frames])
                self.stream_tx.append({
                    'time': event['time'],
                    'bytes': s,
                })
                self.sums_tx.append({
                    'time': event['time'],
                    'bytes': s,
                })

    def add_rx_rates(self, event):
        if (
                'name' in event and
                event['name'] == 'transport:packet_received' and
                'data' in event and
                'frames' in event['data']
                ):
            datagrams = [frame for frame in event['data']['frames'] if
                         frame['frame_type'] == 'datagram']
            stream_frames = [frame for frame in event['data']['frames']
                             if frame['frame_type'] == 'stream']

            if len(datagrams) > 0:
                s = sum([datagram['length'] for datagram in datagrams])
                self.dgram_rx.append({
                    'time': event['time'],
                    'bytes': s,
                })
                self.sums_rx.append({
                    'time': event['time'],
                    'bytes': s,
                })

            if len(stream_frames) > 0:
                s = sum([stream['length'] for stream in stream_frames])
                self.stream_tx.append({
                    'time': event['time'],
                    'bytes': s,
                })
                self.sums_rx.append({
                    'time': event['time'],
                    'bytes': s,
                })

    def add_loss(self, event):
        if (
                'name' in event and
                event['name'] == 'recovery:packet_lost'
                ):
            self.packet_loss.append({
                'time': event['time'],
                })

    def read(self, file):
        if file is None:
            return
        with open(file) as f:
            for index, line in enumerate(f):
                event = json.loads(line.strip())
                self.add_bytes_inflight(event)
                self.add_cwnd(event)
                self.add_rtt(event)
                self.add_tx_rates(event)
                self.add_rx_rates(event)
                self.add_loss(event)

        self.set_inflight(self.inflight)
        self.set_cwnd(self.congestion)
        self.set_rtt(self.rtt)
        self.set_dgram_rx(self.dgram_rx)
        self.set_stream_rx(self.stream_rx)
        self.set_rate_rx(self.sums_rx)
        self.set_dgram_tx(self.dgram_tx)
        self.set_stream_tx(self.stream_tx)
        self.set_rate_tx(self.sums_tx)
        self.set_packet_loss(self.packet_loss)

    def set_inflight(self, inflight):
        self._df_inflight = pd.DataFrame(inflight)
        self._df_inflight.index = pd.to_datetime(
                self._df_inflight['time'], unit='ms')

    def set_cwnd(self, congestion):
        if len(congestion) > 0:
            self._df_congestion = pd.DataFrame(congestion)
            self._df_congestion.index = pd.to_datetime(
                    self._df_congestion['time'], unit='ms')

    def set_rtt(self, rtt):
        if len(rtt) > 0:
            self._rtt_df = pd.DataFrame(rtt)
            self._rtt_df.index = pd.to_datetime(
                    self._rtt_df['time'], unit='ms')

    def set_dgram_rx(self, dgram):
        if len(dgram) > 0:
            self._dgram_rx_df = pd.DataFrame(dgram)
            self._dgram_rx_df.index = pd.to_datetime(
                    self._dgram_rx_df['time'], unit='ms')
            self._dgram_rx_df['bytes'] = self._dgram_rx_df['bytes'].apply(
                    lambda x: x * 8)
            self._dgram_rx_df = self._dgram_rx_df.resample('1s').sum()

    def set_stream_rx(self, stream):
        if len(stream) > 0:
            self._stream_rx_df = pd.DataFrame(stream)
            self._stream_rx_df.index = pd.to_datetime(
                    self._stream_rx_df['time'], unit='ms')
            self._stream_rx_df['bytes'] = self._stream_rx_df['bytes'].apply(
                    lambda x: x * 8)
            self._stream_rx_df = self._stream_rx_df.resample('1s').sum()

    def set_rate_rx(self, rate):
        if len(rate) > 0:
            self._rate_rx_df = pd.DataFrame(rate)
            self._rate_rx_df.index = pd.to_datetime(
                    self._rate_rx_df['time'], unit='ms')
            self._rate_rx_df['bytes'] = self._rate_rx_df['bytes'].apply(
                    lambda x: x * 8)
            self._rate_rx_df = self._rate_rx_df.resample('1s').sum()

    def set_dgram_tx(self, dgram):
        if len(dgram) > 0:
            self._dgram_tx_df = pd.DataFrame(dgram)
            self._dgram_tx_df.index = pd.to_datetime(
                    self._dgram_tx_df['time'], unit='ms')
            self._dgram_tx_df['bytes'] = self._dgram_tx_df['bytes'].apply(
                    lambda x: x * 8)
            self._dgram_tx_df = self._dgram_tx_df.resample('1s').sum()

    def set_stream_tx(self, stream):
        if len(stream) > 0:
            self._stream_tx_df = pd.DataFrame(stream)
            self._stream_tx_df.index = pd.to_datetime(
                    self._stream_tx_df['time'], unit='ms')
            self._stream_tx_df['bytes'] = self._stream_tx_df['bytes'].apply(
                    lambda x: x * 8)
            self._stream_tx_df = self._stream_tx_df.resample('1s').sum()

    def set_rate_tx(self, rate):
        if len(rate) > 0:
            self._rate_tx_df = pd.DataFrame(rate)
            self._rate_tx_df.index = pd.to_datetime(
                    self._rate_tx_df['time'], unit='ms')
            self._rate_tx_df['bytes'] = self._rate_tx_df['bytes'].apply(
                    lambda x: x * 8)
            self._rate_tx_df = self._rate_tx_df.resample('1s').sum()

    def set_packet_loss(self, loss):
        if len(loss) > 0:
            self._packet_loss_df = pd.DataFrame(loss)
            self._packet_loss_df['time'] = pd.to_datetime(
                    self._packet_loss_df['time'], unit='ms')

    def plot_rtt(self, ax, params={}):
        if hasattr(self, '_rtt_df') and self._rtt_df is None:
            return

        ax.plot(
            self._rtt_df.index,
            self._rtt_df['latest_rtt'],
            label='Latest RTT',
            linewidth=0.5,
            **params,
        )

        ax.set_xlabel('Time')
        ax.set_ylabel('RTT')
        ax.set_title('QLOG RTT')
        ax.xaxis.set_major_formatter(DateFormatter("%M:%S"))
        ax.yaxis.set_major_formatter(EngFormatter(unit='ms'))

    def plot_rx_rates(self, ax, params={}):
        labels = []
        if hasattr(self, '_datagram_rx_df') and self._dgram_rx_df is not None:
            l, = ax.plot(
                self._dgram_rx_df.index,
                self._dgram_rx_df['bytes'],
                label='Datagram Received',
                linewidth=0.5,
                **params,
            )
            labels.append(l)

        if hasattr(self, '_stream_rx_df') and self._stream_rx_df is not None:
            l, = ax.plot(
                self._stream_rx_df.index,
                self._stream_rx_df['bytes'],
                label='Stream Received',
                linewidth=0.5,
            )
            labels.append(l)

        if hasattr(self, '_rate_rx_df') and self._rate_rx_df is not None:
            l, = ax.plot(
                self._rate_rx_df.index,
                self._rate_rx_df['bytes'],
                label='Total Received',
                linewidth=0.5,
            )
            labels.append(l)
        return labels

    def plot_tx_rates(self, ax, params={}):
        labels = []
        if hasattr(self, '_datagram_tx_df') and self._dgram_tx_df is not None:
            l, = ax.plot(
                self._dgram_tx_df.index,
                self._dgram_tx_df['bytes'],
                label='Datagram Sent',
                linewidth=0.5,
                **params,
            )
            labels.append(l)

        if hasattr(self, '_stream_tx_df') and self._stream_tx_df is not None:
            l, = ax.plot(
                self._stream_tx_df.index,
                self._stream_tx_df['bytes'],
                label='Stream Sent',
                linewidth=0.5,
            )
            labels.append(l)

        if hasattr(self, '_rate_tx_df') and self._rate_tx_df is not None:
            l, = ax.plot(
                self._rate_tx_df.index,
                self._rate_tx_df['bytes'],
                label='Total sent',
                linewidth=0.5,
            )
            labels.append(l)
        return labels

    def plot_cwnd(self, ax, params={}):
        labels = []
        if hasattr(self, '_df_congestion') and self._df_congestion is not None:
            l, = ax.plot(
                self._df_congestion.index,
                self._df_congestion['cwnd'],
                label='CWND',
                linewidth=0.5,
            )
            labels.append(l)

        if hasattr(self, '_df_inflight') and self._df_inflight is not None:
            l, = ax.plot(
                self._df_inflight.index,
                self._df_inflight['bytes_in_flight'],
                label='Bytes in Flight',
                linewidth=0.5,
            )
            labels.append(l)

        if (hasattr(self, '_packet_loss_df') and
                self._packet_loss_df is not None):
            max_a = max(self._df_inflight['bytes_in_flight'])
            max_b = max(self._df_congestion['cwnd'])
            ll = ax.vlines(
                self._packet_loss_df,
                ymin=0,
                ymax=max(max_a, max_b),
                colors='red',
                label='Loss Event',
                linewidth=0.5,
            )
            labels.append(ll)

        if len(labels) > 0:
            ax.set_xlabel('Time')
            ax.set_ylabel('CWND')
            ax.set_title('QLOG CWND/Inflight')
            ax.yaxis.set_major_formatter(EngFormatter(unit='Bytes'))
            ax.xaxis.set_major_formatter(DateFormatter("%M:%S"))
            ax.legend(handles=labels)
