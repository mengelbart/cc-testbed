import pandas as pd

from matplotlib.dates import DateFormatter
from matplotlib.ticker import EngFormatter, PercentFormatter


def read_rtp(file):
    return pd.read_csv(
        file,
        index_col=0,
        names=['time', 'rate'],
        header=None,
        usecols=[0, 6]
    )


def read_rtcp(file):
    return pd.read_csv(
        file,
        index_col=0,
        names=['time', 'rate'],
        header=None,
        usecols=[0, 1],
    )


def read_capacity(file):
    return pd.read_csv(
        file,
        index_col=0,
        names=['time', 'bandwidth'],
        header=None,
        usecols=[0, 2],
    )


def read_scream_target_rate(file):
    return pd.read_csv(
        file,
        index_col=0,
        names=['time', 'target'],
        header=None,
        usecols=[0, 1]
    )


class RTPAnalyser():
    def __init__(self, basetime):
        self._basetime = basetime

    def set_basetime(self, df):
        if not self._basetime:
            self._basetime = df.index[0]
        df.index = pd.to_datetime(df.index - self._basetime, unit='ms')
        return df

    def add_outgoing_rtp(self, file):
        df = read_rtp(file)
        df = self.set_basetime(df)
        df['rate'] = df['rate'].apply(lambda x: x * 8)
        self._outgoing_rtp = df.resample('1s').sum()

    def add_incoming_rtp(self, file):
        df = read_rtp(file)
        df = self.set_basetime(df)
        df['rate'] = df['rate'].apply(lambda x: x * 8)
        self._incoming_rtp = df.resample('1s').sum()

    def add_capacity(self, file):
        df = read_capacity(file)
        self._capacity = self.set_basetime(df)

    def add_outgoing_rtcp(self, file):
        df = read_rtcp(file)
        df = self.set_basetime(df)
        df['rate'] = df['rate'].apply(lambda x: x * 8)
        self._outgoing_rtcp = df.resample('1s').sum()

    def add_incoming_rtcp(self, file):
        df = read_rtcp(file)
        df = self.set_basetime(df)
        df['rate'] = df['rate'].apply(lambda x: x * 8)
        self._incoming_rtcp = df.resample('1s').sum()

    def add_scream_target_rate(self, file):
        df = read_scream_target_rate(file)
        self._scream_target_rate = self.set_basetime(df)

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
        df = df.drop(['time_send', 'time_receive'], axis=1)
        self._latency = df

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
                df_all['time_send'] - self._basetime, unit='ms')
        df_all['lost'] = df_all['_merge'] == 'left_only'
        df_all = df_all.resample('1s').agg(
                {'time_send': 'count', 'lost': 'sum'})
        df_all['loss_rate'] = df_all['lost'] / df_all['time_send']
        df = df_all.drop('time_send', axis=1)
        self._loss = df.drop('lost', axis=1)

    def plot_throughput(self, ax, params={}):
        labels = []

        defaults = {
                'linewidth': 0.5,
                'label': 'Capacity',
                }
        p = defaults | params
        out, = ax.step(
                self._capacity.index,
                self._capacity.values,
                where='post',
                **p)
        labels.append(out)

        for label, data in {
                'Target Rate': self._scream_target_rate,
                'Transmitted RTP': self._outgoing_rtp,
                'Received RTP': self._incoming_rtp,
                }.items():
            if data is not None:
                defaults = {
                        'linewidth': 0.5,
                        'label': label,
                        }
                p = defaults | params
                out, = ax.plot(data, **p)
                labels.append(out)

        ax.set_xlabel('Time')
        ax.set_ylabel('Rate')
        ax.set_title('RTP Throughput')
        ax.xaxis.set_major_formatter(DateFormatter("%M:%S"))
        ax.yaxis.set_major_formatter(EngFormatter(unit='bit/s'))
        ax.legend(handles=labels, loc='center left', bbox_to_anchor=(1, 0.5))

    def plot_latency(self, ax, params={}):
        if self._latency is not None:
            defaults = {
               's': 0.1,
               'linewidths': 0.5,
            }
            p = defaults | params
            ax.scatter(self._latency.index, self._latency.values, **p)
            ax.set_title('RTP Packet Latency')
            ax.set_ylabel('Latency')
            ax.set_xlabel('Sequence Number')
            ax.yaxis.set_major_formatter(EngFormatter(unit='s'))

    def plot_loss(self, ax, params={}):
        if self._loss is not None:
            defaults = {
                'linewidth': 0.5,
            }
            p = defaults | params
            ax.plot(self._loss, **p)
            ax.set_title('RTP Loss Rate')
            ax.set_xlabel('Time')
            ax.set_ylabel('Loss Rate')
            ax.xaxis.set_major_formatter(DateFormatter("%M:%S"))
            ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0))