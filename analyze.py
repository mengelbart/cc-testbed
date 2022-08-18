#!/usr/bin/env python

import argparse
import glob
import json
import multiprocessing
import os

from jinja2 import Environment, FileSystemLoader
import matplotlib.pyplot as plt

from pathlib import Path

from analyzers.rtp_analyzer import RTPAnalyzer
from analyzers.qlog_analyzer import QLOGAnalyzer
from analyzers.pcap_analyzer import PCAPAnalyzer


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

        self.analyze_rtp(files)
        # self.analyze_pcap(files)
        self.analyze_qlog(files)
        self.save_aggregates()
        self.render_html()

    def analyze_rtp(self, files):
        a = RTPAnalyzer(self._basetime)
        link = next((f for f in files if f.endswith('link.log')), None)
        if link:
            a.add_capacity(link)

        target_rate = next((f for f in files if f.endswith('cc.scream')), None)
        if target_rate:
            a.add_scream_target_rate(target_rate)

        sent = next((f for f in files if f.endswith('sender.rtp')), None)
        if sent:
            a.add_outgoing_rtp(sent)

        received = next((f for f in files if f.endswith('receiver.rtp')), None)
        if received:
            a.add_incoming_rtp(received)
            self._aggregates['average_goodput'] = a.average_goodput()

        if sent and received:
            a.add_latency(sent, received)
            self._aggregates['latency_stats'] = a.latency_stats()
            a.add_loss(sent, received)

        for name, f in {
                'rtp_throughput.png': a.plot_throughput,
                'rtp_latency.png': a.plot_latency,
                'rtp_loss.png': a.plot_loss,
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

    def analyze_qlog(self, files):
        sf = next((f for f in files if f.endswith('Server.qlog')), None)
        if sf is not None:
            server = QLOGAnalyzer()
            server.read(sf)

            for name, f in {
                    'server_qlog_rtt.png': server.plot_rtt,
                    'server_qlog_tx_rates.png': server.plot_tx_rates,
                    'server_qlog_rx_rates.png': server.plot_rx_rates,
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

            for name, f in {
                    'client_qlog_rtt.png': client.plot_rtt,
                    'client_qlog_tx_rates.png': client.plot_tx_rates,
                    'client_qlog_rx_rates.png': client.plot_rx_rates,
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
