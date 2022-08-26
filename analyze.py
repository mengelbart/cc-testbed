#!/usr/bin/env python

import argparse
import glob
import json
import multiprocessing
import os

import pandas as pd

from analyzers.pcap_analyzer import PCAPAnalyzer
from analyzers.flow_analyzer import SingleFlowAnalyzer
from jinja2 import Environment, FileSystemLoader
from pathlib import Path


def read_capacity(file):
    return pd.read_csv(
        file,
        index_col=0,
        names=['time', 'bandwidth'],
        header=None,
        usecols=[0, 2],
    )


class SingleExperimentAnalyzer():
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

        link_file = next((f for f in files if f.endswith('link.log')), None)
        if link_file:
            link = read_capacity(link_file)
            link.index = pd.to_datetime(link.index - self._basetime, unit='ms')

        flows = [flow for flow in c['flows']]
        flow_plots = []
        for flow in flows:
            if 'id' in flow:
                out = os.path.join(self._output, str(flow['id']))
                fa = SingleFlowAnalyzer(flow, out, self._basetime)
                fa.set_link_capacity(link)
                fa.analyze()
                fa.plot()
                flow_plots.append({
                    'id': str(flow['id']),
                    'plots': [{
                        'file_name': Path(pf).relative_to(Path(self._output)),
                    } for pf in fa.plot_files],
                })

        # self.analyze_pcap(files)

        self.save_aggregates()
        self.render_html(flow_plots)

    def analyze_pcap(self, files):
        pcap = next((f for f in files if f.endswith('ls1-eth1.pcap')), None)
        if pcap is None:
            return

        a = PCAPAnalyzer()
        a.read(pcap)

    def save_aggregates(self):
        filename = os.path.join(self._output, 'aggregates.json')
        with open(filename, mode='w', encoding='utf-8') as f:
            json.dump(self._aggregates, f)

    def render_html(self, flows):
        environment = Environment(loader=FileSystemLoader('templates/'))
        environment.filters['tojson_pretty'] = to_pretty_json
        template = environment.get_template('experiment.html')

        context = {
            'flows': flows,
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
    SingleExperimentAnalyzer(args['input_dir'], args['output_dir']).analyze()


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
