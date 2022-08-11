#!/usr/bin/env python

import argparse
import glob
import json
import os

import matplotlib.pyplot as plt

from pathlib import Path

from analyses.rtp_analyser import RTPAnalyser
from analyses.qlog_analyser import QLOGAnalyser


class SingleAnalyzer():
    def __init__(self, input_dir, output_dir):
        self._directory = input_dir
        self._output = output_dir

    def analyze(self):
        files = [file for file in glob.glob(self._directory + '/**/*',
                 recursive=True) if os.path.isfile(file)]
        config = next((f for f in files if f.endswith('config.json')), None)
        if not config:
            print('config file not found, aborting analyses')
            return

        with open(config) as r:
            c = json.load(r)

        self._basetime = c.get('start_time')

        self.analyze_rtp(files)
        self.analyze_qlog(files)

    def analyze_rtp(self, files):
        a = RTPAnalyser(self._basetime)
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

        fig, ax = plt.subplots(figsize=(8, 2), dpi=400)
        a.plot_throughput(ax)
        fig.tight_layout()
        name = os.path.join(self._output, 'rtp_throughput.png')
        fig.savefig(name, bbox_inches='tight')
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(8, 2), dpi=400)
        a.plot_latency(ax)
        fig.tight_layout()
        name = os.path.join(self._output, 'rtp_latency.png')
        fig.savefig(name, bbox_inches='tight')
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(8, 2), dpi=400)
        a.plot_loss(ax)
        fig.tight_layout()
        name = os.path.join(self._output, 'rtp_loss.png')
        fig.savefig(name, bbox_inches='tight')
        plt.close(fig)

    def analyze_pcap(self):
        pass

    def analyze_qlog(self, files):
        sf = next((f for f in files if f.endswith('Server.qlog')), None)
        if sf is not None:
            server = QLOGAnalyser()
            server.read(sf)

            fig, ax = plt.subplots(figsize=(8, 2), dpi=400)
            server.plot_rtt(ax)
            fig.tight_layout()
            name = os.path.join(self._output, 'server_qlog_rtt.png')
            fig.savefig(name, bbox_inches='tight')
            plt.close(fig)

            fig, ax = plt.subplots(figsize=(8, 2), dpi=400)
            server.plot_tx_rates(ax)
            fig.tight_layout()
            name = os.path.join(self._output, 'server_qlog_tx_rates.png')
            fig.savefig(name, bbox_inches='tight')
            plt.close(fig)

            fig, ax = plt.subplots(figsize=(8, 2), dpi=400)
            server.plot_rx_rates(ax)
            fig.tight_layout()
            name = os.path.join(self._output, 'server_qlog_rx_rates.png')
            fig.savefig(name, bbox_inches='tight')
            plt.close(fig)

            fig, ax = plt.subplots(figsize=(8, 2), dpi=400)
            server.plot_cwnd(ax)
            fig.tight_layout()
            name = os.path.join(self._output, 'server_qlog_cwnd.png')
            fig.savefig(name, bbox_inches='tight')
            plt.close(fig)

        cf = next((f for f in files if f.endswith('Client.qlog')), None)
        if cf is not None:
            client = QLOGAnalyser()
            client.read(cf)

            fig, ax = plt.subplots(figsize=(8, 2), dpi=400)
            client.plot_rtt(ax)
            fig.tight_layout()
            name = os.path.join(self._output, 'client_qlog_rtt.png')
            fig.savefig(name, bbox_inches='tight')
            plt.close(fig)

            fig, ax = plt.subplots(figsize=(8, 2), dpi=400)
            client.plot_tx_rates(ax)
            fig.tight_layout()
            name = os.path.join(self._output, 'client_qlog_tx_rates.png')
            fig.savefig(name, bbox_inches='tight')
            plt.close(fig)

            fig, ax = plt.subplots(figsize=(8, 2), dpi=400)
            client.plot_rx_rates(ax)
            fig.tight_layout()
            name = os.path.join(self._output, 'client_qlog_rx_rates.png')
            fig.savefig(name, bbox_inches='tight')
            plt.close(fig)

            fig, ax = plt.subplots(figsize=(8, 2), dpi=400)
            client.plot_cwnd(ax)
            fig.tight_layout()
            name = os.path.join(self._output, 'client_qlog_cwnd.png')
            fig.savefig(name, bbox_inches='tight')
            plt.close(fig)


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
