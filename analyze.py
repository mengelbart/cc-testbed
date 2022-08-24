#!/usr/bin/env python

import argparse
import glob
import json
import multiprocessing
import os

import datetime as dt
import pandas as pd
import matplotlib.pyplot as plt

from jinja2 import Environment, FileSystemLoader

from matplotlib.dates import DateFormatter
from matplotlib.ticker import EngFormatter

from pathlib import Path

from analyzers.link_analyzer import LinkAnalyzer
from analyzers.pcap_analyzer import PCAPAnalyzer
from analyzers.qlog_analyzer import QLOGAnalyzer
from analyzers.rtp_analyzer import RTPAnalyzer


class SingleAnalyzer():
    def __init__(self, input_dir, output_dir):
        self._directory = input_dir
        self._output = output_dir
        self._plot_files = []
        self._aggregates = {}

    def analyze(self):
        files = [file for file in glob.glob(self._directory + '/**/*',
                 recursive=True) if os.path.isfile(file)]
        config = next((f for f in files if f.endswith('config.json')), None)
        if not config:
            print('config file not found, aborting analyses')
            return

        c = read_config(config)

        config_filename = os.path.join(self._output, 'config.json')
        with open(config_filename, 'w') as file:
            json.dump(c, file)

        self._config = c
        self._basetime = c.get('start_time')

        link_analyzer = LinkAnalyzer(self._basetime)
        link = next((f for f in files if f.endswith('link.log')), None)
        if link:
            link_analyzer.add_capacity(link)

        self.analyze_rtp(files, link_analyzer)
        # self.analyze_pcap(files)
        self.analyze_qlog(files, link_analyzer)

        self.save_aggregates()
        self.render_html()

    def analyze_rtp(self, files, link_analyzer):
        rtpa = RTPAnalyzer(self._basetime)
        scream_target_rate = next(
                (f for f in files if f.endswith('cc.scream')), None)
        if scream_target_rate:
            rtpa.add_scream_target_rate(scream_target_rate)

        gcc_target_rate = next(
                (f for f in files if f.endswith('cc.gcc')), None)
        if gcc_target_rate:
            rtpa.add_gcc_target_rate(gcc_target_rate)

        sent = next((f for f in files if f.endswith('sender.rtp')), None)
        if sent:
            rtpa.add_outgoing_rtp(sent)

        received = next((f for f in files if f.endswith('receiver.rtp')), None)
        if received:
            rtpa.add_incoming_rtp(received)
            self._aggregates['average_goodput'] = rtpa.average_goodput()

        if sent and received:
            rtpa.add_latency(sent, received)
            self._aggregates['latency_stats'] = rtpa.latency_stats()
            rtpa.add_loss(sent, received)

        fig, ax = plt.subplots(figsize=(8, 2), dpi=400)
        labels = []
        labels.append(link_analyzer.plot_capacity(ax))
        labels.extend(rtpa.plot_throughput(ax))
        ax.set_xlabel('Time')
        ax.set_ylabel('Rate')
        ax.set_title('RTP Throughput')
        ax.xaxis.set_major_formatter(DateFormatter("%M:%S"))
        ax.yaxis.set_major_formatter(EngFormatter(unit='bit/s'))
        ax.legend(handles=labels)
        name = os.path.join(self._output, 'rtp_throughput.png')
        self._plot_files.append(name)
        fig.savefig(name, bbox_inches='tight')
        plt.close(fig)

        fig, ax = plt.subplots(dpi=400)
        labels = []
        labels.append(rtpa.plot_departure(ax))
        labels.append(rtpa.plot_arrival(ax))
        ax.xaxis.set_major_formatter(EngFormatter(unit='s'))
        ax.legend(handles=labels)
        name = os.path.join(self._output, 'rtp_departure_arrival.png')
        self._plot_files.append(name)
        fig.savefig(name, bbox_inches='tight')
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(8, 2), dpi=400)
        rtpa.plot_latency_hist(ax)
        ax.set_title('RTP packet latency Histogram')
        name = os.path.join(self._output, 'rtp_latency_hist.png')
        self._plot_files.append(name)
        fig.savefig(name, bbox_inches='tight')
        plt.close(fig)

        # TODO: Use pcap instead of RTP to calculate utilization?
        rate = rtpa._incoming_rtp.copy()
        rate['rate'] = rate['rate'].apply(lambda x: x * 8)
        rate = rate.resample('1s').sum()

        link = link_analyzer._capacity.copy()
        link = link.resample('1s').ffill()
        df = pd.concat(
                [
                    rate['rate'],
                    link['bandwidth'],
                ],
                axis=1,
                keys=['rate', 'bandwidth'])
        df['utilization'] = df['rate'] / df['bandwidth']
        fig, ax = plt.subplots(figsize=(8, 2), dpi=400)
        defaults = {
            'linewidth': 0.5,
            'label': 'RTP Utilization',
        }
        label, = ax.plot(df.utilization, **defaults)
        ax.legend(handles=[label])
        ax.set_title('RTP utilization')
        name = os.path.join(self._output, 'rtp_utilization.png')
        self._plot_files.append(name)
        fig.savefig(name, bbox_inches='tight')
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(8, 2), dpi=400)
        ax.hist(df.utilization, cumulative=True, density=False,
                bins=len(df.utilization))
        ax.set_title('RTP Utilization Histogram')
        name = os.path.join(self._output, 'rtp_utilization_hist.png')
        self._plot_files.append(name)
        fig.savefig(name, bbox_inches='tight')
        plt.close(fig)

        for name, f in {
                'rtp_latency.png': rtpa.plot_latency,
                'rtp_loss.png': rtpa.plot_loss,
                }.items():
            fig, ax = plt.subplots(figsize=(8, 2), dpi=400)
            f(ax)
            name = os.path.join(self._output, name)
            self._plot_files.append(name)
            fig.savefig(name, bbox_inches='tight')
            plt.close(fig)

    def analyze_pcap(self, files):
        pcap = next((f for f in files if f.endswith('ls1-eth1.pcap')), None)
        if pcap is None:
            return

        a = PCAPAnalyzer()
        a.read(pcap)

    def plot_qlog_rates(self, qlog_plot_func, link_analyzer, title, filename):
        labels = []
        fig, ax = plt.subplots(figsize=(8, 2), dpi=400)
        labels.extend(qlog_plot_func(ax))
        labels.append(link_analyzer.plot_capacity(ax))
        ax.set_xlabel('Time')
        ax.set_ylabel('Rate')
        ax.set_title(title)
        ax.xaxis.set_major_formatter(DateFormatter("%M:%S"))
        ax.yaxis.set_major_formatter(EngFormatter(unit='bit/s'))
        ax.legend(handles=labels)
        fig.tight_layout()
        name = os.path.join(self._output, filename)
        self._plot_files.append(name)
        fig.savefig(name, bbox_inches='tight')
        plt.close(fig)

    def analyze_qlog(self, files, link_analyzer):
        sf = next((f for f in files if f.endswith('Server.qlog')), None)
        if sf is not None:
            server = QLOGAnalyzer()
            server.read(sf)

            self.plot_qlog_rates(
                    server.plot_tx_rates, link_analyzer,
                    'QLOG Server Tx Rates', 'server_qlog_tx_rates.png')
            self.plot_qlog_rates(
                    server.plot_rx_rates, link_analyzer,
                    'QLOG Server Rx Rates', 'server_qlog_rx_rates.png')

            for name, f in {
                    'server_qlog_rtt.png': server.plot_rtt,
                    'server_qlog_cwnd.png': server.plot_cwnd,
                    }.items():
                fig, ax = plt.subplots(figsize=(8, 2), dpi=400)
                f(ax)
                fig.tight_layout()
                name = os.path.join(self._output, name)
                self._plot_files.append(name)
                fig.savefig(name, bbox_inches='tight')
                plt.close(fig)

        cf = next((f for f in files if f.endswith('Client.qlog')), None)
        if cf is not None:
            client = QLOGAnalyzer()
            client.read(cf)

            self.plot_qlog_rates(
                    client.plot_tx_rates, link_analyzer,
                    'QLOG Client Tx Rates', 'client_qlog_tx_rates.png')
            self.plot_qlog_rates(
                    client.plot_rx_rates, link_analyzer,
                    'QLOG Client Rx Rates', 'client_qlog_rx_rates.png')

            for name, f in {
                    'client_qlog_rtt.png': client.plot_rtt,
                    'client_qlog_cwnd.png': client.plot_cwnd,
                    }.items():
                fig, ax = plt.subplots(figsize=(8, 2), dpi=400)
                f(ax)
                fig.tight_layout()
                name = os.path.join(self._output, name)
                self._plot_files.append(name)
                fig.savefig(name, bbox_inches='tight')
                plt.close(fig)

    def save_aggregates(self):
        filename = os.path.join(self._output, 'aggregates.json')
        with open(filename, mode='w', encoding='utf-8') as f:
            json.dump(self._aggregates, f)

    def render_html(self):
        environment = Environment(loader=FileSystemLoader('templates/'))
        environment.filters['tojson_pretty'] = to_pretty_json
        template = environment.get_template('experiment.html')
        plots = [{
            'file_name': Path(f).name,
            } for f in self._plot_files]
        context = {
            'plots': plots,
            'config': self._config,
        }
        content = template.render(context)
        filename = os.path.join(self._output, 'index.html')
        with open(filename, mode="w", encoding="utf-8") as f:
            f.write(content)


