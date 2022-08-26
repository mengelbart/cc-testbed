import os

from pathlib import Path
from matplotlib.dates import DateFormatter
from matplotlib.ticker import EngFormatter, PercentFormatter

import matplotlib.pyplot as plt
import pandas as pd

from analyzers.qlog_analyzer import QLOGAnalyzer


class SingleFlowAnalyzer():
    def __init__(self, flow, output_dir, basetime):
        self.config = flow
        self.basetime = basetime
        self.input_dir = flow['log_dir']
        self.output_dir = output_dir
        self.plot_files = []

        self.link: pd.DataFrame = None
        self.scream_target_rate: pd.DataFrame = None
        self.gcc_target_rate: pd.DataFrame = None
        self.outgoing_rtp: pd.DataFrame = None
        self.incoming_rtp: pd.DataFrame = None
        self.loss: pd.DataFrame = None
        self.latency: pd.DataFrame = None
        self.rtp_utilization: pd.DataFrame = None
        self.qlog_server: QLOGAnalyzer = None
        self.qlog_client: QLOGAnalyzer = None

    def analyze(self):
        self.read_rtp_stats()
        self.analyze_qlog()

    def set_link_capacity(self, link: pd.DataFrame):
        self.link = link

    def read_rtp_stats(self):
        p = Path(self.input_dir)
        files = [file for file in p.glob('**/*') if os.path.isfile(file)]

        scream_log_file = next(
                (f for f in files if f.name.endswith('cc.scream')), None)
        if scream_log_file:
            df = read_scream_target_rate(scream_log_file)
            df.index = pd.to_datetime(df.index - self.basetime, unit='ms')
            self.scream_target_rate = df

        gcc_log_file = next(
                (f for f in files if f.name.endswith('cc.gcc')), None)
        if gcc_log_file:
            df = read_gcc_target_rate(gcc_log_file)
            df.index = pd.to_datetime(df.index - self.basetime, unit='ms')
            self.gcc_target_rate = df

        sent = next((f for f in files if f.name.endswith('sender.rtp')), None)
        if sent:
            df = read_rtp(sent)
            df.index = pd.to_datetime(df.index - self.basetime, unit='ms')
            self.outgoing_rtp = df

        received = next(
                (f for f in files if f.name.endswith('receiver.rtp')), None)
        if received:
            df = read_rtp(received)
            df.index = pd.to_datetime(df.index - self.basetime, unit='ms')
            self.incoming_rtp = df

        if received:
            self.add_rtp_utilization()

        if sent and received:
            self.add_latency(sent, received)
            self.add_loss(sent, received)

    def add_loss(self, sent, received):
        df_send = pd.read_csv(
                sent,
                index_col=1,
                names=['time_send', 'nr'],
                header=None,
                usecols=[0, 8],
            )
        df_receive = pd.read_csv(
                received,
                index_col=1,
                names=['time_receive', 'nr'],
                header=None,
                usecols=[0, 8],
            )
        df_all = df_send.merge(
                df_receive, on=['nr'], how='left', indicator=True)
        df_all.index = pd.to_datetime(
                df_all['time_send'] - self.basetime, unit='ms')
        df_all['lost'] = df_all['_merge'] == 'left_only'
        df_all = df_all.resample('1s').agg(
                {'time_send': 'count', 'lost': 'sum'})
        df_all['loss_rate'] = df_all['lost'] / df_all['time_send']
        df = df_all.drop('time_send', axis=1)
        self.loss = df.drop('lost', axis=1)

    def add_latency(self, sent, received):
        df_sent = pd.read_csv(
            sent,
            index_col=1,
            names=['time_send', 'nr'],
            header=None,
            usecols=[0, 8],
        )
        df_received = pd.read_csv(
            received,
            index_col=1,
            names=['time_receive', 'nr'],
            header=None,
            usecols=[0, 8],
        )
        df = df_sent.merge(df_received, on='nr')
        df['diff'] = (df['time_receive'] - df['time_send']) / 1000.0
        df.index = pd.to_datetime(df['time_send'] - self.basetime, unit='ms')
        df = df.drop(['time_send', 'time_receive'], axis=1)
        self.latency = df

    def add_rtp_utilization(self):
        rate = self.incoming_rtp.copy()
        rate['rate'] = rate['rate'].apply(lambda x: x * 8)
        rate = rate.resample('1s').sum()

        link = self.link.copy()
        link = link.resample('1s').ffill()

        df = pd.concat(
            [
                rate['rate'],
                link['bandwidth'],
            ],
            axis=1,
            keys=['rate', 'bandwidth'],
        )
        self.rtp_utilization = df

    def analyze_qlog(self):
        p = Path(self.input_dir)
        files = [file for file in p.glob('**/*') if os.path.isfile(file)]

        sf = next((f for f in files if f.name.endswith('Server.qlog')), None)
        if sf is not None:
            self.qlog_server = QLOGAnalyzer()
            self.qlog_server.read(sf)

        cf = next((f for f in files if f.name.endswith('Client.qlog')), None)
        if cf is not None:
            self.qlog_client = QLOGAnalyzer()
            self.qlog_client.read(cf)

    def plot(self):
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        self.plot_rtp_throughput()
        self.plot_rtp_departure_arrival()
        self.plot_rtp_loss()
        self.plot_rtp_latency()
        self.plot_rtp_latency_hist()
        self.plot_qlog()

    def plot_rtp_throughput(self):
        fig, ax = plt.subplots(figsize=(8, 2), dpi=400)
        labels = []

        labels.append(self.plot_link_capacity(ax))

        outgoing_rtp = self.outgoing_rtp[['rate']].copy()
        outgoing_rtp['rate'] = outgoing_rtp['rate'].apply(lambda x: x * 8)
        outgoing_rtp = outgoing_rtp.resample('1s').sum()

        incoming_rtp = self.incoming_rtp[['rate']].copy()
        incoming_rtp['rate'] = incoming_rtp['rate'].apply(lambda x: x * 8)
        incoming_rtp = incoming_rtp.resample('1s').sum()

        target_rate = None
        if self.scream_target_rate is not None:
            target_rate = self.scream_target_rate
        if self.gcc_target_rate is not None:
            target_rate = self.gcc_target_rate

        for label, data in {
                'Target Rate': target_rate,
                'Transmitted RTP': outgoing_rtp,
                'Received RTP': incoming_rtp,
                }.items():
            if data is not None:
                defaults = {
                        'linewidth': 0.5,
                        'label': label,
                        }
                out, = ax.plot(data, **defaults)
                labels.append(out)

        ax.set_xlabel('Time')
        ax.set_ylabel('Rate')
        ax.set_title('RTP Throughput')
        ax.xaxis.set_major_formatter(DateFormatter("%M:%S"))
        ax.yaxis.set_major_formatter(EngFormatter(unit='bit/s'))
        ax.legend(handles=labels)
        name = os.path.join(self.output_dir, 'rtp_throughput.png')
        self.plot_files.append(name)
        fig.savefig(name, bbox_inches='tight')
        plt.close(fig)

    def plot_rtp_departure_arrival(self):
        fig, ax = plt.subplots(dpi=400)
        labels = []

        defaults = {
            's': 0.1,
            'linewidth': 0.5,
            'label': 'Departure'
        }
        zero = pd.to_datetime(0, unit='ms')
        df = self.outgoing_rtp.copy()
        df.index = df.index - zero
        df.index = df.index.map(lambda x: x.delta / 1e+9)
        out = ax.scatter(df.index, df['nr'], **defaults)
        labels.append(out)

        defaults = {
            's': 0.1,
            'linewidth': 0.5,
            'label': 'Arrival'
        }
        zero = pd.to_datetime(0, unit='ms')
        df = self.incoming_rtp.copy()
        df.index = df.index - zero
        df.index = df.index.map(lambda x: x.delta / 1e+9)
        out = ax.scatter(df.index, df['nr'], **defaults)
        labels.append(out)

        ax.xaxis.set_major_formatter(EngFormatter(unit='s'))
        ax.legend(handles=labels)
        name = os.path.join(self.output_dir, 'rtp_departure_arrival.png')
        self.plot_files.append(name)
        fig.savefig(name, bbox_inches='tight')
        plt.close(fig)

    def plot_rtp_latency_hist(self):
        fig, ax = plt.subplots(figsize=(8, 2), dpi=400)
        ax.hist(
                self.latency['diff'],
                cumulative=False,
                bins=1000,
                density=False)
        ax.set_title('RTP packet latency Histogram')
        name = os.path.join(self.output_dir, 'rtp_latency_hist.png')
        self.plot_files.append(name)
        fig.savefig(name, bbox_inches='tight')
        plt.close(fig)

    def plot_rtp_latency(self):
        fig, ax = plt.subplots(figsize=(8, 2), dpi=400)
        defaults = {
           's': 0.1,
           'linewidths': 0.5,
        }
        ax.scatter(self.latency.index, self.latency.values, **defaults)
        ax.set_title('RTP Packet Latency')
        ax.set_ylabel('Latency')
        ax.set_xlabel('Time')
        ax.yaxis.set_major_formatter(EngFormatter(unit='s'))
        name = os.path.join(self.output_dir, 'rtp_latency.png')
        self.plot_files.append(name)
        fig.savefig(name, bbox_inches='tight')
        plt.close(fig)

    def plot_rtp_loss(self):
        fig, ax = plt.subplots(figsize=(8, 2), dpi=400)
        defaults = {
            'linewidth': 0.5,
        }
        ax.plot(self.loss, **defaults)
        ax.set_title('RTP Loss Rate')
        ax.set_xlabel('Time')
        ax.set_ylabel('Loss Rate')
        ax.xaxis.set_major_formatter(DateFormatter("%M:%S"))
        ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0))
        name = os.path.join(self.output_dir, 'rtp_loss.png')
        self.plot_files.append(name)
        fig.savefig(name, bbox_inches='tight')
        plt.close(fig)

    def plot_qlog_rates(self, qlog_plot_func, title, filename):
        labels = []
        fig, ax = plt.subplots(figsize=(8, 2), dpi=400)

        labels.extend(qlog_plot_func(ax))
        labels.append(self.plot_link_capacity(ax))

        ax.set_xlabel('Time')
        ax.set_ylabel('Rate')
        ax.set_title(title)
        ax.xaxis.set_major_formatter(DateFormatter("%M:%S"))
        ax.yaxis.set_major_formatter(EngFormatter(unit='bit/s'))
        ax.legend(handles=labels)
        fig.tight_layout()
        name = os.path.join(self.output_dir, filename)
        self.plot_files.append(name)
        fig.savefig(name, bbox_inches='tight')
        plt.close(fig)

    def plot_link_capacity(self, ax, params={}):
        defaults = {
                'linewidth': 0.5,
                'label': 'Capacity',
                }
        p = defaults | params
        out, = ax.step(
                self.link.index,
                self.link.values,
                where='post',
                **p)
        return out

    def plot_qlog(self):
        if self.qlog_server:
            self.plot_qlog_rates(
                    self.qlog_server.plot_tx_rates,
                    'QLOG Server Tx Rates', 'server_qlog_tx_rates.png')
            self.plot_qlog_rates(
                    self.qlog_server.plot_rx_rates,
                    'QLOG Server Rx Rates', 'server_qlog_rx_rates.png')

            for name, f in {
                    'server_qlog_rtt.png': self.qlog_server.plot_rtt,
                    'server_qlog_cwnd.png': self.qlog_server.plot_cwnd,
                    }.items():
                fig, ax = plt.subplots(figsize=(8, 2), dpi=400)
                f(ax)
                fig.tight_layout()
                name = os.path.join(self.output_dir, name)
                self.plot_files.append(name)
                fig.savefig(name, bbox_inches='tight')
                plt.close(fig)

        if self.qlog_client:
            self.plot_qlog_rates(
                    self.qlog_client.plot_tx_rates,
                    'QLOG Client Tx Rates', 'client_qlog_tx_rates.png')
            self.plot_qlog_rates(
                    self.qlog_client.plot_rx_rates,
                    'QLOG Client Rx Rates', 'client_qlog_rx_rates.png')

            for name, f in {
                    'client_qlog_rtt.png': self.qlog_client.plot_rtt,
                    'client_qlog_cwnd.png': self.qlog_client.plot_cwnd,
                    }.items():
                fig, ax = plt.subplots(figsize=(8, 2), dpi=400)
                f(ax)
                fig.tight_layout()
                name = os.path.join(self.output_dir, name)
                self.plot_files.append(name)
                fig.savefig(name, bbox_inches='tight')
                plt.close(fig)


def read_rtp(file):
    return pd.read_csv(
        file,
        index_col=0,
        names=['time', 'rate', 'nr'],
        header=None,
        usecols=[0, 6, 8]
    )


def read_scream_target_rate(file):
    return pd.read_csv(
        file,
        index_col=0,
        names=['time', 'target'],
        header=None,
        usecols=[0, 1]
    )


def read_gcc_target_rate(file):
    return pd.read_csv(
        file,
        index_col=0,
        names=['time', 'target'],
        header=None,
        usecols=[0, 1]
    )