#!/usr/bin/env python

import argparse
import glob
import json
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

    def analyze(self):
        files = [file for file in glob.glob(self._directory + '/**/*',
                 recursive=True) if os.path.isfile(file)]
        config = next((f for f in files if f.endswith('config.json')), None)
        if not config:
            print('config file not found, aborting analyses')
            return

        with open(config) as r:
            c = json.load(r)

        self._config = c
        self._basetime = c.get('start_time')

        self.analyze_rtp(files)
        # self.analyze_pcap(files)
        self.analyze_qlog(files)
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

        if sent and received:
            a.add_latency(sent, received)
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

    def render_html(self):
        environment = Environment(loader=FileSystemLoader('templates/'))
        environment.filters['tojson_pretty'] = to_pretty_json
        template = environment.get_template('experiment.html')
        plots = [{
            'file_name': Path(f).name,
            } for f in self._plot_files]
        print(plots)
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


def analyze_single(args):
    dirs = [d for d in glob.glob(args.input_dir + '/**/*', recursive=True)
            if os.path.isdir(d) and
            any(fname.endswith('config.json') for fname in os.listdir(d))]
    for dir in dirs:
        out = os.path.join(args.output_dir, dir)
        Path(out).mkdir(parents=True, exist_ok=True)
        SingleAnalyzer(dir, out).analyze()


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
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()