def to_pretty_json(value):
    data = json.dumps(value, sort_keys=True,
                      indent=4, separators=(',', ': '))
    return data


class AggregateAnalyzer():
    def __init__(self, args):
        pass

    def analyze(self):
        pass


def read_config(path):
    with open(path) as r:
        c = json.load(r)
    return c


def create_index(args):
    dirs = [d for d in glob.glob(args.input_dir + '**', recursive=True)
            if os.path.isdir(d) and
            any(fname.endswith('config.json') for fname in os.listdir(d))]

    environment = Environment(loader=FileSystemLoader('templates/'))
    template = environment.get_template('index.html')
    root = Path(args.output_dir)
    paths = [{
        'path': Path(d).relative_to(root),
        'config': read_config(os.path.join(d, 'config.json')),
    } for d in dirs]
    experiments = [{
        'link': os.path.join(p['path'], 'index.html'),
        'name': str(p['path']),
        'config': p['config'],
    } for p in paths]
    context = {
        'experiments': experiments,
    }
    content = template.render(context)
    filename = os.path.join(args.output_dir, 'index.html')
    with open(filename, mode='w', encoding='utf-8') as f:
        f.write(content)


def run_single(args):
    Path(args['output_dir']).mkdir(parents=True, exist_ok=True)
    SingleAnalyzer(args['input_dir'], args['output_dir']).analyze()


def analyze_single(args):
    dirs = [d for d in glob.glob(args.input_dir + '**', recursive=True)
            if os.path.isdir(d) and
            any(fname.endswith('config.json') for fname in os.listdir(d))]

    pool = multiprocessing.Pool(16)
    args = [{
            'input_dir': dir,
            'output_dir': os.path.join(args.output_dir, dir)
            } for dir in dirs]
    pool.map(
        run_single,
        args,
    )


def analyze_aggregate(args):
    AggregateAnalyzer(args).analyze()


def main():
    parser = argparse.ArgumentParser(
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-i', '--input-dir', required=True)
    parser.add_argument('-o', '--output-dir', required=True)
    subparsers = parser.add_subparsers()
    single = subparsers.add_parser(
            'single',
            help='analyze a single experiment')
    single.set_defaults(func=analyze_single)

    aggregate = subparsers.add_parser(
            'aggregate',
            help='analyze a set of experiments')
    aggregate.set_defaults(func=analyze_aggregate)

    index = subparsers.add_parser(
            'index',
            help='create index HTML page')
    index.set_defaults(func=create_index)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
